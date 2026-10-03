// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions L1: the Lineage screen draws every node and edge from GET /lineage, colours a
// model by its state, and a click opens the detail — a model on the Models screen, a
// table on the Tables screen. The core is a stubbed fetch here; the Playwright spec draws
// the seventh sidecar's project.

import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LineageGraph } from '../lib/api';
import { Lineage, nodeCaption } from './Lineage';

const session = { port: 1, token: 't', pid: 0, project: '/p', ready_ms: 1, initialised: null };

const g: LineageGraph = {
  nodes: [
    { name: 'orders', kind: 'table', model: false, state: null, state_reason: null, source: null, freshness: null },
    { name: 'stg', kind: 'view', model: true, state: 'fresh', state_reason: null, source: null, freshness: null },
    { name: 'by_customer', kind: 'table', model: true, state: 'upstream', state_reason: 'stg is out of date', source: null, freshness: null },
    { name: 'places', kind: 'table', model: false, state: null, state_reason: null, source: 's3://b/places/', freshness: null },
  ],
  edges: [{ from: 'orders', to: 'stg', via: 'source' }, { from: 'stg', to: 'by_customer', via: 'ref' }],
  compiled: false,
};

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('the Lineage screen', () => {
  it('draws the nodes and edges, colours the states, and a node opens its detail', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(g), { status: 200 })));
    const onOpenModel = vi.fn();
    const onOpenTable = vi.fn();
    render(<Lineage session={session} mode="technical" onOpenModel={onOpenModel} onOpenTable={onOpenTable} />);
    await waitFor(() => expect(screen.getByTestId('graph')).toBeTruthy());
    expect(screen.getByTestId('lineage-screen').textContent).toContain('4 nodes, 2 edges · 1 model out of date');
    expect(screen.getByTestId('node-by_customer').getAttribute('data-state')).toBe('upstream');
    expect(screen.getByTestId('node-by_customer').textContent).toContain('upstream · stg is out of date');
    expect(screen.getByTestId('node-stg').getAttribute('data-state')).toBe('fresh');
    expect(screen.getByTestId('node-places').textContent).toContain('attached');
    expect(screen.getByTestId('edge-orders-stg').getAttribute('class')).toBe('edge source');
    expect(screen.getByTestId('edge-stg-by_customer').getAttribute('class')).toBe('edge ref');
    // layers: orders and places at the left, stg next, by_customer last
    const x = (name: string) => Number(/translate\((\d+),/.exec(screen.getByTestId(`node-${name}`).getAttribute('transform') ?? '')?.[1]);
    expect(x('orders')).toBe(x('places'));
    expect(x('stg')).toBeGreaterThan(x('orders'));
    expect(x('by_customer')).toBeGreaterThan(x('stg'));
    fireEvent.click(screen.getByTestId('node-by_customer'));
    expect(onOpenModel).toHaveBeenCalledWith('by_customer');
    fireEvent.click(screen.getByTestId('node-orders'));
    expect(onOpenTable).toHaveBeenCalledWith('orders');
    expect(screen.getAllByTestId('command').map((c) => c.textContent)).toEqual(expect.arrayContaining([expect.stringContaining('querysolo lineage --all')]));
  });

  it("Simple mode's captions, and an empty project", async () => {
    expect(nodeCaption(g.nodes[1], 'simple')).toBe('Up to date');
    expect(nodeCaption(g.nodes[2], 'simple')).toBe('Out of date, because stg is');
    expect(nodeCaption(g.nodes[3], 'simple')).toBe('in a bucket');
    expect(nodeCaption(g.nodes[0], 'technical')).toBe('table');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ nodes: [], edges: [], compiled: false }), { status: 200 })));
    render(<Lineage session={session} mode="simple" onOpenModel={() => {}} onOpenTable={() => {}} />);
    await waitFor(() => expect(screen.getByTestId('no-nodes')).toBeTruthy());
    expect(screen.getByTestId('lineage-screen').textContent).toContain('Map');
  });
});
