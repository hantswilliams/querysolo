// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The shell's commands (app brief A7, A10). Inside Tauri each window asks the shell for its
// project and its session once, and opens folders through it; in a browser (development,
// Playwright) the session comes from the URL, ?port=…&token=…, against a `querysolo serve`
// started with QUERYSOLO_DEV_ORIGIN (A12), and there is no folder dialog.

export interface Session {
  port: number;
  token: string;
  pid: number;
  project: string;
  /** Spawn to `serving` line and serve.json read, as the shell measured it (§3.2). */
  ready_ms: number;
  /** `querysolo init`'s output when opening this folder initialised it. */
  initialised: string | null;
}

export interface RecentProject {
  path: string;
  name: string;
  opened: number;
}

export type SidecarEvent =
  | { kind: 'ready'; session: Session }
  | { kind: 'restarted'; session: Session }
  | { kind: 'down'; stderr: string };

export const inTauri = (): boolean => typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;

async function invoke<T>(command: string, args?: Record<string, unknown>): Promise<T> {
  const tauri = await import('@tauri-apps/api/core');
  return tauri.invoke<T>(command, args);
}

const params = () => new URLSearchParams(window.location.search);

/** The window's project, or null for the welcome screen. */
export async function windowProject(): Promise<string | null> {
  if (inTauri()) return invoke<string | null>('window_project');
  const p = params();
  return p.get('port') ? (p.get('project') ?? '') : null;
}

/** The session; inside Tauri this waits while the sidecar starts. */
export async function getSession(): Promise<Session> {
  if (inTauri()) return invoke<Session>('get_session');
  const p = params();
  const port = Number(p.get('port'));
  const token = p.get('token') ?? '';
  if (!port || !token) throw new Error('no session: open through the QuerySolo app, or pass ?port=&token= from serve.json');
  return { port, token, pid: 0, project: p.get('project') ?? '', ready_ms: Number(p.get('ready_ms') ?? 0), initialised: null };
}

export async function recentProjects(): Promise<RecentProject[]> {
  return inTauri() ? invoke<RecentProject[]>('recent_projects') : [];
}

/** The native folder dialog; null when cancelled. Only the app has one. */
export async function pickFolder(): Promise<string | null> {
  if (!inTauri()) throw new Error('the folder dialog is only in the app; in a browser, pass ?port=&token= from serve.json');
  return invoke<string | null>('pick_folder');
}

/** Open a folder as a project: this window when it has none, else a new one (A10). A
 *  `warehouse` (an `s3://bucket/prefix`, decisions W1) goes to `querysolo init --warehouse`
 *  when the folder is not a project yet; a folder that is one already refuses it. */
export async function openProject(path: string, warehouse?: string): Promise<void> {
  if (!inTauri()) throw new Error('opening a project is only in the app');
  return invoke<void>('open_project', { path, warehouse: warehouse?.trim() || null });
}

/** What `querysolo bucket check` says (decisions P1), from the shell or the core's route. */
export interface BucketCheck {
  prefix: string;
  ok: boolean;
  read: boolean;
  write: boolean;
  error: string | null;
  sentence: string;
  credentials: { configured: boolean; source: 'environment' | 'profile' | 'none'; profile: string | null; region: string; endpoint: string | null };
}

/** Decisions P1: the shell runs `querysolo bucket check <prefix> --json` (a window without
 *  a project has no core to ask; one with a core may ask it through `Api.checkBucket`),
 *  with the chosen AWS profile in its environment (C1). */
export async function checkBucket(prefix: string, profile?: string): Promise<BucketCheck> {
  if (!inTauri()) throw new Error('checking a bucket without a core is only in the app');
  return invoke<BucketCheck>('check_bucket', { prefix, profile: profile?.trim() || null });
}

/** Decisions C1: the profile names in this machine's `~/.aws/config` and `~/.aws/credentials`
 *  (names only; the shell reads nothing else). `default` first when there is one. */
export async function awsProfiles(): Promise<string[]> {
  return inTauri() ? invoke<string[]>('aws_profiles') : [];
}

/** The About row (ship brief S8): the app's version and where its `querysolo` came from. */
export interface About {
  version: string;
  sidecar: string;
  sidecar_source: 'bundled' | 'environment' | 'path';
}
export async function about(): Promise<About | null> {
  return inTauri() ? invoke<About>('about') : null;
}

/** Decisions C1: the profile this window's project uses; null means the AWS default. */
export async function projectProfile(): Promise<string | null> {
  return inTauri() ? invoke<string | null>('project_profile') : null;
}

/** Decisions C1: set (or, with null, clear) this project's profile; the shell remembers it
 *  per machine and starts the core again with it, which arrives as a `restarted` event. */
export async function setProjectProfile(profile: string | null): Promise<void> {
  if (!inTauri()) throw new Error('a project\'s profile is kept by the app');
  return invoke<void>('set_project_profile', { profile: profile?.trim() || null });
}

/** Decisions P1: where a new project goes unless another folder is chosen. */
export async function defaultParent(): Promise<string | null> {
  return inTauri() ? invoke<string | null>('default_parent') : null;
}

/** Decisions P1: `parent/name` made and opened as a project (`querysolo init`, with
 *  `--warehouse` for a bucket, and the AWS profile it should use, C1). Resolves to the
 *  folder's path. */
export async function newProject(parent: string, name: string, warehouse?: string, profile?: string): Promise<string> {
  if (!inTauri()) throw new Error('creating a project is only in the app');
  return invoke<string>('new_project', { parent, name, warehouse: warehouse?.trim() || null, profile: profile?.trim() || null });
}

/** A11: after two exits in a minute the shell stops restarting; this asks it to try again. */
export async function restartSidecar(): Promise<void> {
  if (!inTauri()) throw new Error('restarting the core is only in the app');
  return invoke<void>('restart_sidecar');
}

/** The native file dialog, many files allowed; [] when cancelled. Only the app has one. */
export async function pickFiles(): Promise<string[]> {
  if (!inTauri()) throw new Error('the file dialog is only in the app; in a browser, type the path');
  return invoke<string[]>('pick_files');
}

/** Paths dropped on the window (Tauri's drag-drop event, A9); nothing in a browser, where a
 *  drop has no path. `over` and `leave` drive the drop zone's highlight. */
export async function onDrop(handler: (e: { kind: 'over' | 'leave' | 'drop'; paths: string[] }) => void): Promise<() => void> {
  if (!inTauri()) return () => {};
  const { getCurrentWebview } = await import('@tauri-apps/api/webview');
  return getCurrentWebview().onDragDropEvent((event) => {
    const p = event.payload;
    if (p.type === 'drop') handler({ kind: 'drop', paths: p.paths });
    else if (p.type === 'leave') handler({ kind: 'leave', paths: [] });
    else handler({ kind: 'over', paths: 'paths' in p ? p.paths : [] });
  });
}

/** The shell's `sidecar` events for this window only. The shell emits them to a window
 *  by label; the global `listen` of `@tauri-apps/api/event` hears events sent to any
 *  target, so a second window's "ready" reached the first and put the second project's
 *  session, health and tables into it (Hants, 2026-09-21: a window titled querysolo-demo
 *  showing querysolo-second). Listening on the current webview window keeps them apart. */
export async function onSidecarEvent(handler: (e: SidecarEvent) => void): Promise<() => void> {
  if (!inTauri()) return () => {};
  const { getCurrentWebviewWindow } = await import('@tauri-apps/api/webviewWindow');
  return getCurrentWebviewWindow().listen<SidecarEvent>('sidecar', (e) => handler(e.payload));
}
