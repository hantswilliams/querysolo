// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
//! The sidecar supervisor (app brief A6, A8, A11). One `querysolo serve` per window: spawned
//! with a per-window memory limit, ready when its stdout says `serving` and
//! `.querysolo/serve.json` names the port and the token, restarted once if it exits, stopped
//! after two exits inside a minute, killed when the window closes.

use serde::{Deserialize, Serialize};
use std::collections::VecDeque;
use std::ffi::OsString;
use std::io::{BufRead, BufReader, Read};
use std::path::{Path, PathBuf};
use std::process::{Child, Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};

/// What the webview needs to call `/api`: the loopback port and the per-launch token,
/// from `serve.json` (core step 9), plus the sidecar's pid for the status line, how long
/// spawn to ready took (the launch budget, §3.2, measured rather than eyeballed), and
/// `querysolo init`'s output when opening this folder initialised it (A10).
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct Session {
    pub port: u16,
    pub token: String,
    pub pid: u32,
    pub project: PathBuf,
    pub ready_ms: u64,
    pub initialised: Option<String>,
}

#[derive(Clone, Debug)]
pub struct SidecarConfig {
    /// The `querysolo` executable: `QUERYSOLO_SIDECAR` in development and tests, the bundled
    /// sidecar in a build (session 10), else `querysolo` on `PATH`.
    pub executable: OsString,
    pub project: PathBuf,
    /// DuckDB's limit for this process only (A8); `None` leaves `querysolo.toml`'s value.
    pub memory_limit: Option<String>,
    /// In a debug build the window's origin is the Vite dev server, not `tauri://localhost`,
    /// so the sidecar must allow it (`QUERYSOLO_DEV_ORIGIN`); a release build passes nothing.
    pub dev_origin: Option<String>,
    pub ready_timeout: Duration,
    /// The AWS profile this project uses (decisions C1): `AWS_PROFILE` on the sidecar, so
    /// the core's credential chain reads that section of `~/.aws/credentials` (or the SSO
    /// cache); `None` leaves the environment as it is. The shell never holds a key.
    pub profile: Option<String>,
}

impl SidecarConfig {
    pub fn new(project: impl Into<PathBuf>) -> Self {
        Self {
            executable: sidecar_executable(None),
            project: project.into(),
            memory_limit: None,
            dev_origin: if cfg!(debug_assertions) { Some(DEV_ORIGIN.to_string()) } else { None },
            ready_timeout: Duration::from_secs(20),
            profile: None,
        }
    }
}

/// The Vite dev server, as `tauri.conf.json`'s `devUrl` and `vite.config.ts` agree.
pub const DEV_ORIGIN: &str = "http://localhost:5173";

/// Where the `querysolo` executable is, in the order the ship brief fixes (S1):
/// `QUERYSOLO_SIDECAR` when set (development, the tests, a build pointed elsewhere), else the
/// frozen core the bundle carries as a resource (`<resources>/querysolo/querysolo`, from
/// `core/dist/querysolo/`), else `querysolo` on `PATH`.
pub fn sidecar_executable(resource_dir: Option<&Path>) -> OsString {
    if let Some(set) = std::env::var_os("QUERYSOLO_SIDECAR") {
        return set;
    }
    if let Some(dir) = resource_dir {
        let name = if cfg!(windows) { "querysolo.exe" } else { "querysolo" };
        let bundled = dir.join("querysolo").join(name);
        if bundled.is_file() {
            return bundled.into_os_string();
        }
    }
    OsString::from("querysolo")
}

#[derive(Debug)]
pub enum SidecarError {
    Spawn(std::io::Error),
    /// The sidecar exited before it said `serving`; carries its last output.
    ExitedEarly(String),
    NotReady(Duration),
    ServeJson(String),
}

impl std::fmt::Display for SidecarError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SidecarError::Spawn(e) => write!(f, "could not start the querysolo sidecar: {e}"),
            SidecarError::ExitedEarly(out) => write!(f, "the sidecar exited before it was ready:\n{out}"),
            SidecarError::NotReady(t) => write!(f, "the sidecar did not say `serving` within {t:?}"),
            SidecarError::ServeJson(e) => write!(f, "could not read serve.json: {e}"),
        }
    }
}

impl std::error::Error for SidecarError {}

/// Something the window should show (A11).
#[derive(Clone, Debug, Serialize, PartialEq)]
#[serde(tag = "kind", rename_all = "snake_case")]
pub enum SidecarEvent {
    Ready { session: Session },
    Restarted { session: Session },
    /// Two exits inside a minute: no more restarts; the last lines of stderr for the user.
    Down { stderr: String },
}

pub struct Supervisor {
    config: SidecarConfig,
    child: Child,
    session: Session,
    exits: VecDeque<Instant>,
    stderr_tail: mpsc::Receiver<String>,
}

const RESTART_WINDOW: Duration = Duration::from_secs(60);
const MAX_EXITS_IN_WINDOW: usize = 2;

impl Supervisor {
    /// Spawn the sidecar and wait for it to be ready.
    pub fn start(config: SidecarConfig) -> Result<Self, SidecarError> {
        let (child, session, stderr_tail) = spawn(&config)?;
        Ok(Self { config, child, session, exits: VecDeque::new(), stderr_tail })
    }

    pub fn session(&self) -> &Session {
        &self.session
    }

    pub fn session_mut(&mut self) -> &mut Session {
        &mut self.session
    }

    /// Poll: `None` while the sidecar runs; on exit, restart once and report it, or give up
    /// after two exits inside a minute and report the stderr tail.
    pub fn check(&mut self) -> Option<SidecarEvent> {
        match self.child.try_wait() {
            Ok(None) => None,
            Ok(Some(_)) | Err(_) => {
                let now = Instant::now();
                self.exits.push_back(now);
                while let Some(first) = self.exits.front() {
                    if now.duration_since(*first) > RESTART_WINDOW {
                        self.exits.pop_front();
                    } else {
                        break;
                    }
                }
                let stderr = self.drain_stderr();
                if self.exits.len() >= MAX_EXITS_IN_WINDOW {
                    return Some(SidecarEvent::Down { stderr });
                }
                match spawn(&self.config) {
                    Ok((child, session, tail)) => {
                        self.child = child;
                        self.session = session.clone();
                        self.stderr_tail = tail;
                        Some(SidecarEvent::Restarted { session })
                    }
                    Err(e) => Some(SidecarEvent::Down { stderr: format!("{stderr}\n{e}") }),
                }
            }
        }
    }

    fn drain_stderr(&mut self) -> String {
        let mut lines: Vec<String> = self.stderr_tail.try_iter().collect();
        if lines.len() > 20 {
            lines = lines.split_off(lines.len() - 20);
        }
        lines.join("\n")
    }

    /// Kill the sidecar (window close, app exit).
    pub fn stop(&mut self) {
        let _ = self.child.kill();
        let _ = self.child.wait();
    }
}

impl Drop for Supervisor {
    fn drop(&mut self) {
        self.stop();
    }
}

fn spawn(config: &SidecarConfig) -> Result<(Child, Session, mpsc::Receiver<String>), SidecarError> {
    let t0 = Instant::now();
    let mut command = Command::new(&config.executable);
    command
        .arg("-C")
        .arg(&config.project)
        .arg("serve")
        .arg("--port")
        .arg("0")
        // The project is the sidecar's working directory (decisions F1): a Dock-launched
        // app inherits `/`, and DuckDB's Iceberg extension makes a `data/` folder relative
        // to the cwd on the first CREATE TABLE. The core tidies that folder; the cwd must
        // at least be one it may write.
        .current_dir(&config.project)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    if let Some(limit) = &config.memory_limit {
        command.arg("--memory-limit").arg(limit);
    }
    command.env_remove("QUERYSOLO_DEV_ORIGIN");
    if let Some(origin) = &config.dev_origin {
        command.env("QUERYSOLO_DEV_ORIGIN", origin);
    }
    if let Some(profile) = &config.profile {
        command.env("AWS_PROFILE", profile);
    }
    let mut child = command.spawn().map_err(SidecarError::Spawn)?;

    // stderr is read on a thread for the life of the process; the supervisor keeps a tail.
    let (tx, rx) = mpsc::channel::<String>();
    if let Some(stderr) = child.stderr.take() {
        thread::spawn(move || {
            for line in BufReader::new(stderr).lines().map_while(Result::ok) {
                if tx.send(line).is_err() {
                    break;
                }
            }
        });
    }

    // Readiness: the `serving http://127.0.0.1:<port>: ...` line the core prints (A6).
    let stdout = child.stdout.take().expect("stdout is piped");
    let (ready_tx, ready_rx) = mpsc::channel::<String>();
    thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        let mut seen = String::new();
        let mut line = String::new();
        loop {
            line.clear();
            match reader.read_line(&mut line) {
                Ok(0) | Err(_) => {
                    let _ = ready_tx.send(format!("<eof>{seen}"));
                    break;
                }
                Ok(_) => {
                    seen.push_str(&line);
                    if line.starts_with("serving ") {
                        let _ = ready_tx.send(line.clone());
                        // keep draining so the sidecar never blocks on a full pipe
                        let mut rest = Vec::new();
                        let _ = reader.read_to_end(&mut rest);
                        break;
                    }
                }
            }
        }
    });

    match ready_rx.recv_timeout(config.ready_timeout) {
        Ok(line) if line.starts_with("serving ") => {
            let mut session = read_serve_json(&config.project, child.id())?;
            session.ready_ms = t0.elapsed().as_millis() as u64;
            Ok((child, session, rx))
        }
        Ok(output) => {
            let _ = child.kill();
            let stderr: Vec<String> = rx.try_iter().collect();
            let out = output.trim_start_matches("<eof>").to_string();
            Err(SidecarError::ExitedEarly(format!("{out}{}", stderr.join("\n"))))
        }
        Err(_) => {
            let _ = child.kill();
            Err(SidecarError::NotReady(config.ready_timeout))
        }
    }
}

#[derive(Deserialize)]
struct ServeJson {
    port: u16,
    token: String,
}

fn read_serve_json(project: &Path, pid: u32) -> Result<Session, SidecarError> {
    let path = project.join(".querysolo").join("serve.json");
    let text = std::fs::read_to_string(&path).map_err(|e| SidecarError::ServeJson(format!("{}: {e}", path.display())))?;
    let parsed: ServeJson = serde_json::from_str(&text).map_err(|e| SidecarError::ServeJson(e.to_string()))?;
    Ok(Session { port: parsed.port, token: parsed.token, pid, project: project.to_path_buf(), ready_ms: 0, initialised: None })
}

#[cfg(test)]
pub(crate) mod tests {
    use super::*;

    #[test]
    fn the_sidecar_is_the_variable_then_the_bundled_one_then_path() {
        // the environment is process-wide; the test that sets it must also clear it
        std::env::remove_var("QUERYSOLO_SIDECAR");
        let dir = temp_dir("sidecar-order");
        assert_eq!(sidecar_executable(None), OsString::from("querysolo"), "nothing set, nothing bundled: PATH");
        assert_eq!(sidecar_executable(Some(&dir)), OsString::from("querysolo"), "a resource dir with no core in it: PATH");
        let name = if cfg!(windows) { "querysolo.exe" } else { "querysolo" };
        std::fs::create_dir_all(dir.join("querysolo")).unwrap();
        std::fs::write(dir.join("querysolo").join(name), b"").unwrap();
        assert_eq!(sidecar_executable(Some(&dir)), dir.join("querysolo").join(name).into_os_string(), "the bundled core");
        std::env::set_var("QUERYSOLO_SIDECAR", "/elsewhere/querysolo");
        assert_eq!(sidecar_executable(Some(&dir)), OsString::from("/elsewhere/querysolo"), "the variable wins");
        std::env::remove_var("QUERYSOLO_SIDECAR");
    }

    /// A stand-in for the `querysolo` executable (`tests/fake_sidecar.py`): `init` writes a
    /// `querysolo.toml`; `serve` writes serve.json, prints the `serving` line, then lives for
    /// `QUERYSOLO_FAKE_LIFETIME` seconds (or until killed). Python so it runs on every
    /// platform the shell does; the launcher is a tiny wrapper written into the temp dir.
    pub(crate) fn fake_executable(dir: &Path, lifetime_secs: u32) -> OsString {
        let script = std::env::current_dir().unwrap().join("tests").join("fake_sidecar.py");
        let python = std::env::var_os("PYTHON").unwrap_or_else(|| OsString::from("python3"));
        // The fake takes the same arguments as the real thing; the launcher is python plus
        // the script, expressed as an executable via a tiny wrapper written into the temp dir.
        let wrapper = dir.join(if cfg!(windows) { "fake.cmd" } else { "fake.sh" });
        let body = if cfg!(windows) {
            format!("@echo off\r\nset QUERYSOLO_FAKE_LIFETIME={lifetime_secs}\r\n\"{}\" \"{}\" %*\r\n", python.to_string_lossy(), script.display())
        } else {
            format!("#!/bin/sh\nexport QUERYSOLO_FAKE_LIFETIME={lifetime_secs}\nexec \"{}\" \"{}\" \"$@\"\n", python.to_string_lossy(), script.display())
        };
        std::fs::write(&wrapper, body).unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            std::fs::set_permissions(&wrapper, std::fs::Permissions::from_mode(0o755)).unwrap();
        }
        wrapper.into_os_string()
    }

    fn fake_sidecar(dir: &Path, lifetime_secs: u32) -> SidecarConfig {
        let project = dir.join("proj");
        std::fs::create_dir_all(project.join(".querysolo")).unwrap();
        SidecarConfig {
            executable: fake_executable(dir, lifetime_secs),
            project,
            memory_limit: Some("1GB".into()),
            dev_origin: Some("http://localhost:5173".into()),
            ready_timeout: Duration::from_secs(10),
            profile: None,
        }
    }

    pub(crate) fn temp_dir(name: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!("querysolo-supervisor-{name}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    /// The "nothing hidden" line of §6: a release build passes no dev origin, so a bundled
    /// app's sidecar allows only the Tauri origins. Run with `cargo test --release` to hold
    /// it against the build that ships; in a debug build the origin is the Vite server's.
    #[test]
    fn a_release_build_passes_no_dev_origin() {
        let config = SidecarConfig::new("/nowhere");
        if cfg!(debug_assertions) {
            assert_eq!(config.dev_origin.as_deref(), Some(DEV_ORIGIN));
        } else {
            assert_eq!(config.dev_origin, None, "a shipped app never widens CORS");
        }
    }

    #[test]
    fn starts_reads_serve_json_and_stops() {
        let dir = temp_dir("start");
        let config = fake_sidecar(&dir, 60);
        let mut sup = Supervisor::start(config.clone()).expect("the fake sidecar starts");
        let session = sup.session().clone();
        assert_eq!(session.project, config.project);
        assert!(session.port > 0 && session.token.len() > 10);
        assert!(session.ready_ms > 0, "spawn to ready is measured");
        assert!(sup.check().is_none(), "healthy sidecar reports nothing");
        // the fake records the arguments it was given, so the memory limit is checkable
        let args = std::fs::read_to_string(config.project.join(".querysolo").join("fake-args.txt")).unwrap();
        assert!(args.contains("--memory-limit 1GB"), "{args}");
        assert!(args.contains("serve --port 0"), "{args}");
        assert!(args.contains("env QUERYSOLO_DEV_ORIGIN=http://localhost:5173"), "{args}");
        sup.stop();
        assert!(sup.child.try_wait().unwrap().is_some(), "stopped");
    }

    #[test]
    fn restarts_once_then_gives_up_inside_a_minute() {
        let dir = temp_dir("restart");
        let config = fake_sidecar(&dir, 1); // exits after one second, every time
        let mut sup = Supervisor::start(config).expect("starts");
        let first_pid = sup.session().pid;
        let restarted = wait_for_event(&mut sup);
        match restarted {
            SidecarEvent::Restarted { session } => assert_ne!(session.pid, first_pid),
            other => panic!("expected a restart, got {other:?}"),
        }
        let down = wait_for_event(&mut sup);
        assert!(matches!(down, SidecarEvent::Down { .. }), "second exit inside a minute stops: {down:?}");
    }

    fn wait_for_event(sup: &mut Supervisor) -> SidecarEvent {
        let deadline = Instant::now() + Duration::from_secs(15);
        loop {
            if let Some(event) = sup.check() {
                return event;
            }
            assert!(Instant::now() < deadline, "no event within 15 s");
            thread::sleep(Duration::from_millis(50));
        }
    }

    #[test]
    fn a_sidecar_that_never_says_serving_is_an_error_with_its_output() {
        let dir = temp_dir("early");
        let mut config = fake_sidecar(&dir, 0); // lifetime 0: prints an error and exits
        config.ready_timeout = Duration::from_secs(10);
        match Supervisor::start(config) {
            Err(SidecarError::ExitedEarly(out)) => assert!(out.contains("fake sidecar refusing"), "{out}"),
            other => panic!("expected ExitedEarly, got {:?}", other.map(|_| ())),
        }
    }
}
