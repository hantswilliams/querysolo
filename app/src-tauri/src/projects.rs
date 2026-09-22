// Copyright 2026 Lakelet contributors
// SPDX-License-Identifier: Apache-2.0
//! Projects (app brief A8, A10). Which folder a window opens, `lakelet init` when the folder
//! is not a project yet, the recent list in the app's data directory, the memory share each
//! window's sidecar is given, and the registry of open windows: one project per window, one
//! sidecar per window, stopped when the window closes. No Tauri in here, so `cargo test`
//! exercises all of it against the fake sidecar.

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::ffi::OsString;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::Mutex;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};

use crate::supervisor::{Session, SidecarConfig, SidecarEvent, Supervisor};

/// A folder is a project when `lakelet.toml` is in it (core step 2).
pub fn is_project(path: &Path) -> bool {
    path.join("lakelet.toml").is_file()
}

/// The folder's name as the window title and the recent list show it.
pub fn project_name(path: &Path) -> String {
    path.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| path.display().to_string())
}

/// A8: the first window's sidecar gets 60% of RAM; each further window open at the same
/// time halves it. DuckDB takes the value as `<n>MiB`; nothing goes below 256 MiB.
pub fn memory_share(ram_bytes: u64, windows_open: usize) -> String {
    const MIB: u64 = 1024 * 1024;
    let first = ram_bytes / 10 * 6;
    let share = first.checked_shr(windows_open as u32).unwrap_or(0);
    format!("{}MiB", (share / MIB).max(256))
}

/// A folder ready to open: initialised by this call when it was not a project yet, with
/// `lakelet init`'s output so the window can show it (A10).
#[derive(Clone, Debug, PartialEq)]
pub struct Prepared {
    pub project: PathBuf,
    pub initialised: Option<String>,
}

/// The folder's canonical path, which is how windows are matched to projects.
pub fn canonical(folder: &Path) -> Result<PathBuf, String> {
    if !folder.is_dir() {
        return Err(format!("{} is not a folder", folder.display()));
    }
    folder.canonicalize().map_err(|e| format!("{}: {e}", folder.display()))
}

/// Check the folder and run `lakelet init <folder>` when it has no `lakelet.toml`. A
/// `warehouse` (decisions W1: an `s3://bucket/prefix` for the tables' files) goes to `init`
/// as `--warehouse`; it is fixed at init, so a folder that is a project already refuses it
/// rather than opening with a warehouse other than the one asked for.
pub fn prepare(executable: &OsString, folder: &Path, warehouse: Option<&str>) -> Result<Prepared, String> {
    let project = canonical(folder)?;
    if is_project(&project) {
        if let Some(w) = warehouse {
            return Err(format!(
                "{} is a Lakelet project already; its warehouse was fixed when it was set up, so {w} cannot be applied to it. Open a new folder for a project whose tables live in a bucket.",
                project.display()
            ));
        }
        return Ok(Prepared { project, initialised: None });
    }
    let mut init = Command::new(executable);
    init.arg("init").arg(&project);
    if let Some(w) = warehouse {
        init.arg("--warehouse").arg(w);
    }
    let output = init.output().map_err(|e| format!("could not run lakelet init: {e}"))?;
    let text = format!("{}{}", String::from_utf8_lossy(&output.stdout), String::from_utf8_lossy(&output.stderr));
    if !output.status.success() {
        return Err(format!("lakelet init {} failed:\n{}", project.display(), text.trim()));
    }
    if !is_project(&project) {
        return Err(format!("lakelet init {} wrote no lakelet.toml:\n{}", project.display(), text.trim()));
    }
    Ok(Prepared { project, initialised: Some(text.trim().to_string()) })
}

/// What `lakelet bucket check --json` says (decisions P1): the credentials the environment
/// offers, whether the prefix lists and takes a write, and the sentence for the dialog.
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct BucketCheck {
    pub prefix: String,
    pub ok: bool,
    pub read: bool,
    pub write: bool,
    pub error: Option<String>,
    pub sentence: String,
    pub credentials: serde_json::Value,
}

/// Run the core's check for a bucket prefix before a project is made there, with the
/// AWS profile the project would use (decisions C1). The core's exit code says pass or
/// fail; its JSON carries the words. A core that cannot run, or answers with no JSON, is
/// an error of its own.
pub fn check_bucket(executable: &OsString, prefix: &str, profile: Option<&str>) -> Result<BucketCheck, String> {
    let mut command = Command::new(executable);
    command.arg("bucket").arg("check").arg(prefix.trim()).arg("--json");
    if let Some(profile) = profile {
        command.env("AWS_PROFILE", profile);
    }
    let output = command.output().map_err(|e| format!("could not run lakelet bucket check: {e}"))?;
    let stdout = String::from_utf8_lossy(&output.stdout);
    let line = stdout.lines().find(|l| l.trim_start().starts_with('{'));
    match line {
        Some(json) => serde_json::from_str(json).map_err(|e| format!("lakelet bucket check answered oddly: {e}\n{}", stdout.trim())),
        None => Err(format!(
            "lakelet bucket check {} said nothing usable:\n{}{}",
            prefix,
            stdout.trim(),
            String::from_utf8_lossy(&output.stderr).trim()
        )),
    }
}

/// A new project's folder (decisions P1): `parent/name`, made here if it does not exist.
/// A folder that exists must be empty and not a project, so nothing of anyone's is taken
/// over by mistake; the name is one path segment.
pub fn new_folder(parent: &Path, name: &str) -> Result<PathBuf, String> {
    let name = name.trim();
    if name.is_empty() || name == "." || name == ".." || name.contains(['/', '\\']) {
        return Err(format!("a project name is one folder name, not {name:?}"));
    }
    let parent = canonical(parent)?;
    let folder = parent.join(name);
    if folder.exists() {
        if !folder.is_dir() {
            return Err(format!("{} exists and is not a folder", folder.display()));
        }
        if is_project(&folder) {
            return Err(format!("{} is a Lakelet project already; open it instead", folder.display()));
        }
        let occupied = std::fs::read_dir(&folder).map_err(|e| format!("{}: {e}", folder.display()))?.next().is_some();
        if occupied {
            return Err(format!("{} exists and is not empty; pick another name, or open it as it is", folder.display()));
        }
    } else {
        std::fs::create_dir(&folder).map_err(|e| format!("could not make {}: {e}", folder.display()))?;
    }
    Ok(folder)
}

/// The profile names in AWS's own files (decisions C1): `[profile name]` and `[default]`
/// in `~/.aws/config`, `[name]` in `~/.aws/credentials`, as the SDK reads them, with
/// `default` first. Names only; the keys under them are never read.
pub fn aws_profiles(home: &Path) -> Vec<String> {
    let aws = home.join(".aws");
    let mut names: Vec<String> = Vec::new();
    let mut add = |name: &str| {
        let name = name.trim();
        if !name.is_empty() && !names.iter().any(|n| n == name) {
            names.push(name.to_string());
        }
    };
    for (file, prefixed) in [("config", true), ("credentials", false)] {
        let Ok(text) = std::fs::read_to_string(aws.join(file)) else { continue };
        for line in text.lines() {
            let line = line.trim();
            if let Some(inner) = line.strip_prefix('[').and_then(|l| l.strip_suffix(']')) {
                let inner = inner.trim();
                match (prefixed, inner.strip_prefix("profile ")) {
                    (true, Some(name)) => add(name),
                    (true, None) if inner == "default" => add(inner),
                    (true, None) => {} // `[sso-session x]`, `[services x]`: not profiles
                    (false, _) => add(inner),
                }
            }
        }
    }
    names.sort_by(|a, b| (a != "default").cmp(&(b != "default")).then_with(|| a.cmp(b)));
    names
}

/// Which AWS profile each project uses on this machine (decisions C1): a JSON file next
/// to `recent.json`, `{"<canonical path>": {"profile": "name"}}`. A per-person, per-machine
/// fact, so not in `lakelet.toml` (shared, in git) and not in the project's `.lakelet/`.
pub struct ProjectSettings {
    file: PathBuf,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq)]
pub struct ProjectSetting {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub profile: Option<String>,
}

impl ProjectSettings {
    pub fn at(file: impl Into<PathBuf>) -> Self {
        Self { file: file.into() }
    }

    fn all(&self) -> HashMap<String, ProjectSetting> {
        std::fs::read_to_string(&self.file)
            .ok()
            .and_then(|text| serde_json::from_str(&text).ok())
            .unwrap_or_default()
    }

    pub fn profile_of(&self, project: &Path) -> Option<String> {
        self.all().get(&project.display().to_string())?.profile.clone()
    }

    /// Remember the project's profile; `None` forgets it (the AWS default applies).
    pub fn set_profile(&self, project: &Path, profile: Option<&str>) -> std::io::Result<()> {
        let mut all = self.all();
        let key = project.display().to_string();
        let profile = profile.map(str::trim).filter(|p| !p.is_empty()).map(str::to_string);
        match profile {
            Some(p) => all.entry(key).or_default().profile = Some(p),
            None => {
                if let Some(setting) = all.get_mut(&key) {
                    setting.profile = None;
                }
                all.retain(|_, s| *s != ProjectSetting::default());
            }
        }
        if let Some(parent) = self.file.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(&self.file, serde_json::to_string_pretty(&all)?)
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq)]
pub struct RecentProject {
    pub path: PathBuf,
    pub name: String,
    /// Unix seconds of the last open.
    pub opened: u64,
}

pub const MAX_RECENT: usize = 10;

/// The recent list: a JSON file, most recent first, ten entries (A10).
pub struct RecentProjects {
    file: PathBuf,
}

impl RecentProjects {
    pub fn at(file: impl Into<PathBuf>) -> Self {
        Self { file: file.into() }
    }

    pub fn list(&self) -> Vec<RecentProject> {
        std::fs::read_to_string(&self.file)
            .ok()
            .and_then(|text| serde_json::from_str::<Vec<RecentProject>>(&text).ok())
            .unwrap_or_default()
    }

    /// Projects that are still there; a folder that was deleted or is no longer a project
    /// drops out of what the window shows without being forgotten.
    pub fn existing(&self) -> Vec<RecentProject> {
        self.list().into_iter().filter(|p| is_project(&p.path)).collect()
    }

    pub fn remember(&self, project: &Path) -> std::io::Result<()> {
        let mut list: Vec<RecentProject> = self.list().into_iter().filter(|p| p.path != project).collect();
        let opened = SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0);
        list.insert(0, RecentProject { path: project.to_path_buf(), name: project_name(project), opened });
        list.truncate(MAX_RECENT);
        if let Some(parent) = self.file.parent() {
            std::fs::create_dir_all(parent)?;
        }
        std::fs::write(&self.file, serde_json::to_string_pretty(&list)?)
    }
}

/// What a window is doing, as `get_session` sees it.
pub enum WindowState {
    /// The welcome screen: no project chosen yet.
    NoProject,
    /// The sidecar is being spawned; the window shows the amber dot meanwhile (§3.2).
    Starting { project: PathBuf },
    Running { supervisor: Supervisor },
    Failed { project: PathBuf, error: String },
}

/// The open windows, by label. One sidecar each; the memory share counts the others.
pub struct OpenProjects {
    pub executable: OsString,
    pub ram_bytes: u64,
    pub dev_origin: Option<String>,
    pub ready_timeout: Duration,
    windows: Mutex<HashMap<String, WindowState>>,
}

impl OpenProjects {
    pub fn new(executable: OsString, ram_bytes: u64, dev_origin: Option<String>) -> Self {
        Self { executable, ram_bytes, dev_origin, ready_timeout: Duration::from_secs(20), windows: Mutex::new(HashMap::new()) }
    }

    /// Register a window with no project yet (the welcome screen).
    pub fn add_empty(&self, label: &str) {
        self.windows.lock().unwrap().insert(label.to_string(), WindowState::NoProject);
    }

    /// The label of the window already showing this project, if any.
    pub fn window_for(&self, project: &Path) -> Option<String> {
        let windows = self.windows.lock().unwrap();
        windows.iter().find_map(|(label, state)| match state {
            WindowState::Starting { project: p } | WindowState::Failed { project: p, .. } if p == project => Some(label.clone()),
            WindowState::Running { supervisor } if supervisor.session().project == project => Some(label.clone()),
            _ => None,
        })
    }

    pub fn project_of(&self, label: &str) -> Option<PathBuf> {
        let windows = self.windows.lock().unwrap();
        match windows.get(label)? {
            WindowState::NoProject => None,
            WindowState::Starting { project } | WindowState::Failed { project, .. } => Some(project.clone()),
            WindowState::Running { supervisor } => Some(supervisor.session().project.clone()),
        }
    }

    pub fn labels(&self) -> Vec<String> {
        self.windows.lock().unwrap().keys().cloned().collect()
    }

    /// Start the project's sidecar for this window, blocking until it is ready or has
    /// failed. The memory share is 60% of RAM halved for every other window with a sidecar
    /// at this moment (A8); windows already open keep theirs.
    pub fn open(&self, label: &str, prepared: Prepared, profile: Option<String>) -> Result<Session, String> {
        let limit = {
            let mut windows = self.windows.lock().unwrap();
            let others = windows
                .iter()
                .filter(|(l, s)| l.as_str() != label && matches!(s, WindowState::Starting { .. } | WindowState::Running { .. }))
                .count();
            if let Some(WindowState::Running { supervisor }) = windows.get_mut(label) {
                supervisor.stop();
            }
            windows.insert(label.to_string(), WindowState::Starting { project: prepared.project.clone() });
            memory_share(self.ram_bytes, others)
        };
        let config = SidecarConfig {
            executable: self.executable.clone(),
            project: prepared.project.clone(),
            memory_limit: Some(limit),
            dev_origin: self.dev_origin.clone(),
            ready_timeout: self.ready_timeout,
            profile,
        };
        let started = Supervisor::start(config);
        let mut windows = self.windows.lock().unwrap();
        match started {
            Ok(mut supervisor) => {
                supervisor.session_mut().initialised = prepared.initialised;
                let session = supervisor.session().clone();
                windows.insert(label.to_string(), WindowState::Running { supervisor });
                Ok(session)
            }
            Err(e) => {
                let error = format!(
                    "{e}\nsidecar: {}\nproject: {}",
                    self.executable.to_string_lossy(),
                    prepared.project.display()
                );
                windows.insert(label.to_string(), WindowState::Failed { project: prepared.project, error: error.clone() });
                Err(error)
            }
        }
    }

    /// The window has a project and its sidecar is on the way (`open` follows).
    pub fn starting(&self, label: &str, project: PathBuf) {
        self.windows.lock().unwrap().insert(label.to_string(), WindowState::Starting { project });
    }

    /// A window whose project could not be prepared: the reason for `get_session`.
    pub fn fail(&self, label: &str, project: PathBuf, error: String) {
        self.windows.lock().unwrap().insert(label.to_string(), WindowState::Failed { project, error });
    }

    /// The window's session: waits while the sidecar is starting.
    pub fn session(&self, label: &str, timeout: Duration) -> Result<Session, String> {
        let deadline = Instant::now() + timeout;
        loop {
            {
                let windows = self.windows.lock().unwrap();
                match windows.get(label) {
                    None => return Err(format!("no window {label}")),
                    Some(WindowState::NoProject) => return Err("no project".to_string()),
                    Some(WindowState::Running { supervisor }) => return Ok(supervisor.session().clone()),
                    Some(WindowState::Failed { error, .. }) => return Err(error.clone()),
                    Some(WindowState::Starting { .. }) => {}
                }
            }
            if Instant::now() > deadline {
                return Err("the sidecar is still starting".to_string());
            }
            std::thread::sleep(Duration::from_millis(50));
        }
    }

    /// Poll every sidecar once (A11); the events to forward, by window.
    pub fn check_all(&self) -> Vec<(String, SidecarEvent)> {
        let mut windows = self.windows.lock().unwrap();
        let mut events = Vec::new();
        let mut down = Vec::new();
        for (label, state) in windows.iter_mut() {
            if let WindowState::Running { supervisor } = state {
                if let Some(event) = supervisor.check() {
                    if let SidecarEvent::Down { stderr } = &event {
                        down.push((label.clone(), supervisor.session().project.clone(), format!("the core stopped twice in a minute:\n{stderr}")));
                    }
                    events.push((label.clone(), event));
                }
            }
        }
        for (label, project, error) in down {
            windows.insert(label, WindowState::Failed { project, error });
        }
        events
    }

    /// The window closed: stop its sidecar. Returns the sidecar's pid when one was running.
    pub fn close(&self, label: &str) -> Option<u32> {
        let state = self.windows.lock().unwrap().remove(label)?;
        match state {
            WindowState::Running { mut supervisor } => {
                let pid = supervisor.session().pid;
                supervisor.stop();
                Some(pid)
            }
            _ => None,
        }
    }

    /// App exit: stop every sidecar.
    pub fn close_all(&self) {
        for label in self.labels() {
            self.close(&label);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::supervisor::tests::{fake_executable, temp_dir};

    #[test]
    fn the_memory_share_is_sixty_percent_then_halves() {
        let ram = 16 * 1024 * 1024 * 1024u64;
        assert_eq!(memory_share(ram, 0), "9830MiB");
        assert_eq!(memory_share(ram, 1), "4915MiB");
        assert_eq!(memory_share(ram, 2), "2457MiB");
        assert_eq!(memory_share(1024 * 1024 * 1024, 4), "256MiB", "never below the floor");
    }

    #[test]
    fn the_recent_list_is_most_recent_first_without_repeats_and_ten_long() {
        let dir = temp_dir("recent");
        let recent = RecentProjects::at(dir.join("data").join("recent.json"));
        assert!(recent.list().is_empty());
        for i in 0..12 {
            let p = dir.join(format!("p{i}"));
            std::fs::create_dir_all(&p).unwrap();
            std::fs::write(p.join("lakelet.toml"), "").unwrap();
            recent.remember(&p).unwrap();
        }
        recent.remember(&dir.join("p3")).unwrap();
        let list = recent.list();
        assert_eq!(list.len(), MAX_RECENT);
        assert_eq!(list[0].path, dir.join("p3"));
        assert_eq!(list[0].name, "p3");
        assert_eq!(list[1].path, dir.join("p11"));
        assert_eq!(list.iter().filter(|p| p.name == "p3").count(), 1, "remembered once");
        std::fs::remove_file(dir.join("p11").join("lakelet.toml")).unwrap();
        assert!(recent.existing().iter().all(|p| p.name != "p11"), "a folder that is no longer a project is not offered");
        assert_eq!(recent.list().len(), MAX_RECENT, "but is not forgotten");
    }

    #[test]
    fn a_folder_that_is_not_a_project_is_initialised_first() {
        let dir = temp_dir("prepare");
        let exe = fake_executable(&dir, 60);
        let folder = dir.join("fresh");
        std::fs::create_dir_all(&folder).unwrap();
        let prepared = prepare(&exe, &folder, None).expect("init runs");
        assert!(is_project(&prepared.project));
        assert!(prepared.initialised.as_deref().unwrap_or("").contains("lakelet.toml"), "{prepared:?}");
        let again = prepare(&exe, &folder, None).unwrap();
        assert_eq!(again.initialised, None, "an existing project is left alone");
        assert!(prepare(&exe, &dir.join("missing"), None).unwrap_err().contains("not a folder"));
    }

    #[test]
    fn a_warehouse_goes_to_init_and_is_refused_for_a_project_that_exists() {
        let dir = temp_dir("prepare-warehouse");
        let exe = fake_executable(&dir, 60);
        let folder = dir.join("bucketed");
        std::fs::create_dir_all(&folder).unwrap();
        let prepared = prepare(&exe, &folder, Some("s3://lakelet-test/acme")).expect("init runs with --warehouse");
        assert!(is_project(&prepared.project));
        let toml = std::fs::read_to_string(prepared.project.join("lakelet.toml")).unwrap();
        assert!(toml.contains("warehouse = \"s3://lakelet-test/acme\""), "{toml}");
        assert!(prepared.initialised.as_deref().unwrap_or("").contains("s3://lakelet-test/acme"), "{prepared:?}");
        // a folder that is a project already: the warehouse cannot apply, so it is refused
        let refused = prepare(&exe, &folder, Some("s3://other/prefix")).unwrap_err();
        assert!(refused.contains("fixed when it was set up"), "{refused}");
        assert_eq!(prepare(&exe, &folder, None).unwrap().initialised, None);
        // the core refuses anything but s3://, and the refusal reaches the caller
        let bad = dir.join("bad");
        std::fs::create_dir_all(&bad).unwrap();
        let err = prepare(&exe, &bad, Some("/tmp/elsewhere")).unwrap_err();
        assert!(err.contains("s3://bucket/prefix"), "{err}");
        assert!(!is_project(&bad));
    }

    #[test]
    fn the_bucket_check_carries_the_core_s_verdict_and_words() {
        let dir = temp_dir("bucket-check");
        let exe = fake_executable(&dir, 60);
        let ok = check_bucket(&exe, " s3://lakelet-test/acme ", None).expect("the check runs");
        assert!(ok.ok && ok.read && ok.write && ok.error.is_none(), "{ok:?}");
        assert_eq!(ok.prefix, "s3://lakelet-test/acme");
        assert!(ok.sentence.contains("is writable"), "{ok:?}");
        assert_eq!(ok.credentials["source"], "environment");
        let denied = check_bucket(&exe, "s3://denied-bucket/acme", None).unwrap();
        assert!(!denied.ok && denied.read && !denied.write, "{denied:?}");
        assert!(denied.error.as_deref().unwrap_or("").contains("ACCESS_DENIED"), "{denied:?}");
        let nokeys = check_bucket(&exe, "s3://nokeys-bucket/acme", None).unwrap();
        assert!(!nokeys.ok, "{nokeys:?}");
        assert_eq!(nokeys.credentials["source"], "none");
        assert!(nokeys.sentence.contains("no credentials"), "{nokeys:?}");
        let bad = check_bucket(&exe, "/tmp/elsewhere", None).unwrap();
        assert!(!bad.ok && bad.error.as_deref().unwrap_or("").contains("s3://bucket/prefix"), "{bad:?}");
        let missing = OsString::from(dir.join("no-such-lakelet"));
        assert!(check_bucket(&missing, "s3://x/y", None).unwrap_err().contains("could not run"));
        // C1: the profile goes to the check as AWS_PROFILE, and the fake reports it
        let with = check_bucket(&exe, "s3://lakelet-test/acme", Some("acme-data")).unwrap();
        assert_eq!(with.credentials["source"], "profile");
        assert_eq!(with.credentials["profile"], "acme-data");
    }

    #[test]
    fn a_new_folder_is_made_under_the_parent_and_never_takes_one_that_is_in_use() {
        let dir = temp_dir("new-folder");
        let folder = new_folder(&dir, " acme ").unwrap();
        assert_eq!(folder, dir.canonicalize().unwrap().join("acme"));
        assert!(folder.is_dir());
        assert_eq!(new_folder(&dir, "acme").unwrap(), folder, "an empty folder is fine to use");
        std::fs::write(folder.join("lakelet.toml"), "").unwrap();
        assert!(new_folder(&dir, "acme").unwrap_err().contains("project already"));
        let busy = dir.join("busy");
        std::fs::create_dir_all(&busy).unwrap();
        std::fs::write(busy.join("notes.txt"), "x").unwrap();
        assert!(new_folder(&dir, "busy").unwrap_err().contains("not empty"));
        std::fs::write(dir.join("file"), "x").unwrap();
        assert!(new_folder(&dir, "file").unwrap_err().contains("not a folder"));
        for bad in ["", " ", ".", "..", "a/b", "a\\b"] {
            assert!(new_folder(&dir, bad).unwrap_err().contains("one folder name"), "{bad:?}");
        }
        assert!(new_folder(&dir.join("missing"), "x").unwrap_err().contains("not a folder"));
    }

    #[test]
    fn the_profile_names_come_from_aws_s_own_files_and_nothing_else_is_read() {
        let home = temp_dir("aws-profiles");
        assert!(aws_profiles(&home).is_empty(), "no ~/.aws: no profiles");
        std::fs::create_dir_all(home.join(".aws")).unwrap();
        std::fs::write(
            home.join(".aws").join("config"),
            "[default]\nregion = us-east-1\n\n[profile work]\nsso_session = corp\n\n[sso-session corp]\nsso_start_url = x\n\n[profile client-b]\nregion = eu-west-1\n",
        )
        .unwrap();
        std::fs::write(home.join(".aws").join("credentials"), "[personal]\naws_access_key_id = AKIA\naws_secret_access_key = s\n\n[work]\naws_access_key_id = AKIB\n").unwrap();
        assert_eq!(aws_profiles(&home), vec!["default", "client-b", "personal", "work"], "default first, then sorted, each once, sso-session left out");
    }

    #[test]
    fn a_project_s_profile_is_remembered_per_machine_and_forgotten_on_none() {
        let dir = temp_dir("project-settings");
        let settings = ProjectSettings::at(dir.join("data").join("projects.json"));
        let acme = dir.join("acme");
        assert_eq!(settings.profile_of(&acme), None);
        settings.set_profile(&acme, Some(" work ")).unwrap();
        assert_eq!(settings.profile_of(&acme), Some("work".to_string()));
        assert_eq!(settings.profile_of(&dir.join("other")), None);
        settings.set_profile(&acme, Some("")).unwrap();
        assert_eq!(settings.profile_of(&acme), None);
        assert_eq!(std::fs::read_to_string(dir.join("data").join("projects.json")).unwrap().trim(), "{}", "an empty setting leaves no entry");
    }

    #[test]
    fn two_windows_get_two_sidecars_with_halved_limits_and_closing_kills() {
        let dir = temp_dir("windows");
        let exe = fake_executable(&dir, 60);
        let ram = 10 * 1024 * 1024 * 1024u64;
        let open = OpenProjects::new(exe.clone(), ram, Some("http://localhost:5173".into()));
        let a = prepare(&exe, &{ let p = dir.join("a"); std::fs::create_dir_all(&p).unwrap(); p }, None).unwrap();
        let b = prepare(&exe, &{ let p = dir.join("b"); std::fs::create_dir_all(&p).unwrap(); p }, None).unwrap();

        let sa = open.open("project-1", a.clone(), None).expect("first sidecar starts");
        assert!(sa.ready_ms > 0 && sa.ready_ms < 10_000, "spawn to ready is measured: {}", sa.ready_ms);
        assert!(sa.initialised.as_deref().unwrap_or("").contains("lakelet.toml"), "the init output reaches the window");
        let sb = open.open("project-2", b.clone(), Some("acme-data".to_string())).expect("second sidecar starts");
        assert_ne!(sa.pid, sb.pid);
        let args_a = std::fs::read_to_string(a.project.join(".lakelet").join("fake-args.txt")).unwrap();
        let args_b = std::fs::read_to_string(b.project.join(".lakelet").join("fake-args.txt")).unwrap();
        assert!(args_a.contains("--memory-limit 6144MiB"), "{args_a}");
        assert!(args_b.contains("--memory-limit 3072MiB"), "halved for the second window: {args_b}");
        // C1: the project's profile reaches the sidecar as AWS_PROFILE; none means none
        assert!(args_b.contains("env AWS_PROFILE=acme-data"), "{args_b}");
        assert!(!args_a.contains("AWS_PROFILE"), "{args_a}");
        // F1: each sidecar runs in its own project folder, whatever the shell's cwd is
        let canon = |p: &std::path::Path| std::fs::canonicalize(p).unwrap().display().to_string();
        assert!(args_a.contains(&format!("cwd={}", canon(&a.project))), "{args_a}");
        assert!(args_b.contains(&format!("cwd={}", canon(&b.project))), "{args_b}");

        assert_eq!(open.window_for(&b.project), Some("project-2".to_string()));
        assert_eq!(open.project_of("project-1"), Some(a.project.clone()));
        assert_eq!(open.session("project-2", Duration::from_secs(1)).unwrap().pid, sb.pid);
        assert!(open.check_all().is_empty(), "both healthy");

        let pid = open.close("project-2").expect("a sidecar was running");
        assert_eq!(pid, sb.pid);
        assert!(!alive(pid), "closing the window killed its sidecar; no orphan");
        assert!(alive(sa.pid), "the other window's sidecar is untouched");
        assert_eq!(open.window_for(&b.project), None);
        open.close_all();
        assert!(!alive(sa.pid));
        assert!(open.labels().is_empty());
    }

    #[cfg(unix)]
    fn alive(pid: u32) -> bool {
        // `kill -0` on a reaped child fails, which is the point: the supervisor waits on it.
        Command::new("kill").arg("-0").arg(pid.to_string()).output().map(|o| o.status.success()).unwrap_or(false)
    }

    #[cfg(windows)]
    fn alive(pid: u32) -> bool {
        let out = Command::new("tasklist").arg("/FI").arg(format!("PID eq {pid}")).output().unwrap();
        String::from_utf8_lossy(&out.stdout).contains(&pid.to_string())
    }
}
