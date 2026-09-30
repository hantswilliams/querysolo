// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The Recent strip (decisions L2): the last few entries of `querysolo changes <name>` on a
// table's, a view's or a model's detail — what happened to this one thing, newest first —
// with a link to the Changes screen filtered to it.

import { useEffect, useState } from 'react';
import { Api, ago, type Change } from '../lib/api';
import { changeLine } from '../lib/changes';
import type { Session } from '../lib/session';
import type { Mode } from '../lib/vocabulary';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export const RECENT = 5;

export interface RecentProps {
  session: Session;
  name: string;
  mode?: Mode;
  /** Opens the Changes screen with the filter set to this name. */
  onMore?: (name: string) => void;
  /** Changes when the thing changed (a run, an import, a save): read again. */
  refreshKey?: string | number | null;
}

export function Recent({ session, name, mode = 'technical', onMore, refreshKey }: RecentProps) {
  const [data, setData] = useState<Change[]>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    let live = true;
    setData(undefined);
    setError(undefined);
    new Api(session).changes({ name, last: RECENT }).then((d) => { if (live) setData(d); }).catch((e: unknown) => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [session.port, session.token, name, refreshKey]);

  return (
    <>
      <dt>Recent</dt>
      <dd data-testid="recent">
        {error ? <span className="muted">not known: {error}</span> : !data ? <span className="muted">…</span> : data.length === 0 ? <span className="muted">nothing recorded yet</span> : (
          <ul className="recent">
            {data.map((c) => (
              <li key={`${c.kind}-${c.when}-${c.id ?? c.snapshot_id ?? ''}`} data-testid={`recent-${c.kind}`}>
                <span className="muted">{ago(c.when)}</span> {changeLine(c, mode)}
              </li>
            ))}
          </ul>
        )}
        {onMore && data && data.length > 0 && <button type="button" className="link" data-testid="recent-more" onClick={() => onMore(name)}>{mode === 'simple' ? 'Everything about it' : 'All changes'}</button>}
      </dd>
    </>
  );
}
