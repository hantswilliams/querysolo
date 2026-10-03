// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Real-data step 6 gate: the Models screen lists the plan with a verdict per model, the
// detail shows the compiled SQL, lineage, tests and last run; Simple mode shows the same as
// cards with checks; a Red model's run is refused until Run anyway. The core is a stubbed
// fetch here; the Playwright spec runs it against the real one.

import { cleanup as cleanupAll, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { PlannedModel, RunReport } from '../lib/api';
import { Models } from './Models';

const session = { port: 1, token: 't', pid: 0, project: '/p', ready_ms: 1, initialised: null };

const stg: PlannedModel = {
  name: 'stg', unique_id: 'model.demo.stg', materialized: 'view', depends_on: [],
  compiled_sql: 'select * from "querysolo"."main"."orders" where quantity > 0',
  verdict: 'green', words: 'Green — about 1 s', reason: 'reads 2.0 MB', est_wall_local: 1, est_bytes: 2_000_000, error: null,
  description: 'Orders with a quantity.', path: 'models/stg.sql',
  tests: [
    { name: 'not_null_stg_order_id', kind: 'not_null', column: 'order_id', unique_id: 'test.demo.a' },
    { name: 'unique_stg_order_id', kind: 'unique', column: 'order_id', unique_id: 'test.demo.b' },
  ],
  last_run: { ts: new Date(Date.now() - 120_000).toISOString(), ok: true, seconds: 0.4, verdict: 'green', error: null },
  state: 'fresh', state_reason: null, state_since: null,
};
const agg: PlannedModel = {
  ...stg, name: 'agg', unique_id: 'model.demo.agg', materialized: 'table', depends_on: ['model.demo.stg'],
  compiled_sql: 'select customer, sum(amount) as total from "memory"."main"."stg" group by 1',
  verdict: 'red', words: 'Red — needs more machine', reason: 'peak memory 30 GB', est_wall_local: 900, est_bytes: 40e9,
  description: '', tests: [], last_run: null, state: 'never', state_reason: 'never built', state_since: null,
};

function stub(models: PlannedModel[], run: (body: { select: string[]; run_anyway: boolean; stale: boolean }) => Response) {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(`${init?.method ?? 'GET'} ${url.replace(/^.*\/api/, '')}`);
    if (url.endsWith('/run/plan')) return new Response(JSON.stringify(models), { status: 200 });
    if (url.endsWith('/run')) return run(JSON.parse(String(init?.body)));
    const lineage = /\/lineage\/([^/?]+)/.exec(url);
    if (lineage) {
      // G8: stg reads orders (an imported table) and feeds agg; agg reads stg by ref
      const name = decodeURIComponent(lineage[1]);
      const body = name === 'stg'
        ? { name, kind: 'view', upstream: [{ name: 'orders', kind: 'table', via: 'sql', depth: 1 }], downstream: [{ name: 'agg', kind: 'model', via: 'ref', depth: 1 }], built_by: 'stg', last_built: null, compiled: false }
        : { name, kind: 'model', upstream: [{ name: 'stg', kind: 'view', via: 'ref', depth: 1 }], downstream: [], built_by: null, last_built: null, compiled: false };
      return new Response(JSON.stringify(body), { status: 200 });
    }
    return new Response('{}', { status: 404 });
  }));
  return calls;
}

const okReport = (names: string[]): RunReport => ({
  models: [], results: names.map((n) => ({ name: n, status: 'success', seconds: 0.5, message: null })),
  views_recorded: names.filter((n) => n === 'stg'), views_dropped: [], seconds: 1.2, ok: true,
});

afterEach(() => vi.unstubAllGlobals());

describe('the Models screen', () => {
  it('lists the plan, shows a model, and Run this is querysolo run <model>', async () => {
    const calls = stub([stg, agg], (b) => new Response(JSON.stringify(okReport(b.select.length ? b.select : ['stg', 'agg'])), { status: 200 }));
    const onChanged = vi.fn(async () => {});
    const onOpenTable = vi.fn();
    render(<Models session={session} mode="technical" tables={[]} onChanged={onChanged} onOpenTable={onOpenTable} />);
    await waitFor(() => expect(screen.getByTestId('dag')).toBeTruthy());
    expect(screen.getByTestId('models-screen').textContent).toContain('2 models · 1 Red');
    expect(screen.getByTestId('model-stg').textContent).toContain('Green');
    expect(screen.getByTestId('model-agg').textContent).toContain('Red');
    // the first model is selected: its SQL, lineage, tests, last run
    expect(screen.getByTestId('compiled-sql').textContent).toContain('quantity > 0');
    await waitFor(() => expect(screen.getByTestId('reads-from').textContent).toBe('orders (table, named in the SQL)'));
    expect(screen.getByTestId('feeds').textContent).toBe('agg (model, ref)');
    expect(screen.getByTestId('tests').textContent).toContain('not_null(order_id)');
    expect(screen.getByTestId('tests').textContent).toContain('unique(order_id)');
    expect(screen.getByTestId('last-run').textContent).toContain('2 min ago, took');
    expect(screen.getByTestId('sentence').textContent).toBe('Green — about 1 s');
    fireEvent.click(screen.getByTestId('model-agg'));
    await waitFor(() => expect(screen.getByTestId('reads-from').textContent).toBe('stg (view, ref)'));
    expect(screen.getByTestId('feeds').textContent).toBe('nothing');
    expect(screen.getByTestId('tests').textContent).toContain('none in schema.yml');
    expect(screen.getAllByTestId('command').map((c) => c.textContent)).toEqual(expect.arrayContaining([
      expect.stringContaining('querysolo run'),
      expect.stringContaining('querysolo run agg'),
    ]));
    // a lineage name is a link: a model of this project is selected here, an imported table opens on the Tables screen
    fireEvent.click(screen.getByTestId('lineage-stg'));
    expect(screen.getByTestId('model-stg').className).toBe('on');
    await waitFor(() => expect(screen.getByTestId('feeds').textContent).toBe('agg (model, ref)'));
    fireEvent.click(screen.getByTestId('lineage-orders'));
    expect(onOpenTable).toHaveBeenCalledWith('orders');
    // Run this on the Green one posts its selection and re-plans
    fireEvent.click(screen.getByTestId('model-stg'));
    fireEvent.click(screen.getByTestId('run-this'));
    await waitFor(() => expect(screen.getByTestId('run-report')).toBeTruthy());
    expect(calls).toContain('POST /run');
    expect(screen.getByTestId('run-report').textContent).toContain('1 model built in 1.2 s. Views in the catalog: stg.');
    expect(onChanged).toHaveBeenCalled();
    expect(calls.filter((c) => c === 'GET /run/plan').length).toBe(2);
  });

  it('a Red model refuses the run until Run anyway', async () => {
    const posts: { select: string[]; run_anyway: boolean; stale: boolean }[] = [];
    stub([stg, agg], (b) => {
      posts.push(b);
      if (!b.run_anyway) return new Response(JSON.stringify({ error: 'red_refused', message: '1 model(s) need more machine: agg. `--run-anyway` runs the DAG here regardless.' }), { status: 409 });
      return new Response(JSON.stringify(okReport(['stg', 'agg'])), { status: 200 });
    });
    render(<Models session={session} mode="technical" tables={[]} onChanged={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('dag')).toBeTruthy());
    expect(screen.getByTestId('red-note').textContent).toContain('--run-anyway');
    fireEvent.click(screen.getByTestId('run-all'));
    await waitFor(() => expect(screen.getByTestId('refusal')).toBeTruthy());
    expect(screen.getByTestId('refusal').textContent).toContain('need more machine: agg');
    expect(screen.getByTestId('refusal').textContent).toContain('querysolo run --run-anyway');
    fireEvent.click(screen.getByTestId('run-anyway'));
    await waitFor(() => expect(screen.getByTestId('run-report')).toBeTruthy());
    expect(posts).toEqual([{ select: [], burst: 'never', run_anyway: false, stale: false }, { select: [], burst: 'never', run_anyway: true, stale: false }]);
    expect(screen.queryByTestId('refusal')).toBeNull();
  });

  it('the state (V3) is on the DAG and the detail, and Run what changed is querysolo run --stale', async () => {
    const posts: { select: string[]; run_anyway: boolean; stale: boolean }[] = [];
    const orders = new Date(Date.now() - 7200_000).toISOString();
    const stale: PlannedModel = {
      ...agg, name: 'late', unique_id: 'model.demo.late', verdict: 'green', state: 'upstream', state_reason: 'orders changed', state_since: orders,
      state_changes: [{ name: 'orders', operation: 'append', added_rows: 1200, deleted_rows: null, timestamp: orders }],
    };
    stub([stg, agg, stale], (b) => {
      posts.push(b);
      return new Response(JSON.stringify({ ...okReport(b.stale ? ['agg', 'late'] : ['stg', 'agg', 'late']), selected: b.stale ? ['agg', 'late'] : null }), { status: 200 });
    });
    render(<Models session={session} mode="technical" tables={[]} onChanged={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('dag')).toBeTruthy());
    const states = screen.getByTestId('dag').querySelectorAll('td[data-testid="state"]');
    expect(Array.from(states).map((td) => td.textContent)).toEqual(['fresh', 'never', 'upstream']);
    expect(screen.getByTestId('state-sentence').textContent).toBe('fresh');
    fireEvent.click(screen.getByTestId('model-late'));
    const detail = within(screen.getByTestId('model-detail'));
    expect(detail.getByTestId('state-sentence').textContent).toContain('upstream · orders changed 2 h ago');
    // what changed is shown: the commits to orders since the run
    expect(detail.getByTestId('what-changed').textContent).toBe('orders · append +1,200 rows · 2 h ago');
    // and the review lists every stale model, in plan order, with the same evidence
    const review = screen.getByTestId('review');
    expect(review.textContent).toContain('Out of date · 2 models · Run what changed builds them in this order');
    expect(Array.from(review.querySelectorAll('article')).map((a) => a.getAttribute('data-testid'))).toEqual(['review-agg', 'review-late']);
    expect(within(screen.getByTestId('review-agg')).getByText('never · never built')).toBeTruthy();
    expect(within(screen.getByTestId('review-late')).getByTestId('what-changed').textContent).toBe('orders · append +1,200 rows · 2 h ago');
    const button = screen.getByTestId('run-stale');
    expect(button.textContent).toBe('Run what changed (2)');
    expect(screen.getAllByTestId('command').map((c) => c.textContent)).toEqual(expect.arrayContaining([expect.stringContaining('querysolo run --stale')]));
    fireEvent.click(button);
    await waitFor(() => expect(screen.getByTestId('run-report')).toBeTruthy());
    expect(posts).toEqual([{ select: [], burst: 'never', run_anyway: false, stale: true }]);
    expect(screen.getByTestId('run-report').textContent).toContain('2 models built in');
  });

  it('shows the SQL diff behind edited, and the model blamed behind upstream is a link', async () => {
    const edited: PlannedModel = {
      ...stg, state: 'edited', state_reason: 'the SQL changed since the last run',
      state_diff: '--- last run\n+++ now\n@@ -1 +1 @@\n-select * from "querysolo"."main"."orders" where quantity > 0\n+select * from "querysolo"."main"."orders" where quantity > 1',
    };
    const blames: PlannedModel = { ...agg, state: 'upstream', state_reason: 'stg is out of date', state_since: null };
    stub([edited, blames], () => new Response('{}', { status: 500 }));
    render(<Models session={session} mode="technical" tables={[]} onChanged={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('dag')).toBeTruthy());
    const detail = () => within(screen.getByTestId('model-detail'));
    expect(detail().getByTestId('state-sentence').textContent).toContain('edited · the SQL changed since the last run');
    expect(detail().getByTestId('what-changed').textContent).toContain('1 line changed');
    const diff = detail().getByTestId('state-diff');
    expect(diff.querySelector('.del')?.textContent).toContain('quantity > 0');
    expect(diff.querySelector('.add')?.textContent).toContain('quantity > 1');
    fireEvent.click(screen.getByTestId('model-agg'));
    expect(detail().getByTestId('state-sentence').textContent).toBe('upstream · stg is out of date');
    expect(detail().queryByTestId('what-changed')).toBeNull();
    fireEvent.click(detail().getByTestId('state-link-stg'));
    expect(screen.getByTestId('model-stg').className).toBe('on');
    // the review has both, and the blamed name there is a link too
    expect(within(screen.getByTestId('review-agg')).getByTestId('state-link-stg')).toBeTruthy();
    expect(within(screen.getByTestId('review-stg')).getByTestId('state-diff').querySelector('.add')?.textContent).toContain('quantity > 1');
  });

  it('folds a whole-SQL diff to its changes and shows the whole on request', async () => {
    const before = ['select', '  a,', '  b,', '  c,', '  d,', '  e,', '  f,', '  g', 'from t', 'where a > 0'];
    const after = [...before.slice(0, 9), 'where a > 1'];
    const diff = ['--- last run', '+++ now', '@@ -1,10 +1,10 @@', ...before.slice(0, 9).map((l) => ` ${l}`), `-${before[9]}`, `+${after[9]}`].join('\n');
    const edited: PlannedModel = { ...stg, state: 'edited', state_reason: 'the SQL changed since the last run', state_diff: diff };
    stub([edited], () => new Response('{}', { status: 500 }));
    render(<Models session={session} mode="technical" tables={[]} onChanged={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('dag')).toBeTruthy());
    const pre = within(screen.getByTestId('model-detail')).getByTestId('state-diff');
    const texts = () => Array.from(pre.querySelectorAll('span')).map((s) => s.textContent?.trimEnd());
    expect(texts()).toEqual(['--- last run', '+++ now', '@@ -1,10 +1,10 @@', '…', '  f,', '  g', 'from t', 'where a > 0', 'where a > 1']);
    fireEvent.click(within(screen.getByTestId('model-detail')).getByTestId('diff-whole'));
    expect(texts()).toHaveLength(3 + 9 + 2);
    expect(texts()[3]).toBe('select');
    fireEvent.click(within(screen.getByTestId('model-detail')).getByTestId('diff-whole'));
    expect(texts()[3]).toBe('…');
  });

  it('says so when nothing is stale, and the button is off', async () => {
    const fresh = { ...agg, state: 'fresh' as const, state_reason: null };
    stub([stg, fresh], (b) => new Response(JSON.stringify({ ...okReport([]), selected: b.stale ? [] : null }), { status: 200 }));
    render(<Models session={session} mode="technical" tables={[]} onChanged={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('dag')).toBeTruthy());
    const button = screen.getByTestId('run-stale') as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(button.textContent).toBe('Run what changed');
  });

  it('Simple mode is cards: questions, checks, the wait as a sentence, Refresh', async () => {
    stub([stg, agg], () => new Response(JSON.stringify(okReport(['stg'])), { status: 200 }));
    const fresh = new Date(Date.now() - 3600_000 * 5).toISOString();
    render(<Models session={session} mode="simple" tables={[{ name: 'stg', rows: 0, bytes: 0, columns: [], location: '', snapshot_id: null, freshness: fresh, kind: 'view' }]} onChanged={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('cards')).toBeTruthy());
    expect(screen.getByTestId('models-screen').textContent).toContain('2 questions · 1 too big for this machine');
    const card = screen.getByTestId('card-stg');
    expect(card.textContent).toContain('answered live · last refreshed 5 h ago');
    expect(card.textContent).toContain('Orders with a quantity.');
    expect(card.textContent).toContain('Ready in about 1 s.');
    expect(card.textContent).toContain('2 checks: order_id is never empty; order_id is never repeated');
    expect(screen.getByTestId('card-agg').textContent).toContain('Too big for this machine right now.');
    expect(screen.getByTestId('card-agg').textContent).toContain('no checks');
    // the card's state sentence (V3), in Simple's words
    expect(card.querySelector('[data-testid="state"]')?.textContent).toBe('Up to date.');
    expect(screen.getByTestId('card-agg').querySelector('[data-testid="state"]')?.textContent).toBe('Never refreshed.');
    expect(screen.getByTestId('run-stale').textContent).toBe('Refresh what changed (1)');
    expect(screen.getByTestId('run-all').textContent).toBe('Refresh all');
    expect(screen.getByTestId('refresh-stg').textContent).toBe('Refresh');
    expect(screen.queryByTestId('compiled-sql')).toBeNull();
    expect(screen.getByTestId('models-screen').textContent).not.toContain('Green');
    fireEvent.click(screen.getByTestId('refresh-stg'));
    await waitFor(() => expect(screen.getByTestId('run-report')).toBeTruthy());
    expect(screen.getByTestId('run-report').textContent).toContain('1 question built in 1.2 s. Answered live: stg.');
  });

  it('See the answer (Q1) hands the rows to the workspace; a question never refreshed is refreshed first', async () => {
    // the plan after a run says agg is built now: the stub answers the second plan with it fresh
    let plans = 0;
    const models = [stg, agg];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/run/plan')) {
        plans += 1;
        const body = url.includes('select=agg') ? [{ ...agg, state: 'fresh' as const }] : models;
        return new Response(JSON.stringify(body), { status: 200 });
      }
      if (url.endsWith('/run')) return new Response(JSON.stringify(okReport(['agg'])), { status: 200 });
      return new Response('{}', { status: 404 });
    }));
    const onAnswer = vi.fn();
    render(<Models session={session} mode="simple" tables={[]} onChanged={async () => {}} onAnswer={onAnswer} />);
    await waitFor(() => expect(screen.getByTestId('cards')).toBeTruthy());
    expect(screen.getByTestId('answer-stg').textContent).toBe('See the answer');
    expect(screen.getByTestId('answer-agg').textContent).toBe('Refresh, then see the answer');
    fireEvent.click(screen.getByTestId('answer-stg'));
    expect(onAnswer).toHaveBeenCalledWith('stg');
    // never refreshed: the run, then a plan of that one model, then the rows
    fireEvent.click(screen.getByTestId('answer-agg'));
    await waitFor(() => expect(onAnswer).toHaveBeenCalledWith('agg'));
    expect(plans).toBeGreaterThanOrEqual(2);
    // Technical: the detail's footer says Rows
    cleanupAll();
    stub([stg, agg], () => new Response('{}', { status: 200 }));
    render(<Models session={session} mode="technical" tables={[]} onChanged={async () => {}} onAnswer={onAnswer} />);
    await waitFor(() => expect(screen.getByTestId('model-detail')).toBeTruthy());
    expect(screen.getByTestId('answer-stg').textContent).toBe('Rows');
    fireEvent.click(screen.getByTestId('answer-stg'));
    expect(onAnswer).toHaveBeenLastCalledWith('stg');
  });

  it('says when the plan failed, in the plan\'s own words', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'dbt', message: 'dbt is not installed: `pip install \'querysolo[dbt]\'`' }), { status: 400 })));
    render(<Models session={session} mode="technical" tables={[]} onChanged={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('models-error')).toBeTruthy());
    expect(screen.getByTestId('models-error').textContent).toContain('dbt is not installed');
    expect(screen.getByTestId('models-error').textContent).toContain('querysolo run --plan');
    expect(screen.queryByTestId('no-models')).toBeNull();
  });
});
