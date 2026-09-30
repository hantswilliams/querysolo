// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The lineage lines (versions brief G8, step 4): `querysolo lineage <name>` as two rows of
// a detail's facts — what it reads from and what it feeds, one level, each name a link
// that opens that detail (a table or view on the Tables screen, a model on the Models
// screen). Technical mode says how each edge is known: a dbt ref() or source(), a table
// named in the SQL, or a catalog view's SQL. Nothing here does what the CLI cannot.

import { useEffect, useState } from 'react';
import { Api, type Lineage as LineageData, type LineageEdge } from '../lib/api';
import type { Session } from '../lib/session';
import type { Mode } from '../lib/vocabulary';

export interface LineageProps {
  session: Session;
  name: string;
  mode?: Mode;
  /** A name was clicked: open its detail. */
  onOpen: (name: string, kind: LineageEdge['kind']) => void;
  /** Changes when the project changed (a run, an import): the lines are read again. */
  refreshKey?: string | number | null;
}

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export const VIA_WORDS: Record<LineageEdge['via'], string> = {
  ref: 'ref',
  source: 'source',
  sql: 'named in the SQL',
  view: "the view's SQL",
};

/** What a line says about one edge: the name, then in Technical the kind and how it is known. */
export function edgeLabel(e: LineageEdge, mode: Mode): string {
  return mode === 'simple' ? e.name : `${e.name} (${e.kind}, ${VIA_WORDS[e.via]})`;
}

function Names({ edges, mode, onOpen, testid }: { edges: LineageEdge[]; mode: Mode; onOpen: LineageProps['onOpen']; testid: string }) {
  if (edges.length === 0) return <span className="muted" data-testid={testid}>nothing</span>;
  return (
    <span data-testid={testid}>
      {edges.map((e, i) => (
        <span key={e.name}>
          {i > 0 && <span className="muted"> · </span>}
          <button type="button" className="link mono" data-testid={`lineage-${e.name}`} data-kind={e.kind} onClick={() => onOpen(e.name, e.kind)}>{e.name}</button>
          {mode === 'technical' && <span className="muted"> ({e.kind}, {VIA_WORDS[e.via]})</span>}
        </span>
      ))}
    </span>
  );
}

/** Two `dt`/`dd` pairs for a detail's `dl.facts`: Reads from, Feeds. */
export function LineageRows({ session, name, mode = 'technical', onOpen, refreshKey }: LineageProps) {
  const [data, setData] = useState<LineageData>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let live = true;
    setData(undefined);
    setError(undefined);
    new Api(session).lineage(name).then((d) => { if (live) setData(d); }).catch((e: unknown) => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [session.port, session.token, name, refreshKey]);

  const pending = !data && !error;
  return (
    <>
      <dt>Reads from</dt>
      <dd data-testid="reads-from">
        {error ? <span className="muted">not known: {error}</span> : pending ? <span className="muted">…</span> : <Names edges={data!.upstream} mode={mode} onOpen={onOpen} testid="upstream" />}
      </dd>
      <dt>Feeds</dt>
      <dd data-testid="feeds">
        {error ? <span className="muted">not known</span> : pending ? <span className="muted">…</span> : <Names edges={data!.downstream} mode={mode} onOpen={onOpen} testid="downstream" />}
      </dd>
    </>
  );
}
