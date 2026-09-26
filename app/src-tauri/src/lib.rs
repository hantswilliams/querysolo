// Copyright 2026 Lakelet contributors
// SPDX-License-Identifier: Apache-2.0
//! The Lakelet desktop shell (app brief `build-sessions/app-v0-plan.md`). Step 1: one window
//! per project, one sidecar per window with its memory share (A8), a folder dialog and
//! `lakelet init` for a folder that is not a project yet, the recent list (A10), the session
//! handed to each webview, sidecar events forwarded, the sidecar stopped when its window
//! closes. The logic is in `projects` and `supervisor`, tested without Tauri; this file is
//! the wiring.

pub mod projects;
pub mod supervisor;

use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use tauri::{AppHandle, Emitter, Manager, State, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;

use projects::{canonical, prepare, BucketCheck, OpenProjects, ProjectSettings, RecentProject, RecentProjects};
use supervisor::{Session, DEV_ORIGIN};

pub struct Shell {
    open: OpenProjects,
    recent: RecentProjects,
    /// Per-machine settings by project (decisions C1): the AWS profile each one uses.
    settings: ProjectSettings,
    windows_made: AtomicUsize,
}

/// The project the first window opens: `LAKELET_PROJECT`, else the first argument, else the
/// most recent project that still exists; none of those means the welcome screen.
pub fn first_project(recent: &RecentProjects) -> Option<PathBuf> {
    if let Some(p) = std::env::var_os("LAKELET_PROJECT") {
        return Some(PathBuf::from(p));
    }
    if let Some(p) = std::env::args().nth(1).filter(|a| !a.starts_with('-')) {
        return Some(PathBuf::from(p));
    }
    recent.existing().into_iter().next().map(|p| p.path)
}

fn total_ram() -> u64 {
    let mut system = sysinfo::System::new();
    system.refresh_memory();
    system.total_memory()
}

fn window_title(project: Option<&PathBuf>) -> String {
    match project {
        Some(p) => format!("Lakelet — {}", projects::project_name(p)),
        None => "Lakelet".to_string(),
    }
}

/// Make a window; every window loads the same page and asks for its own session.
fn new_window(app: &AppHandle, shell: &Shell, project: Option<&PathBuf>) -> Result<String, String> {
    let n = shell.windows_made.fetch_add(1, Ordering::SeqCst) + 1;
    let label = format!("project-{n}");
    WebviewWindowBuilder::new(app, &label, WebviewUrl::default())
        .title(window_title(project))
        .inner_size(1180.0, 760.0)
        .min_inner_size(820.0, 520.0)
        .build()
        .map_err(|e| format!("could not open a window: {e}"))?;
    Ok(label)
}

/// Give the window its project and, on a thread, `lakelet init` when the folder needs it
/// and then the sidecar; the webview's `get_session` waits, and the ready (or down) event
/// reaches the window either way.
fn start_in_window(app: AppHandle, shell: Arc<Shell>, label: String, folder: PathBuf, warehouse: Option<String>) {
    shell.open.starting(&label, folder.clone());
    thread::spawn(move || {
        if let Some(w) = app.get_webview_window(&label) {
            let _ = w.set_title(&window_title(Some(&folder)));
        }
        let prepared = match prepare(&shell.open.executable, &folder, warehouse.as_deref()) {
            Ok(prepared) => prepared,
            Err(error) => {
                shell.open.fail(&label, folder, error.clone());
                let _ = app.emit_to(&label, "sidecar", supervisor::SidecarEvent::Down { stderr: error });
                return;
            }
        };
        let _ = shell.recent.remember(&prepared.project);
        let profile = shell.settings.profile_of(&prepared.project);
        match shell.open.open(&label, prepared, profile) {
            Ok(session) => {
                let _ = app.emit_to(&label, "sidecar", supervisor::SidecarEvent::Ready { session });
            }
            Err(error) => {
                let _ = app.emit_to(&label, "sidecar", supervisor::SidecarEvent::Down { stderr: error });
            }
        }
    });
}

/// Open a folder: in this window when it has no project yet, in a new window otherwise;
/// when a window already shows it, bring that one forward. `warehouse` is for a folder
/// that is not a project yet (decisions W1): `lakelet init --warehouse s3://…`.
fn open_folder(app: &AppHandle, shell: &Arc<Shell>, from_label: &str, folder: PathBuf, warehouse: Option<String>) -> Result<(), String> {
    let project = canonical(&folder)?;
    if let Some(existing) = shell.open.window_for(&project) {
        if let Some(w) = app.get_webview_window(&existing) {
            let _ = w.set_focus();
        }
        return Ok(());
    }
    let label = if shell.open.project_of(from_label).is_none() && shell.open.labels().contains(&from_label.to_string()) {
        from_label.to_string()
    } else {
        new_window(app, shell, Some(&project))?
    };
    start_in_window(app.clone(), shell.clone(), label, project, warehouse);
    Ok(())
}

/// A7: the webview asks once and calls `/api` itself with the bearer token. Waits while the
/// sidecar is starting; "no project" means the welcome screen.
#[tauri::command]
async fn get_session(window: tauri::Window, shell: State<'_, Arc<Shell>>) -> Result<Session, String> {
    let shell = shell.inner().clone();
    let label = window.label().to_string();
    tauri::async_runtime::spawn_blocking(move || shell.open.session(&label, Duration::from_secs(30)))
        .await
        .map_err(|e| e.to_string())?
}

/// The window's project, if it has one.
#[tauri::command]
fn window_project(window: tauri::Window, shell: State<'_, Arc<Shell>>) -> Option<String> {
    shell.open.project_of(window.label()).map(|p| p.display().to_string())
}

#[tauri::command]
fn recent_projects(shell: State<'_, Arc<Shell>>) -> Vec<RecentProject> {
    shell.recent.existing()
}

/// A10: the native folder dialog. `None` when the user cancels.
#[tauri::command]
async fn pick_folder(app: AppHandle) -> Option<String> {
    let picked = app.dialog().file().set_title("Open a folder as a Lakelet project").blocking_pick_folder();
    picked.and_then(|p| p.into_path().ok()).map(|p| p.display().to_string())
}

/// A9: the native file dialog for the drop zone's "Choose files…"; empty when cancelled.
#[tauri::command]
async fn pick_files(app: AppHandle) -> Vec<String> {
    let picked = app
        .dialog()
        .file()
        .set_title("Files to import")
        .add_filter("Data files", &["csv", "tsv", "parquet", "json", "jsonl", "xlsx"])
        .blocking_pick_files();
    picked
        .unwrap_or_default()
        .into_iter()
        .filter_map(|p| p.into_path().ok())
        .map(|p| p.display().to_string())
        .collect()
}

/// A11: the shell gave up after two exits in a minute; the window asks for one more start.
#[tauri::command]
fn restart_sidecar(app: AppHandle, window: tauri::Window, shell: State<'_, Arc<Shell>>) -> Result<(), String> {
    let label = window.label().to_string();
    let project = shell.open.project_of(&label).ok_or_else(|| "this window has no project".to_string())?;
    start_in_window(app, shell.inner().clone(), label, project, None);
    Ok(())
}

/// Decisions P1: the New project dialog's check of a bucket before the folder is made,
/// `lakelet bucket check <prefix> --json` on the shell's executable (a window without a
/// project has no core to ask), with the profile the project would use (C1).
#[tauri::command]
async fn check_bucket(shell: State<'_, Arc<Shell>>, prefix: String, profile: Option<String>) -> Result<BucketCheck, String> {
    let executable = shell.open.executable.clone();
    let profile = profile.map(|p| p.trim().to_string()).filter(|p| !p.is_empty());
    tauri::async_runtime::spawn_blocking(move || projects::check_bucket(&executable, &prefix, profile.as_deref()))
        .await
        .map_err(|e| e.to_string())?
}

/// What the About row says (ship brief S8): the app's version and where its `lakelet`
/// came from — the bundled one, `LAKELET_SIDECAR`, or `PATH` — so a bug report names both.
#[derive(serde::Serialize)]
struct About {
    version: String,
    sidecar: String,
    /// "bundled", "environment" or "path"
    sidecar_source: String,
}

#[tauri::command]
fn about(app: AppHandle, shell: State<'_, Arc<Shell>>) -> About {
    let sidecar = shell.open.executable.to_string_lossy().to_string();
    let source = if std::env::var_os("LAKELET_SIDECAR").is_some() {
        "environment"
    } else if app.path().resource_dir().map(|d| Path::new(&sidecar).starts_with(d)).unwrap_or(false) {
        "bundled"
    } else {
        "path"
    };
    About { version: app.package_info().version.to_string(), sidecar, sidecar_source: source.to_string() }
}

/// Decisions C1: the profile names in this machine's `~/.aws/config` and `~/.aws/credentials`.
#[tauri::command]
fn aws_profiles(app: AppHandle) -> Vec<String> {
    app.path().home_dir().map(|home| projects::aws_profiles(&home)).unwrap_or_default()
}

/// Decisions C1: the profile this window's project uses, or none (the AWS default).
#[tauri::command]
fn project_profile(window: tauri::Window, shell: State<'_, Arc<Shell>>) -> Option<String> {
    let project = shell.open.project_of(window.label())?;
    shell.settings.profile_of(&project)
}

/// Decisions C1: set (or clear) the profile of this window's project and start its core
/// again with it, since the environment is read at start.
#[tauri::command]
fn set_project_profile(app: AppHandle, window: tauri::Window, shell: State<'_, Arc<Shell>>, profile: Option<String>) -> Result<(), String> {
    let label = window.label().to_string();
    let project = shell.open.project_of(&label).ok_or_else(|| "this window has no project".to_string())?;
    shell.settings.set_profile(&project, profile.as_deref()).map_err(|e| format!("could not save the profile: {e}"))?;
    start_in_window(app, shell.inner().clone(), label, project, None);
    Ok(())
}

/// Decisions P1: where a new project goes by default — the user's Documents folder, or
/// the home folder when there is none.
#[tauri::command]
fn default_parent(app: AppHandle) -> Option<String> {
    app.path()
        .document_dir()
        .ok()
        .filter(|p| p.is_dir())
        .or_else(|| app.path().home_dir().ok())
        .map(|p| p.display().to_string())
}

/// Decisions P1: a new project — `parent/name` made (or an empty folder of that name
/// taken), then opened, which runs `lakelet init` there, with `--warehouse` for a bucket.
#[tauri::command]
async fn new_project(app: AppHandle, window: tauri::Window, shell: State<'_, Arc<Shell>>, parent: String, name: String, warehouse: Option<String>, profile: Option<String>) -> Result<String, String> {
    let shell = shell.inner().clone();
    let label = window.label().to_string();
    let warehouse = warehouse.map(|w| w.trim().to_string()).filter(|w| !w.is_empty());
    let profile = profile.map(|p| p.trim().to_string()).filter(|p| !p.is_empty());
    tauri::async_runtime::spawn_blocking(move || {
        let folder = projects::new_folder(Path::new(&parent), &name)?;
        if let Some(profile) = &profile {
            // remembered by the canonical path, which is how the window will name it
            let canonical = canonical(&folder)?;
            shell.settings.set_profile(&canonical, Some(profile)).map_err(|e| format!("could not save the profile: {e}"))?;
        }
        open_folder(&app, &shell, &label, folder.clone(), warehouse)?;
        Ok(folder.display().to_string())
    })
    .await
    .map_err(|e| e.to_string())?
}

/// A10: open a folder as a project, running `lakelet init` first when it needs it.
#[tauri::command]
async fn open_project(app: AppHandle, window: tauri::Window, shell: State<'_, Arc<Shell>>, path: String, warehouse: Option<String>) -> Result<(), String> {
    let shell = shell.inner().clone();
    let label = window.label().to_string();
    let warehouse = warehouse.map(|w| w.trim().to_string()).filter(|w| !w.is_empty());
    tauri::async_runtime::spawn_blocking(move || open_folder(&app, &shell, &label, PathBuf::from(path), warehouse))
        .await
        .map_err(|e| e.to_string())?
}

fn monitor(app: AppHandle, shell: Arc<Shell>) {
    loop {
        thread::sleep(Duration::from_millis(500));
        for (label, event) in shell.open.check_all() {
            let _ = app.emit_to(&label, "sidecar", &event);
        }
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .setup(|app| {
            let data_dir = app.path().app_data_dir().unwrap_or_else(|_| std::env::temp_dir().join("lakelet-app"));
            let recent = RecentProjects::at(data_dir.join("recent.json"));
            let settings = ProjectSettings::at(data_dir.join("projects.json"));
            let dev_origin = if cfg!(debug_assertions) { Some(DEV_ORIGIN.to_string()) } else { None };
            let shell = Arc::new(Shell {
                open: OpenProjects::new(
                    supervisor::sidecar_executable(app.path().resource_dir().ok().as_deref()),
                    total_ram(),
                    dev_origin,
                ),
                recent,
                settings,
                windows_made: AtomicUsize::new(0),
            });
            app.manage(shell.clone());
            let handle = app.handle().clone();
            let project = first_project(&shell.recent);
            let label = new_window(&handle, &shell, project.as_ref())?;
            shell.open.add_empty(&label);
            if let Some(folder) = project {
                match canonical(&folder) {
                    Ok(project) => start_in_window(handle.clone(), shell.clone(), label, project, None),
                    // The window shows the reason and the welcome screen's buttons.
                    Err(error) => shell.open.fail(&label, folder, error),
                }
            }
            thread::spawn(move || monitor(handle, shell));
            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::Destroyed = event {
                if let Some(shell) = window.try_state::<Arc<Shell>>() {
                    shell.open.close(window.label());
                }
            }
        })
        .invoke_handler(tauri::generate_handler![get_session, window_project, recent_projects, pick_folder, pick_files, open_project, restart_sidecar, check_bucket, default_parent, new_project, aws_profiles, project_profile, set_project_profile, about])
        .build(tauri::generate_context!())
        .expect("error while building the Lakelet shell")
        .run(|app, event| {
            if let tauri::RunEvent::Exit = event {
                if let Some(shell) = app.try_state::<Arc<Shell>>() {
                    shell.open.close_all();
                }
            }
        });
}
