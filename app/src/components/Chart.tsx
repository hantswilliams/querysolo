// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The auto-chart (app brief A5): rendered with Vega-Lite when the one rule in lib/chart.ts
// gives a plan, and nothing otherwise. Vega runs its expressions through the interpreter
// rather than `new Function`, so the window's content-security policy stays without
// 'unsafe-eval' (brief §7). The libraries load with the first chart, not with the screen.

import { useEffect, useMemo, useRef } from 'react';
import type { Column, Row } from '../lib/arrow';
import { planChart, vegaLiteSpec } from '../lib/chart';

export function Chart({ columns, rows, done }: { columns: Column[]; rows: Row[]; done: boolean }) {
  const host = useRef<HTMLDivElement>(null);
  const plan = useMemo(() => (done ? planChart(columns, rows) : null), [columns, rows, done]);

  useEffect(() => {
    const el = host.current;
    if (!el || !plan) return;
    let finalize: (() => void) | undefined;
    let cancelled = false;
    (async () => {
      const [{ default: embed }, { expressionInterpreter }] = await Promise.all([import('vega-embed'), import('vega-interpreter')]);
      if (cancelled) return;
      const result = await embed(el, vegaLiteSpec(plan) as never, { actions: false, renderer: 'svg', ast: true, expr: expressionInterpreter as never });
      finalize = () => result.finalize();
      if (cancelled) finalize();
    })().catch((e: unknown) => { el.textContent = `chart: ${e instanceof Error ? e.message : String(e)}`; });
    return () => { cancelled = true; finalize?.(); };
  }, [plan]);

  if (!plan) return null;
  return (
    <figure className="chart" data-testid="chart" data-kind={plan.kind}>
      <figcaption>{plan.y} by {plan.x}{plan.values.length < rows.length ? `, the first ${plan.values.length.toLocaleString()} rows` : ''}</figcaption>
      <div ref={host} className="chart-host" />
    </figure>
  );
}
