// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The window (app brief steps 0 to 2): the welcome screen when it has no project, else the
// project with its own sidecar: the bar (the status dot, Open…, the mode and theme
// switches, Settings), the sidebar with the five screens and the explorer (decisions U2),
// the screen itself — Tables is the query workspace (U1), then Models, Lineage, Changes,
// Gauge — and the status strip along the bottom (what health says, the time the core took
// to be ready).

import { Suspense, lazy, useCallback, useEffect, useMemo, useState } from 'react';
import { Api, type Health, type TableInfo } from './lib/api';
import {
  about, awsProfiles, checkBucket, defaultParent, getSession, inTauri, newProject, onSidecarEvent, openProject, pickFolder, projectProfile, recentProjects, restartSidecar,
  setProjectProfile, windowProject, type About, type RecentProject, type Session,
} from './lib/session';
import { Explorer } from './components/Explorer';
import { NewProject } from './components/NewProject';
import { OpenMenu } from './components/OpenMenu';
import { SettingsPanel } from './components/SettingsPanel';
import { Sidebar, screenForKey, type Screen } from './components/Sidebar';
import { StatusDot, type Status } from './components/StatusDot';
import { loadMode, saveMode, type Mode } from './lib/vocabulary';
import { applyTheme, loadTheme, saveTheme, THEMES, themeLabel, type Theme } from './lib/theme';
import { useTables } from './lib/useTables';
const Gauge = lazy(() => import('./screens/Gauge').then((m) => ({ default: m.Gauge })));
const Models = lazy(() => import('./screens/Models').then((m) => ({ default: m.Models })));
const Lineage = lazy(() => import('./screens/Lineage').then((m) => ({ default: m.Lineage })));
const Changes = lazy(() => import('./screens/Changes').then((m) => ({ default: m.Changes })));
import { Tables } from './screens/Tables';
import { Welcome } from './screens/Welcome';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e)); // Tauri rejects with a string

const baseName = (path: string) => path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? path;

export default function App() {
  const [project, setProject] = useState<string | null>();
  const [recent, setRecent] = useState<RecentProject[]>([]);
  const [busy, setBusy] = useState<string>();
  const [openError, setOpenError] = useState<string>();
  const [status, setStatus] = useState<Status>('starting');
  const [detail, setDetail] = useState<string>();
  const [session, setSession] = useState<Session>();
  const [health, setHealth] = useState<Health>();
  const [screen, setScreen] = useState<Screen>('tables');
  // G8: a lineage link crosses screens — a table's detail from the Models screen, a model
  // from the Tables screen; the Models screen reads the name once and clears it, a table's
  // detail is the window's (`work`, below).
  const [openModel, setOpenModel] = useState<string>();
  const followModel = (name: string) => { setOpenModel(name); setScreen('models'); };
  // Q1: a question's answer — the Tables screen with `select * from <name>` run.
  const [arrive, setArrive] = useState<string>();
  const showAnswer = (name: string) => { setArrive(`select * from ${name}`); setScreen('tables'); };
  // L2: a detail's Recent strip opens the Changes screen filtered to that name.
  const [changesName, setChangesName] = useState<string>();
  const followChanges = (name: string) => { setChangesName(name); setScreen('changes'); };
  // Screen 8: Simple or Technical, one switch for the window, remembered.
  const [mode, setModeState] = useState<Mode>(loadMode);
  const setMode = (m: Mode) => { saveMode(m); setModeState(m); };
  // Light and dark (D1): the palette is CSS; this only says which of the three is in force.
  const [theme, setThemeState] = useState<Theme>(loadTheme);
  const setTheme = (t: Theme) => { saveTheme(t); applyTheme(t); setThemeState(t); };
  useEffect(() => { applyTheme(theme); }, [theme]);
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [error, setError] = useState<string>();
  const [settingsOpen, setSettingsOpen] = useState(false);
  // C1: the Bucket row in settings is the shell's — the profiles on this machine and the
  // project's choice — so it exists only inside the app.
  const [bucketSetting, setBucketSetting] = useState<{ profiles: string[]; profile: string | null }>();
  const [aboutInfo, setAboutInfo] = useState<About | null>();
  useEffect(() => {
    if (!settingsOpen || !inTauri()) return;
    Promise.all([awsProfiles(), projectProfile()]).then(([profiles, profile]) => setBucketSetting({ profiles, profile })).catch(() => setBucketSetting(undefined));
    about().then(setAboutInfo).catch(() => setAboutInfo(null));
  }, [settingsOpen]);
  const bucket = bucketSetting && {
    ...bucketSetting,
    onProfile: async (profile: string | null) => { await setProjectProfile(profile); setBucketSetting((b) => b && { ...b, profile }); },
  };
  const api = useMemo(() => (session ? new Api(session) : undefined), [session]);

  async function load(s: Session) {
    const api = new Api(s);
    const [h, t] = await Promise.all([api.health(), api.tables()]);
    setHealth(h);
    setTables(t);
    setStatus((prev) => (prev === 'restarted' ? prev : 'ready'));
  }

  const refreshTables = useCallback(async () => {
    if (session) setTables(await new Api(session).tables());
  }, [session]);
  const refreshHealth = useCallback(async () => {
    if (session) setHealth(await new Api(session).health());
  }, [session]);
  // The tables' verbs and what they show (U1, U2): the explorer in the sidebar starts them
  // from any screen; the Tables screen shows the preview or the detail.
  const showTables = useCallback(() => setScreen('tables'), []);
  const work = useTables({ session: status === 'down' ? undefined : session, tables, mode, onChanged: refreshTables, onRelocated: refreshHealth, onShow: showTables });
  const followTable = (name: string) => void work.open(name);

  // Which project this window has; asked again after opening one into this window.
  const refreshProject = useCallback(async () => {
    const [p, r] = await Promise.all([windowProject(), recentProjects()]);
    setRecent(r);
    setProject(p);
  }, []);

  useEffect(() => {
    refreshProject().catch((e: unknown) => { setProject(null); setOpenError(message(e)); });
  }, [refreshProject]);

  // With a project: the session (the shell waits for the sidecar), then health and tables.
  useEffect(() => {
    if (project == null) return;
    let cancelled = false;
    setStatus('starting');
    setError(undefined);
    getSession()
      .then((s) => {
        if (cancelled) return;
        setSession(s);
        return load(s);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setStatus('down');
        setError(message(e));
      });
    const off = onSidecarEvent((e) => {
      if (e.kind === 'down') {
        // a sidecar killed from outside says nothing on stderr; the panel still needs a line
        const why = e.stderr.trim() || 'The core exited twice within a minute and printed nothing on its stderr.';
        setStatus('down');
        setDetail(why);
        setError(why);
      } else {
        if (e.kind === 'restarted') setStatus('restarted');
        setSession(e.session);
        load(e.session).catch((err: unknown) => setError(message(err)));
      }
    });
    return () => {
      cancelled = true;
      off.then((f) => f());
    };
  }, [project]);

  // A10: the dialog, then the shell opens the folder here (no project yet) or in a new window.
  async function open(path?: string) {
    setOpenError(undefined);
    try {
      const folder = path ?? (await pickFolder());
      if (!folder) return;
      setBusy(`opening ${baseName(folder)}…`);
      await openProject(folder);
      await refreshProject();
    } catch (e: unknown) {
      setOpenError(message(e));
    } finally {
      setBusy(undefined);
    }
  }

  // P1: New project… — the dialog, its default parent from the shell, the bucket check
  // through the shell with the chosen AWS profile (C1; a browser asks its core), and the
  // folder made and opened here or in a new window.
  const [newOpen, setNewOpen] = useState(false);
  const [parent, setParent] = useState<string | null>();
  const [profiles, setProfiles] = useState<string[]>();
  useEffect(() => {
    if (!newOpen || parent !== undefined) return;
    defaultParent().then(setParent).catch(() => setParent(null));
    if (inTauri()) awsProfiles().then(setProfiles).catch(() => setProfiles([]));
  }, [newOpen, parent]);
  async function create(parentFolder: string, name: string, warehouse?: string, profile?: string) {
    setOpenError(undefined);
    setBusy(`making ${name}…`);
    try {
      await newProject(parentFolder, name, warehouse, profile);
      setNewOpen(false);
      await refreshProject();
    } finally {
      setBusy(undefined);
    }
  }

  // F0.8.6 and the settings key: ⌘/Ctrl+, opens settings, Esc closes it, ⌘/Ctrl+K goes to
  // the SQL box (the ask box's key, reserved for it); ⌘/Ctrl+1…5 are the screens (U2);
  // ⌘/Ctrl+N is New project… (P1).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey;
      const target = screenForKey(e);
      if (mod && e.key === ',') { e.preventDefault(); setSettingsOpen((o) => !o); }
      else if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); (document.querySelector('.cm-content') as HTMLElement | null)?.focus(); }
      else if (mod && e.key.toLowerCase() === 'n' && !e.shiftKey) { e.preventDefault(); setNewOpen(true); }
      else if (target) { e.preventDefault(); setScreen(target); }
      else if (e.key === 'Escape') setSettingsOpen(false);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  async function restart() {
    setError(undefined);
    setStatus('starting');
    try {
      await restartSidecar();
      const s = await getSession();
      setSession(s);
      await load(s);
    } catch (e: unknown) {
      setStatus('down');
      setError(message(e));
    }
  }

  if (project === undefined) return <div className="app" />; // the first paint, before the shell answers

  return (
    <div className="app">
      <header className="bar">
        <span className="wordmark" data-testid="wordmark">
          {/* the site's mark (web/src/components/Brand.astro), in the brand colour */}
          <svg width="22" height="18" viewBox="0 0 33 27" aria-hidden="true" fill="none"><path d="M2 16C7 11 10 11 15 16C20 21 24 21 31 14M2 23C7 18 10 18 15 23C20 28 24 27 31 21" stroke="currentColor" strokeWidth="2.5" /><path d="M10 7c2-6 9-7 12-1-3 6-9 7-12 1Z" fill="currentColor" /><path d="m11 7-5-4v8Z" fill="currentColor" /></svg>
          querysolo
        </span>
        <span className="project" data-testid="project">{health?.project ?? (project ? baseName(project) : '')}</span>
        {project !== null && <StatusDot status={status} detail={detail} />}
        {inTauri() && project !== null && (
          <OpenMenu recent={recent} current={project} disabled={!!busy} onOpen={(p) => open(p)} onPick={() => open()} onNew={() => setNewOpen(true)} />
        )}
        {api && (
          <nav className="screens mode" aria-label="Mode" data-testid="mode" title="Simple mode says question and check; Technical says model, test and the command.">
            <button type="button" className={mode === 'simple' ? 'on' : ''} onClick={() => setMode('simple')} aria-pressed={mode === 'simple'} data-testid="mode-simple">Simple</button>
            <button type="button" className={mode === 'technical' ? 'on' : ''} onClick={() => setMode('technical')} aria-pressed={mode === 'technical'} data-testid="mode-technical">Technical</button>
          </nav>
        )}
        <nav className="screens theme" aria-label="Theme" data-testid="theme" title="System follows this machine; Light and Dark override it for this window.">
          {THEMES.map((t) => (
            <button key={t} type="button" className={theme === t ? 'on' : ''} onClick={() => setTheme(t)} aria-pressed={theme === t} data-testid={`theme-${t}`}>{themeLabel[t]}</button>
          ))}
        </nav>
        {api && (
          <button type="button" className="quiet" onClick={() => setSettingsOpen((o) => !o)} aria-pressed={settingsOpen} title="Settings (⌘/Ctrl+,)" data-testid="settings-button">Settings</button>
        )}
      </header>
      {project === null ? (
        <main className="alone">
          <Welcome recent={recent} canPick={inTauri()} busy={busy} error={openError} onNew={() => setNewOpen(true)} onPick={() => open()} onOpen={(p) => open(p)} />
        </main>
      ) : (
        <div className="body">
          {api && (
            <Sidebar screen={screen} mode={mode} onScreen={(s) => { if (s === 'changes') setChangesName(undefined); setScreen(s); }}>
              <Explorer
                tables={tables}
                busy={work.busy}
                native={inTauri()}
                over={work.over}
                aws={health?.aws}
                onPaths={(p, anonymous) => void work.preview(p, anonymous)}
                onChoose={() => void work.choose()}
                onRefresh={(name) => void work.refresh(name)}
                onOpen={followTable}
                open={screen === 'tables' ? work.detail?.table.name : undefined}
              />
            </Sidebar>
          )}
          <main className={screen === 'tables' ? 'workspace-host' : undefined}>
            {openError && <section className="error" data-testid="open-error"><b>That folder could not be opened.</b><pre>{openError}</pre></section>}
            {error && (
              <section className="error" data-testid="error">
                <b>{status === 'down' && session ? 'The core stopped.' : 'The core did not start.'}</b>
                <pre>{error}</pre>
                {inTauri() && <p><button type="button" className="primary" onClick={() => void restart()} data-testid="restart">Restart the core</button></p>}
                <p>
                  In development, export <code>QUERYSOLO_SIDECAR</code> (the <code>querysolo</code> executable, for example <code>core/.venv/bin/querysolo</code>)
                  before <code>npm run tauri dev</code>; <code>QUERYSOLO_PROJECT</code> names the folder to open.
                </p>
              </section>
            )}
            {session?.initialised && (
              <section className="notice" data-testid="initialised">
                <b>Set up {baseName(session.project)} as a lakehouse.</b>
                <pre>{session.initialised}</pre>
              </section>
            )}
            {session && status !== 'down' && screen === 'models' && (
              <Suspense fallback={<section className="models-screen" data-testid="models-loading" />}>
                <Models session={session} mode={mode} tables={tables} onChanged={refreshTables} select={openModel} onSelected={() => setOpenModel(undefined)} onOpenTable={followTable} onAnswer={showAnswer} onOpenChanges={followChanges} />
              </Suspense>
            )}
            {session && status !== 'down' && screen === 'lineage' && (
              <Suspense fallback={<section className="lineage-screen" data-testid="lineage-loading" />}>
                <Lineage session={session} mode={mode} onOpenModel={followModel} onOpenTable={followTable} refreshKey={tables.map((t) => `${t.name}:${t.freshness ?? ''}`).join('|')} />
              </Suspense>
            )}
            {session && status !== 'down' && screen === 'changes' && (
              <Suspense fallback={<section className="changes-screen" data-testid="changes-loading" />}>
                <Changes session={session} mode={mode} name={changesName} onOpenModel={followModel} onOpenTable={followTable} refreshKey={tables.map((t) => `${t.name}:${t.freshness ?? ''}`).join('|')} />
              </Suspense>
            )}
            {session && status !== 'down' && screen === 'gauge' && (
              <Suspense fallback={<section className="gauge-screen" data-testid="gauge-loading" />}>
                <Gauge session={session} health={health} onHealthChanged={refreshHealth} />
              </Suspense>
            )}
            {session && status !== 'down' && screen === 'tables' && (
              <Tables session={session} tables={tables} work={work} movedFrom={health?.moved_from} mode={mode} onDone={() => void refreshTables()} onOpenModel={followModel} onOpenChanges={followChanges} arrive={arrive} onArrived={() => setArrive(undefined)} />
            )}
          </main>
        </div>
      )}
      {settingsOpen && project !== null && (
        // a dialog over the window, like New project…: the workspace owns the height, so a
        // panel in the column would be cut off at the bottom
        <div className="modal" onMouseDown={(e) => { if (e.target === e.currentTarget) setSettingsOpen(false); }}>
          {api && status !== 'down' ? (
            <SettingsPanel api={api} bucket={bucket} about={aboutInfo} onClose={() => setSettingsOpen(false)} />
          ) : (
            <section className="settings" data-testid="settings"><header><h2>Settings</h2><button type="button" className="quiet" onClick={() => setSettingsOpen(false)}>Close (Esc)</button></header><p className="muted">The core is not running; settings are read and written through it. Restart it first.</p></section>
          )}
        </div>
      )}
      {newOpen && (
        <NewProject
          canCreate={inTauri()}
          defaultParent={parent}
          aws={health?.aws}
          profiles={profiles}
          onChooseParent={pickFolder}
          check={(prefix, profile) => (inTauri() ? checkBucket(prefix, profile) : api && status !== 'down' ? api.checkBucket(prefix) : checkBucket(prefix))}
          onCreate={create}
          onClose={() => setNewOpen(false)}
        />
      )}
      {project !== null && health && (
        <footer className="strip" data-testid="health">
          <div><b>{health.querysolo}</b><span>querysolo</span></div>
          <div><b>{health.duckdb}</b><span>DuckDB</span></div>
          <div><b>{health.machine.memory_limit_text ?? '—'}</b><span>memory limit, this window</span></div>
          <div title={health.throughput_probe === 'cached' ? 'Measured through the page cache and capped; run `querysolo gauge probe` in the project to measure the disk.' : undefined}>
            <b>{health.throughput_local_mbps ? `${Math.round(health.throughput_local_mbps).toLocaleString()} MB/s` : '—'}</b>
            <span>{health.throughput_probe === 'cached' ? 'local disk (cached; run querysolo gauge probe)' : 'local disk'}</span>
          </div>
          <div data-testid="ready-ms"><b>{session?.ready_ms ? `${session.ready_ms} ms` : '—'}</b><span>core ready in</span></div>
        </footer>
      )}
    </div>
  );
}
