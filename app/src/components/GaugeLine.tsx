// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The gauge line above the grid: the verdict in the site's words and colours with the
// sentence, from the response headers before any row (F0.8.4); Red is a refusal until "Run
// anyway"; while rows stream it counts them; when done, the count and the time.

import type { VerdictLine } from '../lib/arrow';

export type RunState =
  | { kind: 'idle' }
  | { kind: 'estimating' }
  | { kind: 'running'; verdict: VerdictLine; rows: number }
  | { kind: 'done'; verdict: VerdictLine; rows: number; seconds: number; complete: boolean; capped: boolean }
  | { kind: 'stopped'; verdict?: VerdictLine; rows: number; seconds: number }
  | { kind: 'refused'; verdict: VerdictLine }
  | { kind: 'error'; message: string };

export function GaugeLine({ state, onRunAnyway }: { state: RunState; onRunAnyway: () => void }) {
  if (state.kind === 'idle') return null;
  const v = 'verdict' in state ? state.verdict : undefined;
  const cls = `gauge ${v?.verdict ?? (state.kind === 'error' ? 'red' : 'pending')} ${state.kind}`;
  return (
    <div className={cls} role="status" aria-live="polite" data-testid="gauge" data-state={state.kind} data-verdict={v?.verdict ?? ''}>
      <i aria-hidden="true" />
      {state.kind === 'estimating' && <span className="words">estimating…</span>}
      {v && <span className="words">{v.words}</span>}
      {v && <span className="reason">· {v.reason}</span>}
      {state.kind === 'running' && <span className="tail" data-testid="gauge-tail">· running, {state.rows.toLocaleString()} rows so far</span>}
      {state.kind === 'done' && (
        <span className="tail" data-testid="gauge-tail">
          · {state.rows.toLocaleString()} rows in {state.seconds.toFixed(state.seconds < 10 ? 2 : 1)} s
          {state.capped && <> · showing the first {state.rows.toLocaleString()} of a stream; <code>querysolo sql --format parquet</code> for all of it</>}
        </span>
      )}
      {state.kind === 'stopped' && <span className="tail" data-testid="gauge-tail">· stopped after {state.rows.toLocaleString()} rows, {state.seconds.toFixed(1)} s</span>}
      {state.kind === 'refused' && (
        <button type="button" className="quiet" onClick={onRunAnyway} data-testid="run-anyway">Run anyway</button>
      )}
      {state.kind === 'error' && <span className="reason" data-testid="sql-error">{state.message}</span>}
    </div>
  );
}
