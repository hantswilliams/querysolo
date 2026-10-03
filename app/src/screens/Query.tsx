// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Screen 2 of the app brief: SQL in, the verdict before the rows, the rows as they stream.
// Cmd/Ctrl+Enter runs; Esc aborts the fetch, which closes the core's result and records the
// run as stopped early; Red is a refusal until "Run anyway"; the grid keeps 100,000 rows.
// Since decisions U1 the editor sits above the results with a draggable split, and a
// table's detail or a preview takes the results pane when the explorer opened one.

import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Api, ApiError, type TableInfo } from '../lib/api';
import { RedRefused, runQuery, type Column, type Row, type VerdictLine } from '../lib/arrow';
import { sqlCommand } from '../lib/command';
import type { Session } from '../lib/session';
import { Command } from '../components/Command';
import { GaugeLine, type RunState } from '../components/GaugeLine';
import { Chart } from '../components/Chart';
import { Grid } from '../components/Grid';
import { SqlEditor } from '../components/SqlEditor';
import { SaveQuestion } from '../components/SaveQuestion';
import { Split } from '../components/Split';
import type { Mode } from '../lib/vocabulary';

export const ROW_CAP = 100_000;

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export interface QueryProps {
  session: Session;
  tables: TableInfo[];
  mode: Mode;
  /** After a run completes: a statement may have written a table (the panel and an open detail re-read). */
  onDone?: () => void;
  /** After a question is saved: the Models screen lists it on its next plan (G7). */
  onSaved?: () => void;
  /** What takes the results pane's place when set (a table's detail, a preview; U1). */
  panel?: ReactNode;
  /** Run was pressed: the rows are what it is for, so the window clears the panel. */
  onRun?: () => void;
  /** Lines above the results pane: an import's report, a drop's error. */
  notices?: ReactNode;
  /** SQL to put in the box and run on arrival (decisions Q1: a question's answer); the
   *  window clears it through `onArrived` so a re-render does not run it again. */
  arrive?: string;
  onArrived?: () => void;
}

export function Query({ session, tables, mode, onDone, onSaved, panel, notices, onRun, arrive, onArrived }: QueryProps) {
  const [sql, setSql] = useState(arrive ?? '');
  const [state, setState] = useState<RunState>({ kind: 'idle' });
  const [columns, setColumns] = useState<Column[]>([]);
  const [rows, setRows] = useState<Row[]>([]);
  const [allowRed, setAllowRed] = useState(false);
  const controller = useRef<AbortController | undefined>(undefined);
  // Milliseconds from Run: when the verdict arrived, when the first rows reached the grid
  // and how many, when the run ended; the step 3 gate reads them (§3.3's promise, measured).
  const [timing, setTiming] = useState<{ verdict?: number; firstRows?: number; firstCount?: number; done?: number }>({});
  const pending = useRef<Row[]>([]);
  const frame = useRef<number | undefined>(undefined);

  const schema = Object.fromEntries(tables.map((t) => [t.name, t.columns.map(([name]) => name)]));

  // Batches land faster than React should paint; they are flushed once per frame.
  const flush = useCallback(() => {
    frame.current = undefined;
    if (pending.current.length === 0) return;
    const add = pending.current;
    pending.current = [];
    setRows((prev) => (prev.length === 0 ? add : prev.concat(add)));
  }, []);

  const run = useCallback(async (text: string, red: boolean) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    onRun?.();
    controller.current?.abort();
    const ac = new AbortController();
    controller.current = ac;
    pending.current = [];
    setRows([]);
    setColumns([]);
    setState({ kind: 'estimating' });
    const api = new Api(session);
    const t0 = performance.now();
    let verdict: VerdictLine | undefined;
    let count = 0;
    let capped = false;
    let first = true;
    setTiming({});
    // A run that a newer one replaced (Run pressed again; the arrival effect twice under
    // StrictMode) says nothing more: its late rows, verdict or "stopped" would land on top
    // of the newer run's state.
    const current = () => controller.current === ac;
    try {
      const result = await runQuery(api, trimmed, red, ac.signal, {
        onVerdict: (v) => { verdict = v; if (!current()) return; setTiming((t) => ({ ...t, verdict: performance.now() - t0 })); setState({ kind: 'running', verdict: v, rows: 0 }); },
        onSchema: (cols) => { if (current()) setColumns(cols); },
        onRows: (batch) => {
          if (!current()) return false;
          const room = ROW_CAP - count;
          const take = batch.length > room ? batch.slice(0, room) : batch;
          count += take.length;
          pending.current.push(...take);
          if (first) {
            // The first batch goes to the grid at once; its size is read now, not when
            // React applies the update (by then later batches have added to `count`).
            first = false;
            flush();
            const firstMs = performance.now() - t0;
            const firstCount = count;
            setTiming((t) => ({ ...t, firstRows: firstMs, firstCount }));
          }
          else if (frame.current === undefined) frame.current = requestAnimationFrame(flush);
          setState({ kind: 'running', verdict: verdict!, rows: count });
          if (count >= ROW_CAP) { capped = true; return false; }
          return true;
        },
      });
      if (!current()) return;
      flush();
      setTiming((t) => ({ ...t, done: performance.now() - t0 }));
      setState({ kind: 'done', verdict: verdict!, rows: count, seconds: (performance.now() - t0) / 1000, complete: result.complete && !capped, capped });
      onDone?.();
    } catch (e: unknown) {
      if (!current()) return;
      flush();
      if (ac.signal.aborted) {
        setState({ kind: 'stopped', verdict, rows: count, seconds: (performance.now() - t0) / 1000 });
      } else if (e instanceof RedRefused) {
        setState({ kind: 'refused', verdict: e.estimate });
      } else if (e instanceof ApiError) {
        setState({ kind: 'error', message: `${e.code}: ${e.message}` });
      } else {
        setState({ kind: 'error', message: message(e) });
      }
    } finally {
      if (controller.current === ac) controller.current = undefined;
    }
  }, [session, flush, onRun]);

  const cancel = useCallback(() => { controller.current?.abort(); }, []);

  // Q1: SQL handed in is run at once, as if typed and Run pressed.
  useEffect(() => {
    if (!arrive) return;
    setSql(arrive);
    setAllowRed(false);
    onArrived?.();
    void run(arrive, false);
  }, [arrive]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => () => controller.current?.abort(), []);

  // F0.8.6: Esc cancels from anywhere in the window, not only inside the box.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && controller.current) { controller.current.abort(); e.preventDefault(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const running = state.kind === 'running' || state.kind === 'estimating';
  // G7: Save is offered once the gauge has spoken — a run that finished, one stopped part
  // way, or a Red refusal. A Red statement saves too; the box says so.
  const verdict = 'verdict' in state ? state.verdict : undefined;
  const api = new Api(session);

  return (
    <section className="query" data-testid="query" data-verdict-ms={timing.verdict?.toFixed(0)} data-first-rows-ms={timing.firstRows?.toFixed(0)} data-first-rows={timing.firstCount} data-done-ms={timing.done?.toFixed(0)}>
      <Split
        top={
          <>
            <SqlEditor value={sql} onChange={(s) => { setSql(s); setAllowRed(false); }} onRun={() => void run(sql, allowRed)} onCancel={cancel} schema={schema} autoFocus />
            <div className="query-bar">
              {running ? (
                <button type="button" className="quiet" onClick={cancel} data-testid="cancel">Stop (Esc)</button>
              ) : (
                <button type="button" className="primary" onClick={() => void run(sql, allowRed)} disabled={!sql.trim()} data-testid="run">Run</button>
              )}
              {verdict && !running && (
                <SaveQuestion api={api} sql={sql.trim()} mode={mode} firstColumn={columns[0]?.name} red={verdict.verdict === 'red'} onSaved={onSaved} />
              )}
              <Command line={sql.trim() ? sqlCommand(sql.trim(), allowRed) : 'querysolo sql <sql>'} />
            </div>
            <GaugeLine state={state} onRunAnyway={() => { setAllowRed(true); void run(sql, true); }} />
          </>
        }
        bottom={
          <>
            {notices}
            {panel ?? (
              <>
                <Chart columns={columns} rows={rows} done={state.kind === 'done'} />
                <Grid columns={columns} rows={rows} />
              </>
            )}
          </>
        }
      />
    </section>
  );
}
