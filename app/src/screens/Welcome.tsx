// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The window before it has a project (app brief A10): a new project (decisions P1: a name,
// where its tables go), open a folder, or one of the recent ten. A folder that is not a
// project yet is initialised by the shell; the terminal equivalent is shown beside the
// button, as every action in the app is.

import type { RecentProject } from '../lib/session';

export interface WelcomeProps {
  recent: RecentProject[];
  /** True inside the app; a browser has no folder dialog and says so. */
  canPick: boolean;
  busy?: string;
  error?: string;
  /** The New project dialog (P1). */
  onNew: () => void;
  /** The folder dialog, then `querysolo init` for a folder that is not a project yet. */
  onPick: () => void;
  onOpen: (path: string) => void;
}

/** An `s3://bucket/prefix`, the only warehouse `init` takes besides its own folder. */
export const isBucketPrefix = (s: string): boolean => /^s3:\/\/[^/\s]+\/\S+$/.test(s.trim());

export function Welcome({ recent, canPick, busy, error, onNew, onPick, onOpen }: WelcomeProps) {
  return (
    <section className="welcome" data-testid="welcome">
      <h1>A lakehouse is a folder</h1>
      <p className="muted">
        QuerySolo keeps its catalog and tables inside it, next to your files. Make a new one, or open any folder: one that is
        not a project yet is set up first, which is <code>querysolo init &lt;folder&gt;</code> in a terminal.
      </p>
      <div className="actions">
        <button type="button" className="primary" onClick={onNew} disabled={!!busy} data-testid="new-project-button">
          New project…
        </button>
        <button type="button" className="quiet" onClick={onPick} disabled={!canPick || !!busy} data-testid="open-folder">
          Open a folder…
        </button>
        {busy && <span className="muted" data-testid="busy">{busy}</span>}
      </div>
      {!canPick && (
        <p className="muted hint" data-testid="hint">
          In a browser there is no folder dialog. In development, export <code>QUERYSOLO_SIDECAR</code> (the <code>querysolo</code> executable,
          for example <code>core/.venv/bin/querysolo</code>) and run <code>npm run tauri dev</code>; or start <code>querysolo serve</code> yourself
          and open <code>/?port=&amp;token=</code> from its <code>serve.json</code>.
        </p>
      )}
      {error && (
        <div className="error" data-testid="open-error">
          <b>That folder could not be opened.</b>
          <pre>{error}</pre>
        </div>
      )}
      {recent.length > 0 && (
        <div className="recent" data-testid="recent">
          <h2>Recent</h2>
          <ul>
            {recent.map((p) => (
              <li key={p.path}>
                <button type="button" onClick={() => onOpen(p.path)} disabled={!!busy}>
                  <b>{p.name}</b>
                  <span className="mono">{p.path}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
