// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Versions brief G8, step 4: the lineage rows say what a table reads from and what it
// feeds, each name a link that opens that detail; Technical says how each edge is known,
// Simple says only the names; the rows sit inside the table detail; an unknown answer says
// so rather than failing the detail. The core is a stubbed fetch here; the Playwright spec
// runs the lines against the real one.

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Lineage, TableDescription } from '../lib/api';
import { edgeLabel, LineageRows } from './Lineage';
import { TableDetail } from './TableDetail';

const session = { port: 1, token: 't', pid: 0, project: '/p', ready_ms: 1, initialised: null };

const orders: Lineage = {
  name: 'orders',
  kind: 'table',
  upstream: [],
  downstream: [
    { name: 'stg_orders', kind: 'view', via: 'sql', depth: 1 },
    { name: 'orders_v', kind: 'view', via: 'view', depth: 1 },
    { name: 'top', kind: 'model', via: 'ref', depth: 1 },
  ],
  built_by: 'imported',
  last_built: new Date().toISOString(),
  compiled: false,
};

function stub(answer: (name: string) => Response) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const m = /\/lineage\/([^/?]+)/.exec(url);
    if (/\/changes\?/.test(url)) return new Response('[]', { status: 200 }); // the Recent strip (L2) beside the rows
    return m ? answer(decodeURIComponent(m[1])) : new Response('{}', { status: 404 });
  }));
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('the lineage rows', () => {
  it('list what it reads and what reads it, how each is known, and a name is a link', async () => {
    stub(() => new Response(JSON.stringify(orders), { status: 200 }));
    const onOpen = vi.fn();
    render(<dl><LineageRows session={session} name="orders" mode="technical" onOpen={onOpen} /></dl>);
    await waitFor(() => expect(screen.getByTestId('upstream')).toBeTruthy());
    expect(screen.getByTestId('reads-from').textContent).toBe('nothing');
    expect(screen.getByTestId('feeds').textContent).toBe("stg_orders (view, named in the SQL) · orders_v (view, the view's SQL) · top (model, ref)");
    fireEvent.click(screen.getByTestId('lineage-top'));
    expect(onOpen).toHaveBeenCalledWith('top', 'model');
    fireEvent.click(screen.getByTestId('lineage-orders_v'));
    expect(onOpen).toHaveBeenCalledWith('orders_v', 'view');
  });

  it('Simple mode says the names only', async () => {
    stub(() => new Response(JSON.stringify(orders), { status: 200 }));
    render(<dl><LineageRows session={session} name="orders" mode="simple" onOpen={() => {}} /></dl>);
    await waitFor(() => expect(screen.getByTestId('feeds').textContent).toBe('stg_orders · orders_v · top'));
    expect(edgeLabel(orders.downstream[0], 'simple')).toBe('stg_orders');
    expect(edgeLabel(orders.downstream[0], 'technical')).toBe('stg_orders (view, named in the SQL)');
  });

  it('an answer the core cannot give (dbt failed to compile) is said, not thrown', async () => {
    stub(() => new Response(JSON.stringify({ error: 'dbt', message: 'Compilation Error in model top' }), { status: 400 }));
    render(<dl><LineageRows session={session} name="orders" onOpen={() => {}} /></dl>);
    await waitFor(() => expect(screen.getByTestId('reads-from').textContent).toContain('not known: '));
    expect(screen.getByTestId('reads-from').textContent).toContain('Compilation Error in model top');
    expect(screen.getByTestId('feeds').textContent).toBe('not known');
  });

  it('sit in the table detail when it is given a session, after Format', async () => {
    stub(() => new Response(JSON.stringify(orders), { status: 200 }));
    const table: TableDescription = {
      name: 'orders', rows: 200, bytes: 12_000, columns: [['id', 'long']], location: 'file:///p/warehouse/main/orders',
      snapshot_id: 2, freshness: new Date().toISOString(), source: null, public: false, partitioning: 'unpartitioned',
      expirable_snapshots: 0, reclaimable_bytes: 0, keep_days: 7, last_commit: {}, snapshots: 1, format_version: 2, snapshot_list: [],
    };
    const noop = () => {};
    const onOpen = vi.fn();
    render(<TableDetail table={table} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} session={session} onOpen={onOpen} />);
    await waitFor(() => expect(screen.getByTestId('feeds').textContent).toContain('stg_orders'));
    const terms = Array.from(screen.getByTestId('detail').querySelectorAll('dl.facts dt')).map((d) => d.textContent);
    expect(terms).toEqual(['Where', 'Partitioning', 'Last written', 'Format', 'Reads from', 'Feeds', 'Recent']);
    fireEvent.click(screen.getByTestId('lineage-stg_orders'));
    expect(onOpen).toHaveBeenCalledWith('stg_orders', 'view');
    // without a session (the preview panel's tests, an older caller) there are no rows and no fetch
    cleanup();
    render(<TableDetail table={table} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} />);
    expect(screen.queryByTestId('reads-from')).toBeNull();
  });
});
