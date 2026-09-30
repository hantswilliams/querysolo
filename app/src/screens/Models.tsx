// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Screens 7 and 8 of the mockups (real-data brief R5, step 6): the project's dbt models
// through the gauge. Technical mode is `querysolo run --plan` as a panel: the DAG with a
// verdict per model, and a model's compiled SQL, lineage, tests, and last run; `Run all` is
// `querysolo run`, `Run this` is `querysolo run <model>`, a Red model refuses until
// `Run anyway`. Simple mode is the same DAG as cards: questions, checks, freshness, and
// one `Refresh all`. The model's panel carries its history (versions brief G6, step 3):
// the versions with the diff and Restore in Technical, the same as sentences behind
// History on the card in Simple. Each model carries its state (decisions V3, step 4):
// fresh, edited, upstream (an input changed) or never, on the DAG and the cards, and
// `Run what changed` is `querysolo run --stale`. Nothing here does what the terminal cannot.

import { useCallback, useEffect, useState } from 'react';
import { Api, ApiError, ago, humanBytes, type ModelResult, type PlannedModel, type RunReport, type TableInfo } from '../lib/api';
import { runCommand } from '../lib/command';
import type { Session } from '../lib/session';
import { changeSentence, humanSeconds, outOfDateName, planSummary, staleCount, stateSentence, testLabel, verdictSentence, words, type Mode } from '../lib/vocabulary';
import { collapseDiff, diffSummary, parseDiff } from '../lib/versions';
import { Command } from '../components/Command';
import { LineageRows } from '../components/Lineage';
import { Recent } from '../components/Recent';
import { Versions } from '../components/Versions';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const verdictWord: Record<string, string> = { green: 'Green', yellow: 'Yellow', red: 'Red', none: 'Not estimated' };

export interface ModelsProps {
  session: Session;
  mode: Mode;
  /** The tables panel's list: a model's freshness is its table's or its view's. */
  tables: TableInfo[];
  /** After a run: tables and views changed. */
  onChanged: () => Promise<void>;
  /** The model to select on arrival (a lineage link named it, G8); the first otherwise.
   *  `onSelected` says it was, so the request is not repeated. */
  select?: string;
  onSelected?: () => void;
  /** A lineage link named a table or view: the Tables screen opens its detail. */
  onOpenTable?: (name: string) => void;
  /** Decisions Q1: the rows of a model — the Tables screen with `select * from <name>` run. */
  onAnswer?: (name: string) => void;
  /** The detail's Recent strip (L2): the Changes screen, filtered to the model. */
  onOpenChanges?: (name: string) => void;
}

function Verdict({ m }: { m: PlannedModel }) {
  if (m.error) return <span className="verdict none" data-testid="verdict">?</span>;
  return <span className={`verdict ${m.verdict ?? 'none'}`} data-testid="verdict">{m.verdict ? verdictWord[m.verdict] ?? m.verdict : '—'}</span>;
}

function LastRunLine({ m, label }: { m: PlannedModel; label: string }) {
  const r = m.last_run;
  if (!r) return <span className="muted">{label}: never</span>;
  return (
    <span className="muted" data-testid="last-run">
      {label}: {ago(r.ts)}{r.ok ? (r.seconds !== null ? `, took ${humanSeconds(r.seconds)}` : '') : `, failed${r.error ? ` (${r.error})` : ''}`}
    </span>
  );
}

/** The state's sentence, with the model it blames as a link when there is one (V3). */
function StateLine({ m, mode, onSelect }: { m: PlannedModel; mode: Mode; onSelect: (name: string) => void }) {
  const blamed = m.state === 'upstream' ? outOfDateName(m.state_reason) : null;
  const text = stateSentence(m, mode);
  if (!blamed) return <>{text}</>;
  const [before, after] = text.split(blamed, 2);
  return (
    <>{before}<button type="button" className="link mono" data-testid={`state-link-${blamed}`} onClick={() => onSelect(blamed)}>{blamed}</button>{after}</>
  );
}

/** What changed, shown and not only said (V3): the SQL diff since the last run for an
 *  edited model — the changed lines with three of context, or the whole SQL on request —
 *  and the commits to the table since the run for one whose input changed. */
function WhatChanged({ m, mode }: { m: PlannedModel; mode: Mode }) {
  const [whole, setWhole] = useState(false);
  if (m.state === 'edited' && m.state_diff) {
    const all = parseDiff(m.state_diff);
    const { lines, folded } = whole ? { lines: all, folded: false } : collapseDiff(all);
    const canFold = folded || whole;
    return (
      <div className="what-changed" data-testid="what-changed">
        <p className="muted">
          {mode === 'simple' ? 'The SQL, against what was last refreshed' : 'the compiled SQL against the last run'}: {diffSummary(m.state_diff)}
          {canFold && <button type="button" className="link" data-testid="diff-whole" onClick={() => setWhole((w) => !w)}>{whole ? 'changes only' : 'whole SQL'}</button>}
        </p>
        <pre className="diff" data-testid="state-diff">
          {lines.map((l, i) => <span key={i} className={l.kind}>{l.text}{'\n'}</span>)}
        </pre>
      </div>
    );
  }
  if (m.state === 'upstream' && m.state_changes?.length) {
    return (
      <ul className="what-changed changes" data-testid="what-changed">
        {m.state_changes.map((c, i) => <li key={i} className="mono">{changeSentence(c, mode)}</li>)}
      </ul>
    );
  }
  return null;
}

/** The review (V3): every model that is not fresh, in the order the run would build
 *  them, each with why and what changed — read through before Run what changed. */
function Review({ models, mode, onSelect }: { models: PlannedModel[]; mode: Mode; onSelect: (name: string) => void }) {
  const w = words(mode);
  const stale = models.filter((m) => m.state && m.state !== 'fresh');
  if (stale.length === 0) return null;
  return (
    <section className="review" data-testid="review">
      <h3>
        {mode === 'simple' ? 'What changed since the last refresh' : 'Out of date'}
        <span className="muted"> · {stale.length} {stale.length === 1 ? w.model : w.models} · {w.runStale} builds them in this order</span>
      </h3>
      {stale.map((m) => (
        <article key={m.unique_id} data-testid={`review-${m.name}`}>
          <h4>
            <button type="button" className="link mono" onClick={() => onSelect(m.name)}>{m.name}</button>
            <span className={`state ${m.state ?? ''}`}> <StateLine m={m} mode={mode} onSelect={onSelect} /></span>
          </h4>
          <WhatChanged m={m} mode={mode} />
        </article>
      ))}
    </section>
  );
}

export function Models({ session, mode, tables, onChanged, select, onSelected, onOpenTable, onAnswer, onOpenChanges }: ModelsProps) {
  const api = new Api(session);
  const w = words(mode);
  const [models, setModels] = useState<PlannedModel[]>();
  const [selected, setSelected] = useState<string | undefined>(select);
  const [busy, setBusy] = useState<string>();
  const [error, setError] = useState<string>();
  const [refusal, setRefusal] = useState<{ text: string; select: string[]; stale?: boolean }>();
  const [report, setReport] = useState<RunReport>();
  const [historyOf, setHistoryOf] = useState<string>();

  const load = useCallback(async () => {
    setBusy(w.planning);
    try {
      const planned = await api.runPlan();
      setModels(planned);
      setError(undefined);
      setSelected((s) => (s && planned.some((m) => m.name === s) ? s : planned[0]?.name));
    } catch (e: unknown) {
      setModels([]);
      setError(message(e));
    } finally {
      setBusy(undefined);
    }
  }, [session.port, session.token]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { if (select) { setSelected(select); onSelected?.(); } }, [select]); // eslint-disable-line react-hooks/exhaustive-deps

  // G8: a name on the lineage lines opens that detail: a model of this project here (built
  // or not), anything else — an imported table, a view put by hand — on the Tables screen.
  function follow(name: string, kind: 'table' | 'view' | 'model') {
    if (kind === 'model' || !onOpenTable || models?.some((m) => m.name === name)) setSelected(name);
    else onOpenTable(name);
  }

  async function run(select: string[], runAnyway = false, stale = false) {
    setBusy(w.running);
    setError(undefined);
    setRefusal(undefined);
    try {
      const r = await api.run(select, runAnyway, stale);
      setReport(r);
      await onChanged();
      await load();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.code === 'red_refused') setRefusal({ text: e.message, select, stale });
      else setError(message(e));
      setBusy(undefined);
    }
  }

  // Q1: the rows. A model never built has none yet, so the run comes first; the rows are
  // asked for only when it built.
  async function answer(m: PlannedModel) {
    if (!onAnswer) return;
    if (m.state === 'never') {
      await run([m.name]); // `load` after it re-plans; a run that failed or was refused leaves the state
      const built = await api.runPlan([m.name]).catch(() => undefined);
      if (!built?.some((x) => x.name === m.name && x.state !== 'never')) return;
    }
    onAnswer(m.name);
  }
  const answerButton = (m: PlannedModel, primary = false) => onAnswer && (
    <button type="button" className={primary ? 'primary' : 'quiet'} disabled={!!busy} data-testid={`answer-${m.name}`} onClick={() => void answer(m)}>{m.state === 'never' ? w.answerAfterRun : w.answer}</button>
  );

  const byName = new Map(tables.map((t) => [t.name, t]));
  const results = new Map<string, ModelResult>((report?.results ?? []).map((r) => [r.name, r]));
  const current = models?.find((m) => m.name === selected);
  const anyRed = (models ?? []).some((m) => m.verdict === 'red');

  const stale = staleCount(models ?? []);
  const runAll = (
    <>
      <button type="button" className="primary" disabled={!!busy || !models?.length} data-testid="run-all" onClick={() => void run([])}>
        {busy ?? w.runAll}
      </button>
      <Command line={runCommand()} />
      <button type="button" className="quiet" disabled={!!busy || !stale} data-testid="run-stale" title={stale ? '' : `every ${w.model} is up to date`} onClick={() => void run([], false, true)}>
        {w.runStale}{stale ? ` (${stale})` : ''}
      </button>
      {stale > 0 && <Command line={runCommand([], { stale: true })} />}
    </>
  );

  const reportLine = report && (
    <section className="notice" data-testid="run-report">
      <b>
        {report.selected && report.selected.length === 0
          ? `Every ${w.model} is up to date; nothing ran.`
          : report.ok
            ? `${report.results.length} ${report.results.length === 1 ? w.model : w.models} built in ${humanSeconds(report.seconds)}.`
            : `${report.results.filter((r) => r.status !== 'success').length} of ${report.results.length} failed.`}
        {report.views_recorded.length > 0 && ` ${mode === 'simple' ? 'Answered live' : 'Views in the catalog'}: ${report.views_recorded.join(', ')}.`}
        {report.views_dropped.length > 0 && ` Dropped: ${report.views_dropped.join(', ')}.`}
      </b>
      {report.results.filter((r) => r.status !== 'success').map((r) => (
        <pre key={r.name} data-testid={`failed-${r.name}`}>{r.name}: {r.message ?? r.status}</pre>
      ))}
    </section>
  );

  const refusalBox = refusal && (
    <section className="error" data-testid="refusal">
      <b>{mode === 'simple' ? 'Too big for this machine right now.' : 'The gauge refused the run.'}</b>
      <pre>{refusal.text}</pre>
      <div className="actions">
        <button type="button" className="quiet" disabled={!!busy} data-testid="run-anyway" onClick={() => void run(refusal.select, true, refusal.stale)}>{w.runAnyway}</button>
        <Command line={runCommand(refusal.select, { runAnyway: true, stale: refusal.stale })} />
      </div>
    </section>
  );

  const empty = models && models.length === 0 && !error && (
    <p className="muted" data-testid="no-models">
      {mode === 'simple'
        ? 'No questions saved yet. A question is a SQL file under models/; ask one on the Tables screen and save it there.'
        : 'No models. A model is a SQL file under models/ (dbt); querysolo run builds them through the gauge.'}
    </p>
  );

  if (mode === 'simple') {
    return (
      <section className="models-screen simple" data-testid="models-screen" data-mode="simple">
        <header>
          <h2>{w.screen}<span className="muted"> · {models ? planSummary(models, mode) : '…'}</span></h2>
          <span className="run-all">{runAll}</span>
        </header>
        {reportLine}
        {refusalBox}
        {error && <section className="error" data-testid="models-error"><pre>{error}</pre></section>}
        {empty}
        {models && <Review models={models} mode={mode} onSelect={(name) => document.querySelector(`[data-testid="card-${name}"]`)?.scrollIntoView({ block: 'nearest' })} />}
        <div className="cards" data-testid="cards">
          {(models ?? []).map((m) => {
            const t = byName.get(m.name);
            const r = results.get(m.name);
            return (
              <article key={m.unique_id} className={`card ${m.verdict ?? ''}`} data-testid={`card-${m.name}`}>
                <h3 className="mono">{m.name}</h3>
                <p className="kind">{m.materialized === 'view' ? w.view : w.table}{t?.freshness ? ` · ${w.lastRun.toLowerCase()} ${ago(t.freshness)}` : ''}</p>
                <p className={`state ${m.state ?? ''}`} data-testid="state">{stateSentence(m, mode)}</p>
                <WhatChanged m={m} mode={mode} />
                {m.description && <p className="description">{m.description}</p>}
                <p className="sentence" data-testid="sentence">{verdictSentence(m, mode)}</p>
                <p className="checks" data-testid="checks">
                  {m.tests.length === 0 ? `no ${w.tests}` : `${m.tests.length} ${m.tests.length === 1 ? w.test : w.tests}: ${m.tests.map((x) => testLabel(x, mode)).join('; ')}`}
                </p>
                {r && <p className={r.status === 'success' ? 'muted' : 'failed'}>{r.status === 'success' ? `refreshed just now in ${humanSeconds(r.seconds)}` : `failed: ${r.message ?? r.status}`}</p>}
                <footer>
                  {answerButton(m, true)}
                  <button type="button" className="quiet" disabled={!!busy} data-testid={`refresh-${m.name}`} onClick={() => void run([m.name])}>{w.runOne}</button>
                  <Command line={runCommand([m.name])} />
                  <button type="button" className="quiet" aria-pressed={historyOf === m.name} data-testid={`history-${m.name}`} onClick={() => setHistoryOf((h) => (h === m.name ? undefined : m.name))}>{w.versions}</button>
                </footer>
                {historyOf === m.name && <Versions session={session} mode={mode} model={m} onRestored={load} />}
              </article>
            );
          })}
        </div>
      </section>
    );
  }

  return (
    <section className="models-screen" data-testid="models-screen" data-mode="technical">
      <header>
        <h2>{w.screen}<span className="muted"> · {models ? planSummary(models, mode) : '…'}</span></h2>
        <span className="run-all">{runAll}</span>
      </header>
      {reportLine}
      {refusalBox}
      {error && (
        <section className="error" data-testid="models-error">
          <b>The plan failed.</b>
          <pre>{error}</pre>
          <p>The plan is <code>querysolo run --plan</code>: dbt compiles the project, then every model is estimated. dbt comes with <code>pip install 'querysolo[dbt]'</code>.</p>
        </section>
      )}
      {empty}
      {models && <Review models={models} mode={mode} onSelect={setSelected} />}
      {models && models.length > 0 && (
        <div className="split">
          <div className="dag-wrap">
          <table className="dag" data-testid="dag">
            <thead><tr><th>Model</th><th>Kind</th><th>State</th><th>Verdict</th><th>Estimate</th><th>Scans</th><th>Last run</th></tr></thead>
            <tbody>
              {models.map((m) => {
                const r = results.get(m.name);
                return (
                  <tr key={m.unique_id} className={m.name === selected ? 'on' : ''} data-testid={`model-${m.name}`} onClick={() => setSelected(m.name)}>
                    <td className="mono">{m.name}</td>
                    <td>{m.materialized}</td>
                    <td className={`state ${m.state ?? ''}`} data-testid="state">{m.state ?? '—'}</td>
                    <td><Verdict m={m} /></td>
                    <td>{m.est_wall_local === null ? '—' : humanSeconds(m.est_wall_local)}</td>
                    <td>{m.est_bytes === null ? '—' : humanBytes(m.est_bytes)}</td>
                    <td className={r && r.status !== 'success' ? 'failed' : 'muted'}>
                      {r ? (r.status === 'success' ? `just now, ${humanSeconds(r.seconds)}` : `failed`) : m.last_run ? ago(m.last_run.ts) : 'never'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          </div>
          {current && (
            <article className="model" data-testid="model-detail">
              <header>
                <h3 className="mono">{current.name}<span className="muted"> · {current.materialized} · {current.path}</span></h3>
              </header>
              {current.description && <p>{current.description}</p>}
              <dl className="facts">
                <dt>State</dt>
                <dd className={`state ${current.state ?? ''}`} data-testid="state-sentence"><StateLine m={current} mode={mode} onSelect={setSelected} /><WhatChanged m={current} mode={mode} /></dd>
                <dt>Verdict</dt>
                <dd><Verdict m={current} /> <span data-testid="sentence">{verdictSentence(current, mode)}</span>{current.reason && !current.error ? <span className="muted"> · {current.reason}</span> : null}</dd>
                <LineageRows session={session} name={current.name} mode={mode} onOpen={follow} refreshKey={current.last_run?.ts ?? null} />
                <Recent session={session} name={current.name} mode={mode} onMore={onOpenChanges} refreshKey={`${current.last_run?.ts ?? ''}|${current.state_since ?? ''}`} />
                <dt>Tests</dt>
                <dd data-testid="tests">
                  {current.tests.length === 0 ? <span className="muted">none in schema.yml</span> : (
                    <ul>{current.tests.map((t) => <li key={t.unique_id} className="mono">{testLabel(t, mode)}</li>)}</ul>
                  )}
                </dd>
                <dt>{w.lastRun}</dt>
                <dd><LastRunLine m={current} label="run" /></dd>
              </dl>
              <h4>Compiled SQL</h4>
              <pre className="sql" data-testid="compiled-sql">{current.compiled_sql}</pre>
              <footer className="actions">
                <button type="button" className={current.verdict === 'red' ? 'quiet' : 'primary'} disabled={!!busy} data-testid="run-this" onClick={() => void run([current.name])}>{w.runOne}</button>
                <Command line={runCommand([current.name])} />
                {answerButton(current)}
                {current.verdict === 'red' && <span className="muted">Red: the run refuses this one until {w.runAnyway.toLowerCase()}.</span>}
              </footer>
              <Versions session={session} mode={mode} model={current} onRestored={load} />
            </article>
          )}
        </div>
      )}
      {anyRed && !refusal && models && <p className="muted" data-testid="red-note">A Red model makes <code>querysolo run</code> refuse the whole DAG until <code>--run-anyway</code>; that is the gauge's promise, not a limit of the app.</p>}
    </section>
  );
}
