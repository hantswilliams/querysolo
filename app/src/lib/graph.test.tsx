// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions L1: the Lineage screen's layout is pinned — a chain is three layers, a diamond
// puts its two middle nodes in one layer, an imported table is layer 0, rows follow what a
// node reads, and a cycle in a stale manifest does not loop.

import { describe, expect, it } from 'vitest';
import type { LineageGraph, LineageNode } from './api';
import { layers, place } from './graph';

const node = (name: string, over: Partial<LineageNode> = {}): LineageNode => ({
  name, kind: 'table', model: false, state: null, state_reason: null, source: null, freshness: null, ...over,
});
const graph = (names: string[], edges: [string, string][]): LineageGraph => ({
  nodes: names.map((n) => node(n)),
  edges: edges.map(([from, to]) => ({ from, to, via: 'ref' as const })),
  compiled: false,
});

describe('the lineage layout', () => {
  it('layers a chain, a diamond and a lone table', () => {
    expect(layers(graph(['src', 'stg', 'by_c', 'top'], [['src', 'stg'], ['stg', 'by_c'], ['by_c', 'top']]))).toEqual([['src'], ['stg'], ['by_c'], ['top']]);
    expect(layers(graph(['src', 'a', 'b', 'join'], [['src', 'a'], ['src', 'b'], ['a', 'join'], ['b', 'join']]))).toEqual([['src'], ['a', 'b'], ['join']]);
    expect(layers(graph(['lonely', 'src', 'stg'], [['src', 'stg']]))).toEqual([['lonely', 'src'], ['stg']]);
    expect(layers(graph([], []))).toEqual([]);
  });

  it('puts a node in the layer after the deepest thing it reads, and orders rows by what they read', () => {
    // total reads src directly and by_c reads stg: total sits in layer 1 next to stg, not after by_c
    const g = graph(['src', 'other', 'stg', 'by_c', 'total', 'from_other'], [['src', 'stg'], ['stg', 'by_c'], ['src', 'total'], ['other', 'from_other']]);
    expect(layers(g)).toEqual([['other', 'src'], ['from_other', 'stg', 'total'], ['by_c']]);
    const placed = place(g);
    expect(placed.find((p) => p.node.name === 'from_other')).toMatchObject({ layer: 1, row: 0 });
    expect(placed.find((p) => p.node.name === 'by_c')).toMatchObject({ layer: 2, row: 0 });
  });

  it('a cycle ends where it started rather than looping', () => {
    expect(layers(graph(['a', 'b'], [['a', 'b'], ['b', 'a']])).flat().sort()).toEqual(['a', 'b']);
  });
});
