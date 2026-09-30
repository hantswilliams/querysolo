// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The Lineage screen (decisions L1): the whole project as a graph the app draws — every
// table, view and model a node in layers left to right, every edge how lineage knows it,
// a model coloured by its state. A node is a link to its detail: a model on the Models
// screen, a table or view on the Tables screen. `querysolo lineage --all` is the same graph
// as text; nothing here does what the terminal cannot.

import { useEffect, useState } from 'react';
import { Api, type LineageGraph, type LineageNode } from '../lib/api';
import { lineageAllCommand } from '../lib/command';
import { place, type Placed } from '../lib/graph';
import type { Session } from '../lib/session';
import { stateSentence, words, type Mode } from '../lib/vocabulary';
import { Command } from '../components/Command';
import { VIA_WORDS } from '../components/Lineage';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export interface LineageProps {
  session: Session;
  mode: Mode;
  /** A model of the project: the Models screen, with it selected. */
  onOpenModel: (name: string) => void;
  /** A table or a view: the Tables screen, with its detail open. */
  onOpenTable: (name: string) => void;
  /** Changes when the project changed (a run, an import): the graph is read again. */
  refreshKey?: string | number | null;
}

export const COLUMN = 220;
export const ROW = 64;
export const NODE_W = 168;
export const NODE_H = 42;
const PAD = 24;

/** What a node says under its name: its kind, or its state for a model. */
export function nodeCaption(n: LineageNode, mode: Mode): string {
  const w = words(mode);
  if (n.model && n.state) return stateSentence({ state: n.state, state_reason: n.state_reason, state_since: null }, mode).replace(/\.$/, '');
  if (n.source) return mode === 'simple' ? 'in a bucket' : 'attached';
  if (n.kind === 'view') return mode === 'simple' ? 'answered live' : 'view';
  return mode === 'simple' ? w.table.replace('saved as a ', '') : n.kind;
}

function Node({ p, mode, onOpen }: { p: Placed; mode: Mode; onOpen: (n: LineageNode) => void }) {
  const n = p.node;
  const x = PAD + p.layer * COLUMN;
  const y = PAD + p.row * ROW;
  const cls = `node ${n.kind}${n.model ? ' model' : ''}${n.state ? ` ${n.state}` : ''}${n.source ? ' attached' : ''}`;
  return (
    <g className={cls} data-testid={`node-${n.name}`} data-state={n.state ?? ''} transform={`translate(${x},${y})`} onClick={() => onOpen(n)} role="link" tabIndex={0} onKeyDown={(e) => { if (e.key === 'Enter') onOpen(n); }}>
      <title>{n.name}: {nodeCaption(n, mode)}</title>
      <rect width={NODE_W} height={NODE_H} rx={9} />
      <text className="name" x={12} y={18}>{n.name}</text>
      <text className="caption" x={12} y={33}>{nodeCaption(n, mode)}</text>
    </g>
  );
}

export function Lineage({ session, mode, onOpenModel, onOpenTable, refreshKey }: LineageProps) {
  const [graph, setGraph] = useState<LineageGraph>();
  const [error, setError] = useState<string>();
  const w = words(mode);

  useEffect(() => {
    let live = true;
    setError(undefined);
    new Api(session).lineageAll().then((g) => { if (live) setGraph(g); }).catch((e: unknown) => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [session.port, session.token, refreshKey]);

  const open = (n: LineageNode) => (n.model || n.kind === 'model' ? onOpenModel(n.name) : onOpenTable(n.name));
  const placed = graph ? place(graph) : [];
  const at = new Map(placed.map((p) => [p.node.name, p]));
  const width = PAD * 2 + (Math.max(-1, ...placed.map((p) => p.layer)) + 1) * COLUMN - (COLUMN - NODE_W);
  const height = PAD * 2 + (Math.max(-1, ...placed.map((p) => p.row)) + 1) * ROW - (ROW - NODE_H);
  const stale = placed.filter((p) => p.node.state && p.node.state !== 'fresh').length;

  return (
    <section className="lineage-screen" data-testid="lineage-screen" data-mode={mode}>
      <header>
        <h2>
          {mode === 'simple' ? 'Map' : 'Lineage'}
          <span className="muted"> · {graph ? `${graph.nodes.length} ${graph.nodes.length === 1 ? 'node' : 'nodes'}, ${graph.edges.length} ${graph.edges.length === 1 ? 'edge' : 'edges'}${stale ? ` · ${stale} ${stale === 1 ? w.model : w.models} out of date` : ''}` : '…'}</span>
        </h2>
        <Command line={lineageAllCommand()} />
      </header>
      {error && <section className="error" data-testid="lineage-error"><pre>{error}</pre></section>}
      {graph && graph.nodes.length === 0 && <p className="muted" data-testid="no-nodes">Nothing to draw yet: import a file or save a question and it appears here.</p>}
      {graph && graph.nodes.length > 0 && (
        <div className="graph-wrap">
          <svg className="graph" data-testid="graph" width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${graph.nodes.length} nodes, ${graph.edges.length} edges`}>
            <g className="edges">
              {graph.edges.map((e) => {
                const a = at.get(e.from);
                const b = at.get(e.to);
                if (!a || !b) return null;
                const x1 = PAD + a.layer * COLUMN + NODE_W;
                const y1 = PAD + a.row * ROW + NODE_H / 2;
                const x2 = PAD + b.layer * COLUMN;
                const y2 = PAD + b.row * ROW + NODE_H / 2;
                const dx = Math.max(24, (x2 - x1) / 2);
                return (
                  <path key={`${e.from}-${e.to}`} className={`edge ${e.via}`} data-testid={`edge-${e.from}-${e.to}`} d={`M${x1},${y1} C${x1 + dx},${y1} ${x2 - dx},${y2} ${x2},${y2}`}>
                    <title>{e.to} reads {e.from} · {VIA_WORDS[e.via]}</title>
                  </path>
                );
              })}
            </g>
            <g className="nodes">
              {placed.map((p) => <Node key={p.node.name} p={p} mode={mode} onOpen={open} />)}
            </g>
          </svg>
        </div>
      )}
      <p className="muted legend" data-testid="legend">
        {mode === 'simple'
          ? 'Left to right: what each thing is made from. Amber needs refreshing; click anything to open it.'
          : 'Left to right: what each node reads. A model is coloured by its state (amber: edited or upstream changed; grey: never built); an edge says how it is known on hover. Click a node for its detail.'}
      </p>
    </section>
  );
}
