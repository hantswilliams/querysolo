// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Screen 5 of the mockups, the gauge's record (real-data brief R8): this machine, the runs
// recorded and how the estimates held up, the run list, estimate versus actual on log
// axes, what the gauge has learned (after 20 runs, from session 10), and four verbs:
// `gauge history`, `gauge export`, `gauge reset`, `gauge probe`. Nothing is sent anywhere;
// the export is a file in the project.

import { useCallback, useEffect, useRef, useState } from 'react';
import { Api, humanBytes, type GaugeSummary, type Health, type HistoryRun } from '../lib/api';
import { scatterSpec, type GaugePoint } from '../lib/chart';
import { gaugeExportCommand, gaugeHistoryCommand, gaugeProbeCommand, gaugeResetCommand } from '../lib/command';
import type { Session } from '../lib/session';
import { Command } from '../components/Command';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

const seconds = (s: number | null) => (s === null ? '—' : s < 10 ? `${s.toFixed(1)} s` : s < 600 ? `${Math.round(s)} s` : `${(s / 60).toFixed(1)} min`);
const words: Record<string, string> = { green: 'Green', yellow: 'Yellow', red: 'Red', none: 'Not estimated' };
const when = (iso: string) => {
  const d = new Date(iso);
  const today = new Date();
  const sameDay = d.toDateString() === today.toDateString();
  return sameDay ? d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : d.toLocaleDateString([], { month: 'short', day: 'numeric' }) + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

export function points(runs: HistoryRun[]): GaugePoint[] {
  return runs
    .filter((r) => r.ran && r.ran_where === 'local' && !r.error && r.verdict !== 'none' && r.est_wall_local && r.actual_wall && r.est_wall_local > 0 && r.actual_wall > 0)
    .map((r) => ({ est: r.est_wall_local!, actual: r.actual_wall!, verdict: r.verdict ?? 'green', when: when(r.ts) }));
}

function Scatter({ data }: { data: GaugePoint[] }) {
  const host = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = host.current;
    if (!el || data.length === 0) return;
    let finalize: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      const [{ default: embed }, { expressionInterpreter }] = await Promise.all([import('vega-embed'), import('vega-interpreter')]);
      if (cancelled) return;
      const result = await embed(el, scatterSpec(data) as never, { actions: false, renderer: 'svg', ast: true, expr: expressionInterpreter as never });
      finalize = () => result.finalize();
      if (cancelled) finalize();
    })().catch((e: unknown) => { el.textContent = `chart: ${message(e)}`; });
    return () => { cancelled = true; finalize?.(); };
  }, [data]);
  if (data.length === 0) return <p className="muted">The scatter draws once a run has both an estimate and an actual.</p>;
  return (
    <figure className="chart" data-testid="scatter" data-points={data.length}>
      <figcaption>estimate versus actual · log scale · the dashed line is a perfect estimate</figcaption>
      <div ref={host} className="chart-host" />
    </figure>
  );
}

export interface GaugeProps {
  session: Session;
  health?: Health;
  /** After a probe: health has a new disk figure. */
  onHealthChanged: () => Promise<void>;
}

export function Gauge({ session, health, onHealthChanged }: GaugeProps) {
  const api = new Api(session);
  const [runs, setRuns] = useState<HistoryRun[]>();
  const [summary, setSummary] = useState<GaugeSummary>();
  const [busy, setBusy] = useState<string>();
  const [notice, setNotice] = useState<{ text: string; line: string }>();
  const [error, setError] = useState<string>();
  const [confirmReset, setConfirmReset] = useState(false);

  const load = useCallback(async () => {
    try {
      const [r, s] = await Promise.all([api.history(200), api.gaugeSummary()]);
      setRuns(r);
      setSummary(s);
      setError(undefined);
    } catch (e: unknown) {
      setError(message(e));
    }
  }, [session.port, session.token]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { void load(); }, [load]);

  async function act(label: string, fn: () => Promise<{ text: string; line: string }>) {
    setBusy(label);
    setError(undefined);
    try {
      setNotice(await fn());
      await load();
    } catch (e: unknown) {
      setError(message(e));
    } finally {
      setBusy(undefined);
    }
  }

  const machine = health?.machine;
  const disk = health?.throughput_local_mbps;
  const share = summary?.within_2x_share;

  return (
    <section className="gauge-screen" data-testid="gauge-screen">
      <header>
        <h2>Gauge · this machine</h2>
        <Command line={gaugeHistoryCommand()} />
      </header>
      <p className="muted machine" data-testid="machine">
        {machine ? `${machine.ram ? `${Math.round(machine.ram / 2 ** 30)} GB` : '?'} · ${machine.threads ?? '?'} threads · memory limit ${machine.memory_limit_text ?? '—'} · ` : ''}
        {disk ? `${Math.round(disk).toLocaleString()} MB/s local disk${health?.throughput_probe === 'cached' ? ' (cached)' : ''}` : 'disk not measured'}
        {health?.bandwidth_mbps ? ` · ${Math.round(health.bandwidth_mbps)} Mbps ↓` : ''}
      </p>
      <section className="tiles" data-testid="tiles">
        <div><b data-testid="tile-runs">{summary ? summary.runs.toLocaleString() : '—'}</b><span>runs recorded</span></div>
        <div><b data-testid="tile-within">{share === null || share === undefined ? '—' : `${Math.round(share * 100)}%`}</b><span>within 2× on time{summary?.compared ? ` (${summary.compared} compared)` : ''}</span></div>
        <div><b data-testid="tile-green-over">{summary ? summary.green_over_3min : '—'}</b><span>Green runs over 3 min</span></div>
      </section>
      <Scatter data={runs ? points(runs) : []} />
      <p className="muted learned" data-testid="learned">
        Learned on this machine: nothing yet. Correction factors are applied after 20 runs (session 10); until then the estimate is the model's.
      </p>
      <table className="runs" data-testid="runs">
        <thead><tr><th>When</th><th>Verdict</th><th>Where</th><th>Estimate</th><th>Actual</th><th>Scans</th></tr></thead>
        <tbody>
          {(runs ?? []).slice(0, 50).map((r) => (
            <tr key={r.id} data-testid={`run-${r.id}`}>
              <td title={r.ts}>{when(r.ts)}</td>
              <td className={`verdict ${r.verdict ?? ''}`}>{r.verdict ? words[r.verdict] ?? r.verdict : '—'}{r.error ? ' · failed' : ''}</td>
              <td>{r.ran ? r.ran_where : r.ran_where === 'refused' ? 'refused' : 'not run'}</td>
              <td>{seconds(r.est_wall_local)}</td>
              <td>{seconds(r.actual_wall)}</td>
              <td>{r.est_bytes === null ? '—' : humanBytes(r.est_bytes)}</td>
            </tr>
          ))}
          {runs && runs.length === 0 && <tr><td colSpan={6} className="muted">No runs yet. Every query you run is recorded here with its estimate and what happened.</td></tr>}
        </tbody>
      </table>
      {notice && (
        <section className="notice" data-testid="gauge-notice">
          <b>{notice.text}</b>
          <Command line={notice.line} />
        </section>
      )}
      {error && <section className="error" data-testid="gauge-error"><pre>{error}</pre></section>}
      <footer className="actions">
        <button
          type="button"
          className="quiet"
          disabled={!!busy}
          data-testid="export"
          onClick={() => void act('exporting…', async () => {
            const r = await api.gaugeExport();
            return { text: `${r.runs} ${r.runs === 1 ? 'run' : 'runs'} written to ${r.path}. Nothing was sent anywhere; the file holds the fingerprint, the machine class, operator counts, estimate and actual, never SQL, table or column names, or values.`, line: gaugeExportCommand() };
          })}
        >Export history</button>
        <button
          type="button"
          className="quiet"
          disabled={!!busy}
          data-testid="probe"
          onClick={() => void act('measuring the disk…', async () => {
            const r = await api.gaugeProbe();
            await onHealthChanged();
            return { text: `Local disk reads at ${Math.round(r.mbps).toLocaleString()} MB/s (${r.method === 'cached' ? 'through the cache, capped' : 'cache bypassed'}).`, line: gaugeProbeCommand() };
          })}
        >Probe the disk again</button>
        {confirmReset ? (
          <span className="confirm" data-testid="confirm-reset">
            Forget every recorded run?
            <button
              type="button"
              className="primary"
              disabled={!!busy}
              data-testid="reset-yes"
              onClick={() => { setConfirmReset(false); void act('forgetting…', async () => { const r = await api.gaugeReset(); return { text: `${r.removed} ${r.removed === 1 ? 'run' : 'runs'} forgotten.`, line: gaugeResetCommand() }; }); }}
            >Yes, reset</button>
            <button type="button" className="quiet" onClick={() => setConfirmReset(false)}>Keep them</button>
          </span>
        ) : (
          <button type="button" className="quiet" disabled={!!busy || !summary?.runs} data-testid="reset" onClick={() => setConfirmReset(true)}>Reset</button>
        )}
        {busy && <span className="muted">{busy}</span>}
      </footer>
    </section>
  );
}
