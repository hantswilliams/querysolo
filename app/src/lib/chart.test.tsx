// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 4 gate, the auto-chart's one rule (A5): categorical + numeric is a bar chart, date +
// numeric is a line, anything else is no chart; the first 5,000 rows; one series, one hue.

import { describe, expect, it } from 'vitest';
import { CHART_ROWS, MAX_BARS, planChart, vegaLiteSpec } from './chart';

const col = (name: string, type: string) => ({ name, type });

describe('planChart', () => {
  it('one categorical and one numeric column is a bar chart, in the rows\' order', () => {
    const plan = planChart([col('customer', 'Utf8'), col('n', 'Int64')], [['c2', 4], ['c1', 9], ['c3', 1]]);
    expect(plan?.kind).toBe('bar');
    expect(plan?.x).toBe('customer');
    expect(plan?.values.map((v) => v.customer)).toEqual(['c2', 'c1', 'c3']);
    const spec = vegaLiteSpec(plan!);
    expect((spec.encoding as { x: { sort: unknown } }).x.sort).toBeNull();
    expect(JSON.stringify(spec)).not.toContain('legend');
  });

  it('the columns may come in either order', () => {
    expect(planChart([col('amt', 'Float64'), col('region', 'Utf8')], [[1.5, 'n'], [2, 's']])?.kind).toBe('bar');
  });

  it('a date and a numeric is a line', () => {
    expect(planChart([col('day', 'Date32<DAY>'), col('n', 'Int64')], [[1, 2], [3, 4]])?.kind).toBe('line');
    expect(planChart([col('at', 'Timestamp<MICROSECOND>'), col('x', 'Decimal[38e-2]')], [[1, 2], [3, 4]])?.kind).toBe('line');
  });

  it('anything else is no chart, not an error', () => {
    expect(planChart([col('a', 'Int64'), col('b', 'Float64')], [[1, 2]])).toBeNull();
    expect(planChart([col('a', 'Utf8'), col('b', 'Utf8')], [['x', 'y']])).toBeNull();
    expect(planChart([col('a', 'Utf8'), col('b', 'Int64'), col('c', 'Int64')], [['x', 1, 2]])).toBeNull();
    expect(planChart([col('a', 'Utf8')], [['x']])).toBeNull();
    expect(planChart([col('a', 'Utf8'), col('b', 'Int64')], [['only', 1]])).toBeNull();
  });

  it('too many bars is no chart, and the rows are capped', () => {
    const many = Array.from({ length: MAX_BARS + 1 }, (_, i) => [`c${i}`, i]);
    expect(planChart([col('c', 'Utf8'), col('n', 'Int64')], many)).toBeNull();
    const rows = Array.from({ length: CHART_ROWS + 100 }, (_, i) => [i, i % 3]);
    const plan = planChart([col('day', 'Date32<DAY>'), col('n', 'Int64')], rows);
    expect(plan?.values).toHaveLength(CHART_ROWS);
  });
});

describe('the gauge scatter (real-data R8)', () => {
  it('plots on log axes with the diagonal and colours by verdict with a legend', async () => {
    const { scatterSpec } = await import('./chart');
    const spec = scatterSpec([{ est: 2, actual: 1.8, verdict: 'green', when: '10:41' }, { est: 90, actual: 246, verdict: 'yellow', when: '10:22' }]) as { layer: Record<string, unknown>[] };
    expect(spec.layer).toHaveLength(2);
    const points = spec.layer[1] as { encoding: { x: { scale: { type: string; domain: number[] } }; color: { scale: { domain: string[] }; legend: unknown } } };
    expect(points.encoding.x.scale.type).toBe('log');
    expect(points.encoding.x.scale.domain[0]).toBeLessThan(1.8);
    expect(points.encoding.x.scale.domain[1]).toBeGreaterThan(246);
    expect(points.encoding.color.scale.domain).toEqual(['green', 'yellow', 'red']);
    expect(points.encoding.color.legend).toBeTruthy();
  });
});
