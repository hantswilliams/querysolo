// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The auto-chart's one rule (app brief A5): a result of exactly two columns, one
// categorical and one numeric, is a bar chart; a date or timestamp and a numeric is a line;
// anything else is no chart and no error. Built from the first 5,000 rows, in the order
// the query returned them. Pure, so it is tested without a renderer.

import type { Column, Row } from './arrow';

export const CHART_ROWS = 5_000;
export const MAX_BARS = 40;

export type ChartKind = 'bar' | 'line';

export interface ChartPlan {
  kind: ChartKind;
  x: string;
  y: string;
  values: Array<Record<string, unknown>>;
}

const numeric = (t: string) => /^(Int|Uint|Float|Decimal)/.test(t);
const asNumber = (t: string) => (t.startsWith('Decimal') ? (v: unknown) => (v == null ? null : Number(v)) : (v: unknown) => v);
const temporal = (t: string) => /^(Date|Timestamp)/.test(t);
const categorical = (t: string) => /^(Utf8|LargeUtf8|Bool)/.test(t);

/** The plan for these columns and rows, or null when the rule gives no chart. */
export function planChart(columns: Column[], rows: Row[]): ChartPlan | null {
  if (columns.length !== 2) return null;
  const [a, b] = columns;
  let x: Column | undefined;
  let y: Column | undefined;
  let kind: ChartKind | undefined;
  for (const [cat, num] of [[a, b], [b, a]] as const) {
    if (numeric(num.type) && categorical(cat.type)) { x = cat; y = num; kind = 'bar'; break; }
    if (numeric(num.type) && temporal(cat.type)) { x = cat; y = num; kind = 'line'; break; }
  }
  if (!x || !y || !kind) return null;
  const xi = columns.indexOf(x);
  const yi = columns.indexOf(y);
  const slice = rows.slice(0, CHART_ROWS);
  if (kind === 'bar') {
    const distinct = new Set(slice.map((r) => String(r[xi])));
    if (distinct.size > MAX_BARS || distinct.size < 2) return null;
  }
  const num = asNumber(y.type);
  const values = slice.map((r) => ({ [x!.name]: r[xi], [y!.name]: num(r[yi]) }));
  return { kind, x: x.name, y: y.name, values };
}

// The palette the site and the app share (web/src/styles/palette.css): the lake for the one
// series, muted ink for text, the line colour for hairlines. Text never wears the series
// colour.
//
// Read from the document rather than written down, so a chart is drawn in the theme the
// window is actually in (decision D1). Vega is handed colours, not CSS, so this is the one
// place a dark window would otherwise keep light-grey axes on a dark panel. The fallbacks
// are the light values, for a render with no document to ask (a test, a server).
const FALLBACK = { lake: '#164F44', muted: '#5F6E68', line: '#D5DCD6', grid: '#F4F6F1', panel: '#FFFFFF', local: '#1F8A5B', slow: '#C98A12', burst: '#D24B3A' };

export function chartColours(root: HTMLElement | null = globalThis.document?.documentElement ?? null) {
  if (!root) return { ...FALLBACK };
  const style = getComputedStyle(root);
  const token = (name: string, fallback: string) => style.getPropertyValue(name).trim() || fallback;
  return {
    lake: token('--lake', FALLBACK.lake),
    muted: token('--muted', FALLBACK.muted),
    line: token('--line', FALLBACK.line),
    grid: token('--bg', FALLBACK.grid), // the grid is the window's own background, a shade under the panel
    panel: token('--panel', FALLBACK.panel),
    local: token('--local', FALLBACK.local),
    slow: token('--slow', FALLBACK.slow),
    burst: token('--burst', FALLBACK.burst),
  };
}

const FONT = 'Manrope, system-ui, -apple-system, "Segoe UI", sans-serif';

/** A Vega-Lite spec for the plan: thin marks, rounded data-ends, 2px line with markers,
 *  a hairline grid, a tooltip on every mark, and no legend (one series; the title names it). */
export function vegaLiteSpec(plan: ChartPlan): Record<string, unknown> {
  const { lake, muted, line, grid } = chartColours();
  const mark = plan.kind === 'bar'
    ? { type: 'bar', cornerRadiusEnd: 4, color: lake, tooltip: true, width: { band: 0.6 } } // thin: the band's leftover is air
    : { type: 'line', strokeWidth: 2, color: lake, point: { size: 64, filled: true, color: lake, stroke: 'var(--panel)', strokeWidth: 2 }, tooltip: true, interpolate: 'monotone' };
  const x = plan.kind === 'bar'
    ? { field: plan.x, type: 'nominal', sort: null, axis: { labelAngle: 0, labelLimit: 120, title: null } }
    : { field: plan.x, type: 'temporal', axis: { title: null, grid: false } };
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    width: 'container',
    height: 200,
    background: 'transparent',
    data: { values: plan.values },
    mark,
    encoding: {
      x,
      y: { field: plan.y, type: 'quantitative', axis: { title: plan.y, format: ',~f', tickCount: 5 } },
    },
    config: {
      font: FONT,
      view: { stroke: null },
      axis: { labelColor: muted, titleColor: muted, domainColor: line, tickColor: line, gridColor: grid, gridWidth: 1, labelFontSize: 12, titleFontSize: 12, titleFontWeight: 500 },
      scale: { bandPaddingInner: 0.25 },
    },
  };
}

// -- the Gauge screen's scatter (real-data brief R8) -------------------------------------

/** One completed local run with both numbers: what the scatter plots. */
export interface GaugePoint { est: number; actual: number; verdict: string; when: string }


/** Estimate versus actual on log axes with the diagonal of a perfect estimate; the verdict
 *  colours a point and the legend names it, so colour is never the only carrier. */
export function scatterSpec(points: GaugePoint[]): Record<string, unknown> {
  const { muted, line, grid, panel, local, slow, burst } = chartColours();
  const verdictColours = { green: local, yellow: slow, red: burst };
  const all = points.flatMap((p) => [p.est, p.actual]).filter((v) => v > 0);
  const lo = Math.max(Math.min(...all, 1) / 2, 0.001);
  const hi = Math.max(...all, 1) * 2;
  return {
    $schema: 'https://vega.github.io/schema/vega-lite/v6.json',
    width: 'container',
    height: 260,
    background: 'transparent',
    layer: [
      {
        data: { values: [{ v: lo }, { v: hi }] },
        mark: { type: 'line', strokeDash: [4, 4], color: line, strokeWidth: 1.5 },
        encoding: { x: { field: 'v', type: 'quantitative' }, y: { field: 'v', type: 'quantitative' } },
      },
      {
        data: { values: points },
        mark: { type: 'point', filled: true, size: 70, opacity: 0.85, stroke: panel, strokeWidth: 1.5, tooltip: true },
        encoding: {
          x: { field: 'est', type: 'quantitative', scale: { type: 'log', domain: [lo, hi] }, axis: { title: 'estimated seconds', format: '~s', tickCount: 5 } },
          y: { field: 'actual', type: 'quantitative', scale: { type: 'log', domain: [lo, hi] }, axis: { title: 'actual seconds', format: '~s', tickCount: 5 } },
          color: {
            field: 'verdict',
            type: 'nominal',
            scale: { domain: ['green', 'yellow', 'red'], range: [verdictColours.green, verdictColours.yellow, verdictColours.red] },
            legend: { title: null, orient: 'top', labelExpr: "datum.label == 'green' ? 'Green · runs here' : datum.label == 'yellow' ? 'Yellow · slowly' : 'Red · more machine'" },
          },
          tooltip: [
            { field: 'when', type: 'nominal', title: 'when' },
            { field: 'verdict', type: 'nominal', title: 'verdict' },
            { field: 'est', type: 'quantitative', title: 'estimated s', format: '.2f' },
            { field: 'actual', type: 'quantitative', title: 'actual s', format: '.2f' },
          ],
        },
      },
    ],
    config: {
      font: FONT,
      view: { stroke: null },
      axis: { labelColor: muted, titleColor: muted, domainColor: line, tickColor: line, gridColor: grid, gridWidth: 1, labelFontSize: 12, titleFontSize: 12, titleFontWeight: 500 },
      legend: { labelColor: muted, labelFontSize: 12, symbolType: 'circle' },
    },
  };
}
