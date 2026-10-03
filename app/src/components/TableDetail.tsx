// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// A table's detail (real-data brief R7): `describe` as a panel, with the columns, where the
// data is, partitioning, the snapshot list, what `expire` would reclaim at the project's
// retention, and three buttons that are three CLI verbs: sample, expire, refresh. A view
// (real-data R6, step 6) has its own shape: its query, its columns, its version, the dbt
// model it came from and that `querysolo run` rebuilds it; no snapshots, nothing to expire.

import { useState } from 'react';
import { ago, humanBytes, type LineageEdge, type PublishReport, type TableDescription } from '../lib/api';
import { attachCommand, describeCommand, expireCommand, publishCommand, refreshCommand, runCommand, sampleCommand } from '../lib/command';
import type { Session } from '../lib/session';
import { words, type Mode } from '../lib/vocabulary';
import { Command } from './Command';
import { LineageRows } from './Lineage';
import { Recent } from './Recent';

export interface TableDetailProps {
  table: TableDescription;
  sample?: Record<string, unknown>[];
  /** Screen 8: a view's words. Technical by default. */
  mode?: Mode;
  busy?: string;
  error?: string;
  onSample: () => void;
  onExpire: () => void;
  onRefresh: () => void;
  /** `querysolo tables attach --replace`: register the prefix again after its files changed (T2). */
  onReattach?: () => void;
  onClose: () => void;
  /** The lineage lines (G8) are read through the API when a session is given; a name
   *  clicked opens that detail (a table or view here, a model on the Models screen). */
  session?: Session;
  onOpen?: (name: string, kind: LineageEdge['kind']) => void;
  /** `querysolo run --stale` from here (L3): a snapshot made models out of date. */
  onRunStale?: () => void;
  /** `querysolo tables publish` (W2): weigh (a dry run) and move a local table into a bucket;
   *  each resolves to the report or rejects with the core's sentence. */
  onPublish?: (prefix: string, dryRun: boolean, yes: boolean) => Promise<PublishReport>;
  /** The Recent strip's link (L2): the Changes screen, filtered to this name. */
  onChanges?: (name: string) => void;
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** The publish box (W2): a prefix, Weigh it (a dry run with the bandwidth sentence), Publish;
 *  a refusal over the cap offers Publish anyway (`--yes`). */
function PublishBox({ name, mode, busy, onPublish }: { name: string; mode: Mode; busy?: string; onPublish: NonNullable<TableDetailProps['onPublish']> }) {
  const [open, setOpen] = useState(false);
  const [prefix, setPrefix] = useState('');
  const [weighed, setWeighed] = useState<PublishReport>();
  const [error, setError] = useState<string>();
  const [working, setWorking] = useState(false);
  const run = async (dryRun: boolean, yes: boolean) => {
    setWorking(true);
    setError(undefined);
    try {
      const r = await onPublish(prefix.trim(), dryRun, yes);
      if (dryRun) setWeighed(r);
      else { setOpen(false); setWeighed(undefined); }
    } catch (e: unknown) {
      setError(message(e));
    } finally {
      setWorking(false);
    }
  };
  if (!open) return <button type="button" className="quiet" disabled={!!busy} data-testid="publish-open" onClick={() => setOpen(true)}>{mode === 'simple' ? 'Move to a bucket…' : 'Publish to a bucket…'}</button>;
  const ok = /^s3:\/\/[^/]+\/.+/.test(prefix.trim());
  const overCap = error?.includes('over the cap');
  return (
    <div className="publish" data-testid="publish-box">
      <p>
        {mode === 'simple'
          ? `Move ${name} into a bucket, with its whole history; other tools and machines can read it there.`
          : `Move ${name} into a bucket, every snapshot kept: its files are copied under the prefix, the metadata rewritten there, the catalog moved in one commit; the local files are orphans for expire.`}
      </p>
      <div className="path">
        <input type="text" value={prefix} placeholder="s3://bucket/prefix" spellCheck={false} data-testid="publish-prefix" onChange={(e) => { setPrefix(e.target.value); setWeighed(undefined); setError(undefined); }} />
        <button type="button" className="quiet" disabled={!ok || working || !!busy} data-testid="publish-weigh" onClick={() => void run(true, false)}>Weigh it</button>
        <button type="button" className="primary" disabled={!ok || working || !!busy} data-testid="publish-go" onClick={() => void run(false, false)}>{working ? 'working…' : 'Publish'}</button>
        <button type="button" className="quiet" disabled={working} onClick={() => setOpen(false)}>Cancel</button>
      </div>
      {weighed && (
        <p className="muted" data-testid="publish-weighed">
          {weighed.files} {weighed.files === 1 ? 'file' : 'files'}, {humanBytes(weighed.bytes)} to copy to <span className="mono">{weighed.target}</span>{weighed.seconds !== null ? `, about ${Math.max(1, Math.round(weighed.seconds))} s at the measured bandwidth` : ''}.
        </p>
      )}
      {error && (
        <div className="error" data-testid="publish-error">
          <pre>{error}</pre>
          {overCap && <button type="button" className="quiet" disabled={working} data-testid="publish-anyway" onClick={() => void run(false, true)}>Publish anyway</button>}
        </div>
      )}
      {ok && <Command line={publishCommand(name, prefix.trim(), { dryRun: !weighed && !error })} />}
    </div>
  );
}

const cell = (v: unknown) => (v === null || v === undefined ? '∅' : typeof v === 'object' ? JSON.stringify(v) : String(v));

function Where({ t }: { t: TableDescription }) {
  if (!t.source && t.location.startsWith('s3://')) return <span>in a bucket, the project's warehouse: <span className="mono">{t.location}</span></span>;
  if (!t.source) return <span>local, under the project's warehouse</span>;
  return <span>{t.public ? 'public bucket, read without credentials' : 'attached'}: <span className="mono">{t.source}</span></span>;
}

const DBT_MODEL = 'querysolo.dbt-model';

function SampleBlock({ t, sample }: { t: TableDescription; sample: Record<string, unknown>[] }) {
  return (
    <div data-testid="sample">
      <h3>First rows</h3>
      {sample.length === 0 ? <p className="muted">{t.kind === 'view' ? 'The view answers no rows right now.' : 'The table is empty.'}</p> : (
        <table className="sample">
          <thead><tr>{Object.keys(sample[0]).map((k) => <th key={k}>{k}</th>)}</tr></thead>
          <tbody>
            {sample.map((row, i) => <tr key={i}>{Object.values(row).map((v, j) => <td key={j} className="mono">{cell(v)}</td>)}</tr>)}
          </tbody>
        </table>
      )}
      <Command line={sampleCommand(t.name)} />
    </div>
  );
}

function ViewDetail({ table: t, sample, mode, busy, error, onSample, onClose, session, onOpen, onChanges }: TableDetailProps & { mode: Mode }) {
  const w = words(mode);
  const lineage = session && onOpen && <LineageRows session={session} name={t.name} mode={mode} onOpen={onOpen} refreshKey={t.freshness} />;
  const recent = session && <Recent session={session} name={t.name} mode={mode} onMore={onChanges} refreshKey={t.freshness} />;
  const modelId = t.properties?.[DBT_MODEL];
  const modelName = modelId ? modelId.split('.').pop() ?? modelId : undefined;
  return (
    <section className="preview detail view" data-testid="detail" data-kind="view">
      <header>
        <h2 className="mono">{t.name}<span className="muted"> · {mode === 'simple' ? 'a question, answered live' : 'view'} · {t.columns.length} columns</span></h2>
        <button type="button" className="quiet" onClick={onClose} disabled={!!busy}>Close</button>
      </header>
      <Command line={describeCommand(t.name)} />
      <pre className="sql" data-testid="view-sql">{t.view_sql}</pre>
      <dl className="facts">
        <dt>Where</dt><dd data-testid="detail-where">{mode === 'simple' ? 'not stored: the rows are computed from the tables each time it is asked' : <span>a view in the catalog; the rows are computed from its query each time</span>}</dd>
        <dt>Version</dt><dd data-testid="view-version" title={t.freshness ?? ''}>{t.snapshots} {t.snapshots === 1 ? 'version' : 'versions'} · this one {ago(t.freshness)}</dd>
        <dt>{mode === 'simple' ? 'Comes from' : 'Model'}</dt>
        <dd data-testid="view-model">
          {modelName ? (
            <span>
              {mode === 'simple' ? `the question ${modelName}` : <span className="mono">{modelId}</span>}; {mode === 'simple' ? 'refreshing it on the Questions screen' : <code>querysolo run {modelName}</code>} rewrites this view
            </span>
          ) : (
            <span className="muted">{mode === 'simple' ? 'not a saved question: a view put in the catalog directly' : 'not a dbt model: put in the catalog directly (the REST catalog, or the Python API)'}</span>
          )}
        </dd>
        {lineage}
        {recent}
      </dl>
      <table className="columns">
        <thead><tr><th>Column</th><th>Iceberg</th></tr></thead>
        <tbody>
          {t.columns.map(([name, type]) => (
            <tr key={name}><td className="mono">{name}</td><td className="mono muted">{type}</td></tr>
          ))}
        </tbody>
      </table>
      <p className="muted" data-testid="no-snapshots">A view has versions, not snapshots: nothing is stored for it, so there is nothing to expire.</p>
      {sample && <SampleBlock t={t} sample={sample} />}
      {error && <div className="error" data-testid="detail-error"><pre>{error}</pre></div>}
      <footer className="actions">
        <button type="button" className="quiet" onClick={onSample} disabled={!!busy} data-testid="sample-rows">Sample rows</button>
        {modelName && <Command line={runCommand([modelName])} label={`${w.runOne}: copy as command`} />}
      </footer>
    </section>
  );
}

/** What a snapshot did downstream (L3): the models whose last run predates it, as links. */
function Affects({ names, mode, onOpen }: { names: string[]; mode: Mode; onOpen?: TableDetailProps['onOpen'] }) {
  if (names.length === 0) return null;
  const w = words(mode);
  return (
    <span data-testid="affects">
      {mode === 'simple' ? `${names.length} ${names.length === 1 ? w.model : w.models} need refreshing because of this: ` : 'made out of date: '}
      {names.map((n, i) => (
        <span key={n}>
          {i > 0 && ', '}
          <button type="button" className="link mono" data-testid={`affects-${n}`} onClick={() => onOpen?.(n, 'model')}>{n}</button>
        </span>
      ))}
    </span>
  );
}

export function TableDetail(props: TableDetailProps) {
  const { table: t, sample, busy, error, onSample, onExpire, onRefresh, onReattach, onClose, session, onOpen, onRunStale, onPublish, onChanges } = props;
  const mode = props.mode ?? 'technical';
  const w = words(mode);
  const changed = t.changed_files ?? [];
  if (t.kind === 'view') return <ViewDetail {...props} mode={mode} />;
  const reclaimable = t.expirable_snapshots > 0;
  const affected = Array.from(new Set(t.snapshot_list.flatMap((s) => s.affects ?? [])));
  const lineage = session && onOpen && <LineageRows session={session} name={t.name} mode={props.mode ?? 'technical'} onOpen={onOpen} refreshKey={t.freshness} />;
  const recent = session && <Recent session={session} name={t.name} mode={mode} onMore={onChanges} refreshKey={t.freshness} />;
  return (
    <section className="preview detail" data-testid="detail">
      <header>
        <h2 className="mono">{t.name}<span className="muted"> · {t.rows.toLocaleString()} rows · {humanBytes(t.bytes)} · {t.columns.length} columns</span></h2>
        <button type="button" className="quiet" onClick={onClose} disabled={!!busy}>Close</button>
      </header>
      <Command line={describeCommand(t.name)} />
      <dl className="facts">
        <dt>Where</dt><dd data-testid="detail-where"><Where t={t} /></dd>
        <dt>Partitioning</dt><dd>{t.partitioning}</dd>
        <dt>Last written</dt><dd title={t.freshness ?? ''}>{ago(t.freshness)}{t.last_commit.operation ? ` (${t.last_commit.operation})` : ''}</dd>
        <dt>Format</dt><dd>Iceberg v{t.format_version}, {t.snapshots} {t.snapshots === 1 ? 'snapshot' : 'snapshots'}</dd>
        {lineage}
        {recent}
      </dl>
      <table className="columns">
        <thead><tr><th>Column</th><th>Iceberg</th></tr></thead>
        <tbody>
          {t.columns.map(([name, type]) => (
            <tr key={name}><td className="mono">{name}</td><td className="mono muted">{type}</td></tr>
          ))}
        </tbody>
      </table>
      <h3>Snapshots</h3>
      <table className="snapshots" data-testid="snapshots">
        <thead><tr><th>When</th><th>Operation</th><th>Rows added</th><th>Files added</th><th>Rows after</th><th></th></tr></thead>
        <tbody>
          {t.snapshot_list.map((s) => (
            <tr key={s.id} data-testid={`snapshot-${s.id}`} className={s.expirable ? 'expirable' : ''}>
              <td title={s.timestamp}>{ago(s.timestamp)}</td>
              <td>{s.operation ?? '—'}</td>
              <td>{s.added_rows !== null ? s.added_rows.toLocaleString() : s.deleted_rows ? `−${s.deleted_rows.toLocaleString()}` : '—'}</td>
              <td>{s.added_files === null ? '—' : s.added_files.toLocaleString()}</td>
              <td>{s.total_rows === null ? '—' : s.total_rows.toLocaleString()}</td>
              <td className="muted">{s.current ? 'current' : s.expirable ? 'expirable' : ''}{s.affects?.length ? <><br /><Affects names={s.affects} mode={mode} onOpen={onOpen} /></> : null}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {affected.length > 0 && onRunStale && (
        <div className="affected" data-testid="affected">
          <span className="state upstream">{mode === 'simple' ? `${affected.length} ${affected.length === 1 ? w.model : w.models} out of date because this table changed.` : `${affected.length} ${affected.length === 1 ? 'model is' : 'models are'} out of date because of these commits.`}</span>
          {' '}
          <button type="button" className="quiet" disabled={!!busy} data-testid="run-stale" onClick={onRunStale}>{w.runStale}</button>
          <Command line={runCommand([], { stale: true })} />
        </div>
      )}
      {t.source && (
        <p className={changed.length ? 'failed' : 'muted'} data-testid="files-verified">
          {t.verify_error
            ? `Files not verified: ${t.verify_error}`
            : changed.length
              ? `${changed.length} ${changed.length === 1 ? 'file' : 'files'} changed under the same path since the attach: ${changed.slice(0, 5).map(([uri, why]) => `${uri.split('/').pop()} (${why})`).join(', ')}${changed.length > 5 ? ' …' : ''}. The table's statistics no longer describe them; register the prefix again.`
              : `Files verified against the prefix ${ago(t.verified_at ?? null)}.`}
        </p>
      )}
      {t.local_copy_files ? (
        <p className="muted" data-testid="local-copy">
          {t.local_copy_files} {t.local_copy_files === 1 ? 'file' : 'files'} of the local copy still under the project's warehouse, until expire sweeps them.
        </p>
      ) : null}
      <p className="muted" data-testid="reclaimable">
        {t.source
          ? 'An attached table is never expired: its files are not QuerySolo\'s to delete.'
          : reclaimable
            ? `${t.expirable_snapshots} ${t.expirable_snapshots === 1 ? 'snapshot' : 'snapshots'} older than ${t.keep_days} days, ${humanBytes(t.reclaimable_bytes)} reclaimable.`
            : `Nothing to expire at the project's retention of ${t.keep_days} days.`}
      </p>
      {sample && <SampleBlock t={t} sample={sample} />}
      {error && <div className="error" data-testid="detail-error"><pre>{error}</pre></div>}
      <footer className="actions">
        <button type="button" className="quiet" onClick={onSample} disabled={!!busy} data-testid="sample-rows">Sample rows</button>
        {t.source && changed.length > 0 && onReattach ? (
          <button type="button" className="primary" onClick={onReattach} disabled={!!busy} data-testid="reattach">{busy ?? 'Register again'}</button>
        ) : t.source ? (
          <button type="button" className="primary" onClick={onRefresh} disabled={!!busy} data-testid="refresh">{busy ?? 'Refresh'}</button>
        ) : (
          <button type="button" className="primary" onClick={onExpire} disabled={!!busy || !reclaimable} data-testid="expire">{busy ?? 'Expire snapshots'}</button>
        )}
        <Command line={t.source ? (changed.length ? attachCommand(t.name, t.source, t.public, true) : refreshCommand(t.name)) : expireCommand(t.name)} />
        {!t.source && !t.location.startsWith('s3://') && onPublish && <PublishBox name={t.name} mode={mode} busy={busy} onPublish={onPublish} />}
      </footer>
    </section>
  );
}
