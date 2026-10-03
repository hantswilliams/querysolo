// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The Lineage screen's layout (decisions L1): the whole project as layers left to right.
// A node's layer is one more than the deepest thing it reads (imported and attached
// tables, and anything that reads nothing, are layer 0); within a layer the nodes are
// ordered by the average row of what they read, so edges mostly run straight. No
// library: a project's graph is tens of nodes, and this is fifty lines that a test pins.

import type { LineageGraph, LineageNode } from './api';

export interface Placed {
  node: LineageNode;
  layer: number;
  row: number;
}

/** Layers left to right, each a list of node names in row order. */
export function layers(graph: LineageGraph): string[][] {
  const upstream = new Map<string, string[]>();
  for (const n of graph.nodes) upstream.set(n.name, []);
  for (const e of graph.edges) if (upstream.has(e.to) && upstream.has(e.from)) upstream.get(e.to)!.push(e.from);
  const depth = new Map<string, number>();
  const visiting = new Set<string>();
  const of = (name: string): number => {
    const known = depth.get(name);
    if (known !== undefined) return known;
    if (visiting.has(name)) return 0; // a cycle (a stale manifest could say anything) ends here
    visiting.add(name);
    const ups = upstream.get(name) ?? [];
    const d = ups.length === 0 ? 0 : 1 + Math.max(...ups.map(of));
    visiting.delete(name);
    depth.set(name, d);
    return d;
  };
  for (const n of graph.nodes) of(n.name);
  const count = Math.max(-1, ...Array.from(depth.values())) + 1;
  const out: string[][] = Array.from({ length: count }, () => []);
  for (const n of graph.nodes) out[depth.get(n.name)!].push(n.name);
  // rows: layer 0 by name; each later layer by the mean row of what it reads, then by name
  out[0]?.sort();
  const row = new Map<string, number>();
  out[0]?.forEach((name, i) => row.set(name, i));
  for (let l = 1; l < out.length; l++) {
    const key = (name: string) => {
      const rows = (upstream.get(name) ?? []).map((u) => row.get(u)).filter((r): r is number => r !== undefined);
      return rows.length ? rows.reduce((a, b) => a + b, 0) / rows.length : Number.POSITIVE_INFINITY;
    };
    out[l].sort((a, b) => key(a) - key(b) || a.localeCompare(b));
    out[l].forEach((name, i) => row.set(name, i));
  }
  return out;
}

/** Every node with its layer and row. */
export function place(graph: LineageGraph): Placed[] {
  const byName = new Map(graph.nodes.map((n) => [n.name, n]));
  return layers(graph).flatMap((names, layer) => names.map((name, row) => ({ node: byName.get(name)!, layer, row })));
}
