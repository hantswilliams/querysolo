// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The Versions section's words (versions brief G6): the unified diff the core sends,
// rendered line by line without a library; its one-line summary; and each version as a
// sentence for Simple mode, where a commit is "Updated · 1 line changed" and never an id.

import { ago, type GitStatus, type Version } from './api';
import type { Mode } from './vocabulary';

export type DiffKind = 'add' | 'del' | 'ctx' | 'hunk' | 'meta';

export interface DiffLine {
  kind: DiffKind;
  text: string;
}

/** The unified diff as lines with a kind each: `---`/`+++` are meta, `@@` a hunk, then
 *  added, removed and context lines with their marker stripped. */
export function parseDiff(diff: string): DiffLine[] {
  if (!diff) return [];
  const lines = diff.replace(/\n$/, '').split('\n');
  return lines.map((line): DiffLine => {
    if (line.startsWith('+++') || line.startsWith('---')) return { kind: 'meta', text: line };
    if (line.startsWith('@@')) return { kind: 'hunk', text: line };
    if (line.startsWith('+')) return { kind: 'add', text: line.slice(1) };
    if (line.startsWith('-')) return { kind: 'del', text: line.slice(1) };
    return { kind: 'ctx', text: line.startsWith(' ') ? line.slice(1) : line };
  });
}

/** The diff folded to its changes: context lines further than ``context`` from a changed
 *  line are dropped and each dropped run is one `…` hunk line, so a whole-file diff (the
 *  state's, V3) reads as changes only; `whole` is the same lines untouched. */
export function collapseDiff(lines: DiffLine[], context = 3): { lines: DiffLine[]; folded: boolean } {
  const changed = lines.map((l) => l.kind === 'add' || l.kind === 'del');
  const keep = lines.map((l, i) => {
    if (l.kind !== 'ctx') return true;
    for (let j = Math.max(0, i - context); j <= Math.min(lines.length - 1, i + context); j++) if (changed[j]) return true;
    return false;
  });
  const out: DiffLine[] = [];
  let folded = false;
  let skipping = false;
  lines.forEach((l, i) => {
    if (keep[i]) { out.push(l); skipping = false; return; }
    folded = true;
    if (!skipping) { out.push({ kind: 'hunk', text: '…' }); skipping = true; }
  });
  return { lines: out, folded };
}

/** "1 line changed", "2 lines added", "3 lines added, 1 removed", or "no change to the SQL". */
export function diffSummary(diff: string): string {
  const lines = parseDiff(diff);
  const added = lines.filter((l) => l.kind === 'add').length;
  const removed = lines.filter((l) => l.kind === 'del').length;
  if (added === 0 && removed === 0) return 'no change to the SQL';
  if (added === removed) return `${added} ${added === 1 ? 'line' : 'lines'} changed`;
  const parts = [added && `${added} ${added === 1 ? 'line' : 'lines'} added`, removed && `${removed} removed`].filter(Boolean);
  return parts.join(', ');
}

/** The name in git's `Name <email>`. */
export const authorName = (author: string): string => author.replace(/\s*<[^>]*>\s*$/, '').trim() || author;

const SAVE = /^save question: (.*)$/;
const UPDATE = /^update question: (.*)$/;
const RESTORE = /^restore (?:question|model): (.*) to ([0-9a-f]{7})$/;

/** What the version did, the way each mode says it. Technical is the commit message as
 *  written. Simple is a sentence with no git in it: a save from the app is "Saved" or
 *  "Updated", a restore says so, and anything else (a run's commit, a hand-written one)
 *  is the diff's one-line summary, which is all the app can honestly say about it. */
export function versionWhat(v: Version, mode: Mode): string {
  if (mode === 'technical') return v.message;
  const summary = diffSummary(v.diff);
  if (SAVE.test(v.message)) return 'Saved';
  if (UPDATE.test(v.message)) return v.sql_changed ? `Updated · ${summary}` : 'Updated the checks';
  if (RESTORE.test(v.message)) return `Restored an earlier version · ${summary}`;
  return v.sql_changed ? summary : 'Checks changed';
}

/** One version as a line: "4 min ago · Ada Lovelace · Updated · 1 line changed". */
export function versionSentence(v: Version, mode: Mode, now = Date.now()): string {
  return `${ago(v.when, now)} · ${authorName(v.author)} · ${versionWhat(v, mode)}`;
}

/** The panel's one line about git, Technical mode only (G6): `git · main · origin not set`. */
export function gitLine(s: GitStatus): string {
  if (!s.repository) return 'git · no repository yet · the first save makes one';
  return `git · ${s.branch ?? 'detached'} · ${s.origin ? `origin ${s.origin}` : 'origin not set'}`;
}
