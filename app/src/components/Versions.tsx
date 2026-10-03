// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Screen 9 of the mockups on the model's own panel (versions brief G6): one model's history
// as `querysolo versions <name>` lists it, the selected version's diff, "Gauge then / now",
// and Restore this version, which is `querysolo restore <name> <id>` — a new version, never a
// rewrite. Technical shows the log with ids and the diff; Simple shows the same versions as
// sentences and the one button, with no git word on the screen.

import { useCallback, useEffect, useState } from 'react';
import { Api, ApiError, ago, type Estimate, type GitStatus, type PlannedModel, type Version } from '../lib/api';
import { restoreCommand } from '../lib/command';
import type { Session } from '../lib/session';
import { diffSummary, gitLine, parseDiff, versionSentence, authorName } from '../lib/versions';
import { verdictSentence, words, type Mode } from '../lib/vocabulary';
import { Command } from './Command';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export interface VersionsProps {
  session: Session;
  mode: Mode;
  /** The model whose history this is; its path says whether it is a question. */
  model: Pick<PlannedModel, 'name' | 'path' | 'verdict' | 'words' | 'reason' | 'error' | 'est_wall_local'>;
  /** After a restore: the SQL changed, so the plan is read again. */
  onRestored: () => Promise<void>;
}

/** "Gauge then" for one version: the estimate of its SQL when that SQL is plain, or the
 *  sentence saying why not — a model with `ref()` or `source()` needs a compile of an old
 *  file, which dbt does not offer without checking it out (G6). */
type Then = { estimate: Estimate } | { skipped: string } | undefined;

const NOT_MEASURED = 'not measured for a model with refs';

export function Versions({ session, mode, model, onRestored }: VersionsProps) {
  const api = new Api(session);
  const w = words(mode);
  const simple = mode === 'simple';
  const [versions, setVersions] = useState<Version[]>();
  const [empty, setEmpty] = useState<string>();
  const [error, setError] = useState<string>();
  const [selected, setSelected] = useState<string>();
  const [then, setThen] = useState<Then>();
  const [git, setGit] = useState<GitStatus>();
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string>();

  const load = useCallback(async (keep?: string) => {
    try {
      const list = await api.versions(model.name);
      setVersions(list);
      setEmpty(undefined);
      setSelected((s) => (keep && list.some((v) => v.id === keep) ? keep : s && list.some((v) => v.id === s) ? s : list[0]?.id));
    } catch (e: unknown) {
      setVersions([]);
      if (e instanceof ApiError && e.code === 'no_history') setEmpty(e.message);
      else setError(message(e));
    }
  }, [session.port, session.token, model.name]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    setVersions(undefined);
    setSelected(undefined);
    setNotice(undefined);
    setError(undefined);
    void load();
    if (!simple) api.git().then(setGit, () => setGit(undefined));
  }, [load, simple]); // eslint-disable-line react-hooks/exhaustive-deps

  // Gauge then: the selected version's SQL is fetched when the row is selected, and
  // estimated when it is plain SQL (a question always is).
  useEffect(() => {
    if (!selected) return;
    let live = true;
    setThen(undefined);
    (async () => {
      try {
        const { sql } = await api.versionSql(model.name, selected);
        if (/\{\{/.test(sql)) {
          if (live) setThen({ skipped: NOT_MEASURED });
          return;
        }
        const estimate = await api.estimate(sql);
        if (live) setThen({ estimate });
      } catch (e: unknown) {
        if (live) setThen({ skipped: `not measured: ${message(e)}` });
      }
    })();
    return () => { live = false; };
  }, [selected, model.name]); // eslint-disable-line react-hooks/exhaustive-deps

  async function restore() {
    if (!selected) return;
    setBusy(true);
    setNotice(undefined);
    setError(undefined);
    try {
      const r = await api.restore(model.name, selected);
      const from = versions?.find((v) => v.id === selected);
      if (!r.commit) {
        setNotice(simple ? 'This is already the current version.' : `Already the current version: nothing to restore.`);
      } else {
        setNotice(
          simple
            ? `Restored the version from ${from ? ago(from.when) : 'before'}.`
            : `Restored ${selected.slice(0, 7)} as version ${r.commit.slice(0, 7)}.${r.git ? ` git: ${r.git}` : ''}`,
        );
        await load(r.commit);
        await onRestored();
      }
    } catch (e: unknown) {
      setError(message(e));
    } finally {
      setBusy(false);
    }
  }

  const current = versions?.find((v) => v.id === selected);
  // Technical is the gauge line as the CLI prints it, "Runs here · reads 2.0 MB"; Simple is
  // the wait as a sentence, the way the card says it.
  const nowSentence = simple
    ? verdictSentence(model, 'simple')
    : model.error ? `not estimated: ${model.error}` : [model.words, model.reason].filter(Boolean).join(' · ') || '—';
  const thenSentence = !then
    ? '…'
    : 'skipped' in then
      ? then.skipped
      : simple
        ? verdictSentence({ verdict: then.estimate.verdict, words: then.estimate.words, reason: then.estimate.reason, error: null, est_wall_local: then.estimate.wall_local }, 'simple')
        : `${then.estimate.words} · ${then.estimate.reason}`;

  const gauge = current && (
    <dl className="facts gauge-then" data-testid="gauge-then-now">
      <dt>{simple ? 'Then' : 'Gauge then'}</dt>
      <dd data-testid="gauge-then">{thenSentence}</dd>
      <dt>{simple ? 'Now' : 'Gauge now'}</dt>
      <dd data-testid="gauge-now">{nowSentence}</dd>
    </dl>
  );

  const restoreButton = current && (
    <button type="button" className="quiet" disabled={busy} data-testid="restore" onClick={() => void restore()}>
      {busy ? 'restoring…' : 'Restore this version'}
    </button>
  );

  const noticeLine = notice && <p className="notice" data-testid="restored">{notice}</p>;
  const errorLine = error && <p className="failed" data-testid="versions-error">{error}</p>;

  if (simple) {
    return (
      <section className="versions simple" data-testid="versions" data-mode="simple">
        <h4>{w.versions}{versions && versions.length > 0 && <span className="muted"> · {versions.length}</span>}</h4>
        {empty && <p className="muted" data-testid="no-versions">No history yet: the next save records the first version.</p>}
        {versions && versions.length > 0 && (
          <ul className="version-list" data-testid="version-list">
            {versions.map((v, i) => (
              <li key={v.id} className={v.id === selected ? 'on' : ''} data-testid={`version-${i}`} onClick={() => setSelected(v.id)}>
                <span className="sentence">{versionSentence(v, mode)}</span>
                {v.checks_changed && <span className="muted"> · {w.tests} changed</span>}
              </li>
            ))}
          </ul>
        )}
        {gauge}
        {current && <footer className="actions">{restoreButton}</footer>}
        {noticeLine}
        {errorLine}
      </section>
    );
  }

  return (
    <section className="versions" data-testid="versions" data-mode="technical">
      <h4>{w.versions}{versions && versions.length > 0 && <span className="muted"> · {versions.length}</span>}</h4>
      {git && <p className="muted mono git-line" data-testid="git-line">{gitLine(git)}</p>}
      {empty && <p className="muted" data-testid="no-versions">{empty}</p>}
      {versions && versions.length > 0 && (
        <table className="version-list" data-testid="version-list">
          <thead><tr><th>Version</th><th>When</th><th>Who</th><th>What</th><th>Checks</th></tr></thead>
          <tbody>
            {versions.map((v, i) => (
              <tr key={v.id} className={v.id === selected ? 'on' : ''} data-testid={`version-${i}`} onClick={() => setSelected(v.id)}>
                <td className="mono">{v.id.slice(0, 7)}</td>
                <td className="muted" title={v.when}>{ago(v.when)}</td>
                <td>{authorName(v.author)}</td>
                <td>{v.message}{!v.sql_changed && <span className="muted"> · SQL unchanged</span>}</td>
                <td className={v.checks_changed ? '' : 'muted'}>{v.checks_changed ? 'checks changed' : 'checks unchanged'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {current && (
        <>
          <p className="muted" data-testid="diff-summary">{current.id.slice(0, 7)} against the version before: {diffSummary(current.diff)}</p>
          <pre className="diff" data-testid="diff">
            {parseDiff(current.diff).map((l, i) => <span key={i} className={l.kind}>{l.text}{'\n'}</span>)}
          </pre>
        </>
      )}
      {gauge}
      {current && (
        <footer className="actions">
          {restoreButton}
          <Command line={restoreCommand(model.name, current.id)} />
        </footer>
      )}
      {noticeLine}
      {errorLine}
    </section>
  );
}
