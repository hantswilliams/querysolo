// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions L2: the Changes screen lists the feed from GET /changes newest first, each
// entry a sentence with a link to its detail; the filter is the CLI's name argument; the
// Recent strip on a detail reads the same route with a name. The core is a stubbed fetch.

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Change } from '../lib/api';
import { Recent } from '../components/Recent';
import { Changes } from './Changes';

const session = { port: 1, token: 't', pid: 0, project: '/p', ready_ms: 1, initialised: null };

const base: Change = {
  when: new Date(Date.now() - 120_000).toISOString(), kind: 'snapshot', name: 'orders', target: 'table',
  operation: 'append', snapshot_id: 3, added_rows: 1200, deleted_rows: null, affects: ['stg'],
  ok: null, seconds: null, verdict: null, error: null, id: null, author: null, message: null, names: [],
};
const feed: Change[] = [
  base,
  { ...base, when: new Date(Date.now() - 3_600_000).toISOString(), kind: 'version', name: 'total', target: 'question', id: 'abc1234', author: 'Ada Lovelace <ada@x>', message: 'save question: Total', names: ['total'], affects: [] },
  { ...base, when: new Date(Date.now() - 7_200_000).toISOString(), kind: 'run', name: 'by_c', target: 'model', ok: true, seconds: 1.2, verdict: 'green', affects: [] },
  { ...base, when: new Date(Date.now() - 8_000_000).toISOString(), kind: 'version', name: null, target: 'project', id: 'def5678', author: 'hants', message: 'run: by_c, stg changed', names: ['by_c', 'stg'], affects: [] },
];

const stub = () => {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    calls.push(url);
    const name = new URL(url).searchParams.get('name');
    const body = name ? feed.filter((c) => c.name === name || c.names.includes(name)) : feed;
    return new Response(JSON.stringify(body), { status: 200 });
  }));
  return calls;
};

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('the Changes screen', () => {
  it('lists the feed newest first with a link each, and the filter is the name argument', async () => {
    const calls = stub();
    const onOpenModel = vi.fn();
    const onOpenTable = vi.fn();
    render(<Changes session={session} mode="technical" onOpenModel={onOpenModel} onOpenTable={onOpenTable} />);
    await waitFor(() => expect(screen.getByTestId('feed')).toBeTruthy());
    expect(calls[0]).toContain('/api/changes?last=100');
    expect(screen.getByTestId('changes-screen').textContent).toContain('4 entries');
    const entries = screen.getAllByTestId(/^entry-/);
    expect(entries.map((e) => e.getAttribute('data-testid'))).toEqual(['entry-snapshot', 'entry-version', 'entry-run', 'entry-version']);
    expect(entries[0].textContent).toContain('2 min ago');
    expect(entries[0].textContent).toContain('orders: append +1,200 rows · made out of date: stg');
    expect(entries[1].textContent).toContain('save question: Total · Ada Lovelace');
    expect(entries[2].textContent).toContain('by_c built in 1.2 s, Green');
    expect(entries[3].textContent).toContain('run: by_c, stg changed · hants');
    fireEvent.click(screen.getByTestId('open-orders'));
    expect(onOpenTable).toHaveBeenCalledWith('orders');
    fireEvent.click(screen.getByTestId('open-total'));
    expect(onOpenModel).toHaveBeenCalledWith('total');
    expect(screen.getAllByTestId('open-stg')).toHaveLength(1); // the run-time version's second file
    expect(screen.getAllByTestId('command').some((c) => c.textContent?.includes('querysolo changes --last 100'))).toBe(true);

    fireEvent.change(screen.getByTestId('changes-filter'), { target: { value: 'total' } });
    await waitFor(() => expect(screen.getByTestId('changes-screen').textContent).toContain('1 entry about total'));
    expect(calls.at(-1)).toContain('name=total');
    expect(screen.getAllByTestId('command').some((c) => c.textContent?.includes('querysolo changes total --last 100'))).toBe(true);
    fireEvent.change(screen.getByTestId('changes-filter'), { target: { value: 'nowhere' } });
    await waitFor(() => expect(screen.getByTestId('no-changes').textContent).toBe('Nothing about nowhere yet.'));
  });

  it("Simple mode's words, and arriving with a name", async () => {
    stub();
    render(<Changes session={session} mode="simple" name="by_c" onOpenModel={() => {}} onOpenTable={() => {}} />);
    await waitFor(() => expect(screen.getByTestId('feed')).toBeTruthy());
    expect((screen.getByTestId('changes-filter') as HTMLInputElement).value).toBe('by_c');
    expect(screen.getByTestId('changes-screen').textContent).toContain('Recent');
    const entries = screen.getAllByTestId(/^entry-/);
    expect(entries).toHaveLength(2);
    expect(entries[0].textContent).toContain('refresh');
    expect(entries[0].textContent).toContain('by_c refreshed in 1.2 s');
    expect(entries[1].textContent).toContain('by_c, stg changed before a refresh · hants');
  });

  it('the Recent strip on a detail reads the feed for one name and links to the screen', async () => {
    const calls = stub();
    const onMore = vi.fn();
    render(<dl><Recent session={session} name="orders" mode="simple" onMore={onMore} /></dl>);
    await waitFor(() => expect(screen.getByTestId('recent-snapshot')).toBeTruthy());
    expect(calls[0]).toContain('/api/changes?last=5&name=orders');
    expect(screen.getByTestId('recent').textContent).toContain('2 min ago orders: 1,200 rows added · 1 question needs refreshing: stg');
    fireEvent.click(screen.getByTestId('recent-more'));
    expect(onMore).toHaveBeenCalledWith('orders');
    cleanup();
    vi.stubGlobal('fetch', vi.fn(async () => new Response('[]', { status: 200 })));
    render(<dl><Recent session={session} name="fresh" /></dl>);
    await waitFor(() => expect(screen.getByTestId('recent').textContent).toContain('nothing recorded yet'));
    expect(screen.queryByTestId('recent-more')).toBeNull();
  });
});
