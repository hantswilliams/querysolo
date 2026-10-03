// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The Changes screen (decisions L2): everything that happened to the project, newest
// first — every table's snapshots, every run of each model and question, the versions git
// holds for the models — one sentence each in the mode's words, each a link to its detail.
// `querysolo changes` is the same list as text; a name typed in the filter is its argument.

import { useEffect, useState } from 'react';
import { Api, ago, type Change } from '../lib/api';
import { changeLine, changeLinks } from '../lib/changes';
import { changesCommand } from '../lib/command';
import type { Session } from '../lib/session';
import type { Mode } from '../lib/vocabulary';
import { Command } from '../components/Command';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

export const LAST = 100;

export interface ChangesProps {
  session: Session;
  mode: Mode;
  /** The filter to arrive with (a detail's Recent strip named it). */
  name?: string;
  onOpenModel: (name: string) => void;
  onOpenTable: (name: string) => void;
  /** Changes when the project changed (a run, an import): the feed is read again. */
  refreshKey?: string | number | null;
}

const KIND_WORDS: Record<Mode, Record<Change['kind'], string>> = {
  technical: { snapshot: 'snapshot', run: 'run', version: 'version' },
  simple: { snapshot: 'data', run: 'refresh', version: 'saved' },
};

export function Changes({ session, mode, name, onOpenModel, onOpenTable, refreshKey }: ChangesProps) {
  const [filter, setFilter] = useState(name ?? '');
  const [feed, setFeed] = useState<Change[]>();
  const [error, setError] = useState<string>();
  const wanted = filter.trim();

  useEffect(() => { if (name !== undefined) setFilter(name); }, [name]);

  useEffect(() => {
    let live = true;
    setError(undefined);
    new Api(session).changes({ last: LAST, name: wanted || undefined }).then((d) => { if (live) setFeed(d); }).catch((e: unknown) => { if (live) setError(message(e)); });
    return () => { live = false; };
  }, [session.port, session.token, wanted, refreshKey]);

  const open = (link: { name: string; where: 'table' | 'model' }) => (link.where === 'table' ? onOpenTable(link.name) : onOpenModel(link.name));

  return (
    <section className="changes-screen" data-testid="changes-screen" data-mode={mode}>
      <header>
        <h2>
          {mode === 'simple' ? 'Recent' : 'Changes'}
          <span className="muted"> · {feed ? `${feed.length} ${feed.length === 1 ? 'entry' : 'entries'}${wanted ? ` about ${wanted}` : ''}${feed.length === LAST ? ', the latest' : ''}` : '…'}</span>
        </h2>
        <label className="filter">
          <span className="muted">{mode === 'simple' ? 'Only about' : 'Name'}</span>
          <input type="text" value={filter} placeholder={mode === 'simple' ? 'a table or a question' : 'a table, view, model or question'} spellCheck={false} data-testid="changes-filter" onChange={(e) => setFilter(e.target.value)} />
        </label>
        <Command line={changesCommand({ name: wanted || undefined, last: LAST })} />
      </header>
      {error && <section className="error" data-testid="changes-error"><pre>{error}</pre></section>}
      {feed && feed.length === 0 && (
        <p className="muted" data-testid="no-changes">
          {wanted ? `Nothing about ${wanted} yet.` : 'Nothing yet: import a file, ask and save a question, and it appears here.'}
        </p>
      )}
      {feed && feed.length > 0 && (
        <ol className="feed" data-testid="feed">
          {feed.map((c) => {
            const links = changeLinks(c);
            return (
              <li key={`${c.kind}-${c.when}-${c.id ?? c.snapshot_id ?? c.name ?? ''}`} className={`entry ${c.kind}${c.kind === 'run' && c.ok === false ? ' failed' : ''}`} data-testid={`entry-${c.kind}`}>
                <span className="when muted" title={c.when}>{ago(c.when)}</span>
                <span className={`kind ${c.kind}`}>{KIND_WORDS[mode][c.kind]}</span>
                <span className="line">
                  {changeLine(c, mode)}
                  {links.map((l) => <button key={l.name} type="button" className="link mono" data-testid={`open-${l.name}`} onClick={() => open(l)}>{links.length > 1 || l.name !== c.name ? l.name : 'open'}</button>)}
                </span>
              </li>
            );
          })}
        </ol>
      )}
      <p className="muted legend" data-testid="changes-legend">
        {mode === 'simple'
          ? 'Newest first: data that arrived, questions refreshed, questions saved. Nothing here is recorded for its own sake; it is read from what the project keeps.'
          : 'Newest first, from three sources: every table\'s snapshots (with the models each made out of date), every run of each model and question, and the versions git holds for the models. Nothing is recorded for this list.'}
      </p>
    </section>
  );
}
