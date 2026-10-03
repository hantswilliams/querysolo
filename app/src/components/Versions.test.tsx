// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Versions step 3 gate (G6), against a stubbed core: the section lists a question's two
// versions newest first with the diff of the selected one, Gauge then is the estimate of
// that version's SQL, Restore posts the id and the list grows to three, Simple mode is
// sentences and one button, and a model with refs says why "then" is not measured. The
// Playwright spec does the same against a real core and the eighth sidecar.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { PlannedModel, Version } from '../lib/api';
import { Versions } from './Versions';

const session = { port: 1, token: 't', pid: 0, project: '/p', ready_ms: 1, initialised: null };

const FIRST = 'select customer, sum(amt) as revenue from orders group by 1';
const SECOND = FIRST + ' order by 2 desc';
const file = (sql: string) => `-- Revenue by customer\n-- saved by querysolo on 2026-09-12\n${sql}\n`;

const v1: Version = {
  id: '1111111aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', when: new Date(Date.now() - 3600_000).toISOString(),
  author: 'Ada Lovelace <ada@example.com>', message: 'save question: Revenue by customer', sql_changed: true, checks_changed: true,
  diff: ['--- before', '+++ after', '@@ -0,0 +1,3 @@', '+-- Revenue by customer', '+-- saved by querysolo on 2026-09-12', `+${FIRST}`, ''].join('\n'),
};
const v2: Version = {
  id: '2222222bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb', when: new Date(Date.now() - 120_000).toISOString(),
  author: 'Ada Lovelace <ada@example.com>', message: 'update question: Revenue by customer', sql_changed: true, checks_changed: false,
  diff: ['--- before', '+++ after', '@@ -1,3 +1,3 @@', ' -- Revenue by customer', ' -- saved by querysolo on 2026-09-12', `-${FIRST}`, `+${SECOND}`, ''].join('\n'),
};
const v3: Version = { ...v1, id: '3333333ccccccccccccccccccccccccccccccccc', when: new Date().toISOString(), message: 'restore question: Revenue by customer to 1111111', checks_changed: false };

const question: Pick<PlannedModel, 'name' | 'path' | 'verdict' | 'words' | 'reason' | 'error' | 'est_wall_local'> = {
  name: 'revenue_by_customer', path: 'models/questions/revenue_by_customer.sql',
  verdict: 'green', words: 'Green — about 1 s', reason: 'reads 2.0 MB', error: null, est_wall_local: 1,
};

function stub(versionsByCall: Version[][], sqlOf: Record<string, string>, opts: { estimateWords?: string; git?: boolean } = {}) {
  const calls: { method: string; path: string; body?: unknown }[] = [];
  let listCalls = 0;
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const path = url.replace(/^.*\/api/, '');
    const method = init?.method ?? 'GET';
    calls.push({ method, path, body: init?.body ? JSON.parse(String(init.body)) : undefined });
    if (path === '/git') return new Response(JSON.stringify({ repository: opts.git !== false, branch: 'main', origin: null }), { status: 200 });
    if (path === '/versions/revenue_by_customer') {
      const list = versionsByCall[Math.min(listCalls++, versionsByCall.length - 1)];
      return new Response(JSON.stringify(list), { status: 200 });
    }
    if (path === '/versions/by_customer') return new Response(JSON.stringify([{ ...v1, message: 'run: by_customer changed', checks_changed: false }]), { status: 200 });
    if (path === '/versions/nothing') return new Response(JSON.stringify({ error: 'no_history', message: 'nothing.sql has no versions yet: it is not in the repository.' }), { status: 404 });
    const one = /^\/versions\/[^/]+\/([0-9a-f]+)$/.exec(path);
    if (one) return new Response(JSON.stringify({ name: 'revenue_by_customer', id: one[1], sql: sqlOf[one[1]] ?? '' }), { status: 200 });
    if (path === '/estimate') {
      const sql = (JSON.parse(String(init?.body)) as { sql: string }).sql;
      const words = opts.estimateWords ?? (sql.includes('order by') ? 'Green — about 2 s' : 'Green — about 1 s');
      return new Response(JSON.stringify({ verdict: 'green', words, reason: 'reads 2.0 MB', wall_local: sql.includes('order by') ? 2 : 1, bytes_scanned: 2e6 }), { status: 200 });
    }
    if (path === '/versions/revenue_by_customer/restore') return new Response(JSON.stringify({ name: 'revenue_by_customer', commit: v3.id, git: null }), { status: 200 });
    return new Response('{}', { status: 404 });
  }));
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe('the Versions section', () => {
  it('lists the versions newest first, draws the selected diff, and Gauge then is that version\'s estimate', async () => {
    const calls = stub([[v2, v1]], { [v2.id]: file(SECOND), [v1.id]: file(FIRST) });
    render(<Versions session={session} mode="technical" model={question} onRestored={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('version-list')).toBeTruthy());
    expect(screen.getByTestId('git-line').textContent).toBe('git · main · origin not set');
    const rows = screen.getAllByTestId(/^version-\d$/);
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringContaining('2222222'),
      expect.stringContaining('1111111'),
    ]);
    expect(rows[0].textContent).toContain('2 min ago');
    expect(rows[0].textContent).toContain('Ada Lovelace');
    expect(rows[0].textContent).toContain('update question: Revenue by customer');
    expect(rows[0].textContent).toContain('checks unchanged');
    expect(rows[1].textContent).toContain('checks changed');
    // the newest is selected: its diff, and Gauge then from its SQL
    expect(rows[0].className).toBe('on');
    expect(screen.getByTestId('diff-summary').textContent).toContain('2222222 against the version before: 1 line changed');
    const diff = screen.getByTestId('diff');
    expect(diff.querySelector('.add')?.textContent).toContain('order by 2 desc');
    expect(diff.querySelector('.del')?.textContent).toContain(FIRST);
    expect(diff.querySelectorAll('.ctx').length).toBe(2);
    await waitFor(() => expect(screen.getByTestId('gauge-then').textContent).toBe('Green — about 2 s · reads 2.0 MB'));
    expect(screen.getByTestId('gauge-now').textContent).toBe('Green — about 1 s · reads 2.0 MB');
    expect(calls.find((c) => c.path === '/estimate')?.body).toEqual({ sql: file(SECOND) });
    expect(screen.getByTestId('command').textContent).toContain('querysolo restore revenue_by_customer 2222222');
    // selecting the first: the file arriving, and its own estimate
    fireEvent.click(rows[1]);
    expect(screen.getByTestId('diff-summary').textContent).toContain('1111111 against the version before: 3 lines added');
    await waitFor(() => expect(screen.getByTestId('gauge-then').textContent).toBe('Green — about 1 s · reads 2.0 MB'));
    expect(screen.getByTestId('command').textContent).toContain('querysolo restore revenue_by_customer 1111111');
  });

  it('Restore this version posts the id, says the new version, re-reads the list and the plan', async () => {
    const calls = stub([[v2, v1], [v3, v2, v1]], { [v2.id]: file(SECOND), [v1.id]: file(FIRST), [v3.id]: file(FIRST) });
    const onRestored = vi.fn(async () => {});
    render(<Versions session={session} mode="technical" model={question} onRestored={onRestored} />);
    await waitFor(() => expect(screen.getByTestId('version-list')).toBeTruthy());
    fireEvent.click(screen.getByTestId('version-1'));
    fireEvent.click(screen.getByTestId('restore'));
    await waitFor(() => expect(screen.getByTestId('restored')).toBeTruthy());
    expect(calls.find((c) => c.path === '/versions/revenue_by_customer/restore')?.body).toEqual({ id: v1.id });
    expect(screen.getByTestId('restored').textContent).toBe('Restored 1111111 as version 3333333.');
    expect(screen.getAllByTestId(/^version-\d$/).length).toBe(3);
    expect(screen.getByTestId('version-0').textContent).toContain('restore question: Revenue by customer to 1111111');
    expect(screen.getByTestId('version-0').className).toBe('on');
    expect(onRestored).toHaveBeenCalledTimes(1);
  });

  it('Simple mode is sentences with no id, Then and Now as waits, and one button', async () => {
    stub([[v2, v1]], { [v2.id]: file(SECOND), [v1.id]: file(FIRST) });
    render(<Versions session={session} mode="simple" model={question} onRestored={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('version-list')).toBeTruthy());
    expect(screen.getByTestId('versions').textContent).toContain('History · 2');
    expect(screen.queryByTestId('git-line')).toBeNull();
    expect(screen.getByTestId('version-0').textContent).toBe('2 min ago · Ada Lovelace · Updated · 1 line changed');
    expect(screen.getByTestId('version-1').textContent).toBe('1 h ago · Ada Lovelace · Saved · checks changed');
    expect(screen.getByTestId('versions').textContent).not.toMatch(/[0-9a-f]{7}/);
    expect(screen.queryByTestId('diff')).toBeNull();
    expect(screen.queryByTestId('command')).toBeNull();
    await waitFor(() => expect(screen.getByTestId('gauge-then').textContent).toBe('Ready in about 2 s.'));
    expect(screen.getByTestId('gauge-now').textContent).toBe('Ready in about 1 s.');
    expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual(['Restore this version']);
  });

  it('a model with refs says Gauge then is not measured; a file with no versions says why', async () => {
    stub([[v2]], { [v1.id]: "select customer, sum(amt) as total from {{ ref('stg') }} group by 1\n" });
    const model = { ...question, name: 'by_customer', path: 'models/by_customer.sql' };
    const { unmount } = render(<Versions session={session} mode="technical" model={model} onRestored={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('gauge-then').textContent).toBe('not measured for a model with refs'));
    expect(screen.getByTestId('version-0').textContent).toContain('run: by_customer changed');
    unmount();
    render(<Versions session={session} mode="technical" model={{ ...question, name: 'nothing', path: 'models/nothing.sql' }} onRestored={async () => {}} />);
    await waitFor(() => expect(screen.getByTestId('no-versions')).toBeTruthy());
    expect(screen.getByTestId('no-versions').textContent).toContain('has no versions yet');
    expect(screen.queryByTestId('restore')).toBeNull();
  });
});
