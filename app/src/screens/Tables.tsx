// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The Tables screen, a query workspace since decisions U1: the editor, the verdict and
// the rows (screen 2) stacked with a draggable split, and in the results pane's place a
// table's detail or a dropped file's preview (screen 1) when the explorer in the sidebar
// opened one. The verbs behind them are the window's (`lib/useTables.ts`).

import { Suspense, lazy, useCallback } from 'react';
import type { TableInfo } from '../lib/api';
import { relocateCommand } from '../lib/command';
import type { Session } from '../lib/session';
import type { TablesWork } from '../lib/useTables';
import type { Mode } from '../lib/vocabulary';
import { Command } from '../components/Command';
import { PreviewPanel } from '../components/PreviewPanel';
import { Split } from '../components/Split';
import { TableDetail } from '../components/TableDetail';
// Screen 2 carries Arrow and CodeMirror; loaded once there is a table to ask, so the first
// paint (the launch budget, §3.2) does not wait for them.
const Query = lazy(() => import('./Query').then((m) => ({ default: m.Query })));

export interface TablesProps {
  session: Session;
  tables: TableInfo[];
  work: TablesWork;
  /** The folder this project's tables were written in, when it is not this one (T5). */
  movedFrom?: string | null;
  mode: Mode;
  /** After a run: a statement may have written a table (the list and an open detail re-read). */
  onDone: () => void;
  /** A lineage link named a model that is not in the catalog yet: the Models screen opens it. */
  onOpenModel?: (name: string) => void;
  /** A detail's Recent strip (L2): the Changes screen, filtered to that name. */
  onOpenChanges?: (name: string) => void;
  /** SQL to run on arrival (Q1), and the word that it was taken. */
  arrive?: string;
  onArrived?: () => void;
}

export function Tables({ session, tables, work, movedFrom, mode, onDone, onOpenModel, onOpenChanges, arrive, onArrived }: TablesProps) {
  const { busy, dropError, pending, done, detail } = work;

  // Run shows rows: whatever sat in their place goes (a detail; a preview not yet imported).
  const clearPanel = useCallback(() => { work.setDetail(undefined); work.setPending(undefined); }, [work.setDetail, work.setPending]); // eslint-disable-line react-hooks/exhaustive-deps

  function follow(name: string, kind: 'table' | 'view' | 'model') {
    if (kind === 'model' && onOpenModel) onOpenModel(name);
    else void work.open(name);
  }

  // What sits in the results pane's place: the detail, else the preview, else nothing (the rows).
  const panel = detail ? (
    <TableDetail
      table={detail.table}
      sample={detail.sample}
      mode={mode}
      busy={busy}
      error={detail.error}
      onSample={() => void work.sample()}
      onExpire={() => void work.expire()}
      onRefresh={() => void work.refresh(detail.table.name)}
      onReattach={() => detail.table.source && void work.reattach(detail.table.name, detail.table.source, !!detail.table.public)}
      onClose={() => work.setDetail(undefined)}
      session={session}
      onOpen={follow}
      onRunStale={() => void work.runStale()}
      onPublish={(prefix, dryRun, yes) => work.publish(detail.table.name, prefix, dryRun, yes)}
      onChanges={onOpenChanges}
    />
  ) : pending ? (
    <PreviewPanel
      path={pending.path}
      folder={pending.folder}
      previews={pending.previews}
      name={pending.name}
      mode={pending.mode}
      exists={pending.exists}
      error={pending.error}
      busy={busy}
      onName={(name) => work.setPending({ ...pending, name, exists: undefined, error: undefined })}
      onImport={(mode) => void work.doImport(mode)}
      onAttach={() => void work.attach()}
      onCancel={() => work.setPending(undefined)}
    />
  ) : undefined;

  const notices = (
    <>
      {done && (
        <section className="notice" data-testid="imported">
          <b>{done.text}</b>
          <Command line={done.line} />
        </section>
      )}
      {dropError && <section className="error" data-testid="drop-error"><pre>{dropError}</pre></section>}
    </>
  );

  return (
    <section className="workspace" data-testid="workspace">
      {movedFrom && (
        <section className="error" data-testid="moved">
          <b>{mode === 'simple' ? 'This project was moved.' : `This project was moved from ${movedFrom}.`}</b>
          <p>
            {tables.filter((t) => t.needs_relocate).length} {tables.filter((t) => t.needs_relocate).length === 1 ? 'table points' : 'tables point'} at the old folder.
            {mode === 'simple' ? ' Relocate updates them; nothing is copied.' : ' Every snapshot is kept; the old metadata files are orphans for expire.'}
          </p>
          <div className="actions">
            <button type="button" className="primary" disabled={!!busy} data-testid="relocate" onClick={() => void work.relocate()}>{busy ?? 'Relocate'}</button>
            <Command line={relocateCommand()} />
          </div>
        </section>
      )}
      {tables.length > 0 ? (
        <Suspense fallback={<section className="query" data-testid="query-loading" />}>
          <Query session={session} tables={tables} mode={mode} onDone={onDone} panel={panel} notices={notices} onRun={clearPanel} arrive={arrive} onArrived={onArrived} />
        </Suspense>
      ) : (
        <Split
          top={<p className="muted empty" data-testid="no-tables">No tables yet: drop a file on the sidebar, or run <code>querysolo import &lt;file&gt;</code>. The SQL box opens with the first table.</p>}
          bottom={<>{notices}{panel}</>}
        />
      )}
    </section>
  );
}
