// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The Changes feed's sentences (decisions L2): each entry one line in the mode's words.
// Technical: "orders: append +1,200 rows", "by_c built in 1.2 s, Green", "save question:
// Total · Ada Lovelace". Simple: "orders: 1,200 rows added", "by_c refreshed in 1.2 s",
// "Total saved, a new version · Ada Lovelace". The time and the link are the screen's.

import { type Change } from './api';
import { authorName } from './versions';
import { humanSeconds, type Mode } from './vocabulary';

const rows = (v: number) => `${v.toLocaleString()} ${v === 1 ? 'row' : 'rows'}`;

function snapshotWhat(c: Change, mode: Mode): string {
  if (mode === 'technical') {
    const parts = [c.operation ?? 'commit', c.added_rows ? `+${rows(c.added_rows)}` : '', c.deleted_rows ? `−${rows(c.deleted_rows)}` : ''];
    return parts.filter(Boolean).join(' ');
  }
  const parts = [c.added_rows ? `${rows(c.added_rows)} added` : '', c.deleted_rows ? `${rows(c.deleted_rows)} deleted` : ''].filter(Boolean);
  if (parts.length) return parts.join(', ');
  return c.operation === 'overwrite' || c.operation === 'replace' ? 'replaced' : c.operation === 'delete' ? 'rows deleted' : 'changed';
}

/** What a version's message means, without the slug the core put in it: "save question:
 *  Total" → "Total saved, a new version"; "update question: Total" → "Total updated";
 *  "restore question: Total to 3f2a1c9" → "Total restored to 3f2a1c9"; "run: by_c
 *  changed" → "run: by_c changed" (Technical) / "by_c changed before a refresh" (Simple);
 *  anything else as it is. */
export function versionWhat(c: Change, mode: Mode): string {
  const m = c.message ?? '';
  const save = /^(save|update|restore) (question|model): (.+?)( to ([0-9a-f]{7,}))?$/.exec(m);
  if (save) {
    const [, verb, , title, , at] = save;
    if (mode === 'technical') return m;
    if (verb === 'save') return `${title} saved, a new version`;
    if (verb === 'update') return `${title} updated, a new version`;
    return `${title} restored to ${at?.slice(0, 7) ?? 'an earlier version'}`;
  }
  const run = /^run: (.+)$/.exec(m);
  if (run && mode === 'simple') return `${run[1].replace(/ changed$/, '')} changed before a refresh`;
  return m;
}

/** The entry as one sentence in the mode's words; no time (the screen puts it beside). */
export function changeLine(c: Change, mode: Mode): string {
  if (c.kind === 'snapshot') {
    const affects = c.affects.length
      ? mode === 'technical' ? ` · made out of date: ${c.affects.join(', ')}` : ` · ${c.affects.length === 1 ? '1 question needs' : `${c.affects.length} questions need`} refreshing: ${c.affects.join(', ')}`
      : '';
    return `${c.name}: ${snapshotWhat(c, mode)}${affects}`;
  }
  if (c.kind === 'run') {
    const verb = c.target === 'question' ? (mode === 'technical' ? 'answered' : 'asked') : mode === 'technical' ? 'built' : 'refreshed';
    if (!c.ok) return mode === 'technical' ? `${c.name} failed to build: ${c.error ?? 'no reason recorded'}` : `${c.name} could not be refreshed`;
    const took = c.seconds !== null ? ` in ${humanSeconds(c.seconds)}` : '';
    const verdict = c.verdict && mode === 'technical' ? `, ${c.verdict[0].toUpperCase()}${c.verdict.slice(1)}` : '';
    return `${c.name} ${verb}${took}${verdict}`;
  }
  const who = c.author ? ` · ${authorName(c.author)}` : '';
  return `${versionWhat(c, mode)}${who}`;
}

/** The names an entry links to, with where each opens: the table or view's detail, or
 *  the model on the Models screen (a question is a model there). */
export function changeLinks(c: Change): { name: string; where: 'table' | 'model' }[] {
  if (c.kind === 'version') return c.names.map((name) => ({ name, where: 'model' }));
  if (!c.name) return [];
  return [{ name: c.name, where: c.target === 'table' ? 'table' : 'model' }];
}

/** The screen's filter is the CLI's name argument: an exact name. */
export const matchesName = (c: Change, name: string): boolean => c.name === name || c.names.includes(name);
