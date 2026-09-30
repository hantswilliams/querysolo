// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Versions step 3 gate, the words: the unified diff the core sends becomes lines with a kind
// each, its one-line summary counts what changed, a version is a sentence in Simple mode
// with no id in it, and the git line says what the panel says.

import { describe, expect, it } from 'vitest';
import type { Version } from './api';
import { authorName, collapseDiff, diffSummary, gitLine, parseDiff, versionSentence, versionWhat } from './versions';

const DIFF = [
  '--- before',
  '+++ after',
  '@@ -1,3 +1,3 @@',
  ' -- Revenue by customer',
  ' -- saved by querysolo on 2026-09-12',
  '-select customer, sum(amt) as revenue from orders group by 1',
  '+select customer, sum(amt) as revenue from orders group by 1 order by 2 desc',
  '',
].join('\n');

const ARRIVING = ['--- before', '+++ after', '@@ -0,0 +1,3 @@', '+-- Revenue by customer', '+-- saved by querysolo on 2026-09-12', '+select 1', ''].join('\n');

const version = (over: Partial<Version>): Version => ({
  id: 'abcdef0123456789', when: new Date(Date.now() - 240_000).toISOString(), author: 'Ada Lovelace <ada@example.com>',
  message: 'update question: Revenue by customer', sql_changed: true, checks_changed: false, diff: DIFF, ...over,
});

describe('the diff', () => {
  it('is parsed into meta, hunk, context, removed and added lines with the markers stripped', () => {
    expect(parseDiff(DIFF).map((l) => l.kind)).toEqual(['meta', 'meta', 'hunk', 'ctx', 'ctx', 'del', 'add']);
    expect(parseDiff(DIFF)[3].text).toBe('-- Revenue by customer');
    expect(parseDiff(DIFF)[6].text).toBe('select customer, sum(amt) as revenue from orders group by 1 order by 2 desc');
    expect(parseDiff('')).toEqual([]);
  });

  it('is summarised as what changed', () => {
    expect(diffSummary(DIFF)).toBe('1 line changed');
    expect(diffSummary(ARRIVING)).toBe('3 lines added');
    expect(diffSummary(['@@', '+a', '+b', '-c', ''].join('\n'))).toBe('2 lines added, 1 removed');
    expect(diffSummary('')).toBe('no change to the SQL');
  });
});

describe('a version as a sentence', () => {
  it('Technical is the commit message; Simple says what happened and never an id', () => {
    const v = version({});
    expect(versionWhat(v, 'technical')).toBe('update question: Revenue by customer');
    expect(versionWhat(v, 'simple')).toBe('Updated · 1 line changed');
    expect(versionWhat(version({ message: 'save question: Revenue by customer', diff: ARRIVING, checks_changed: true }), 'simple')).toBe('Saved');
    expect(versionWhat(version({ message: 'restore question: Revenue by customer to abcdef0' }), 'simple')).toBe('Restored an earlier version · 1 line changed');
    expect(versionWhat(version({ message: 'update question: Revenue by customer', sql_changed: false, checks_changed: true, diff: '' }), 'simple')).toBe('Updated the checks');
    // a run's commit, or one made by hand: the diff's summary is all the app can say
    expect(versionWhat(version({ message: 'run: stg changed' }), 'simple')).toBe('1 line changed');
    expect(versionWhat(version({ message: 'wip', sql_changed: false, checks_changed: true, diff: '' }), 'simple')).toBe('Checks changed');
    expect(versionSentence(v, 'simple')).toBe('4 min ago · Ada Lovelace · Updated · 1 line changed');
    expect(versionSentence(v, 'simple')).not.toMatch(/[0-9a-f]{7}/);
  });

  it('shows the name git knows, without the address', () => {
    expect(authorName('Ada Lovelace <ada@example.com>')).toBe('Ada Lovelace');
    expect(authorName('hants <hants@mac.local>')).toBe('hants');
    expect(authorName('nobody')).toBe('nobody');
  });
});

describe('the git line', () => {
  it('names the branch and says when origin is not set', () => {
    expect(gitLine({ repository: true, branch: 'main', origin: null })).toBe('git · main · origin not set');
    expect(gitLine({ repository: true, branch: 'main', origin: 'git@github.com:ada/proj.git' })).toBe('git · main · origin git@github.com:ada/proj.git');
    expect(gitLine({ repository: false, branch: null, origin: null })).toBe('git · no repository yet · the first save makes one');
  });

  it('folds a whole-file diff to the changed lines with three of context, marking what it dropped', () => {
    const ctx = (n: number) => Array.from({ length: n }, (_, i) => ` line ${i}`);
    const whole = ['--- last run', '+++ now', '@@ -1,12 +1,12 @@', ...ctx(10), '-old', '+new'].join('\n');
    const { lines, folded } = collapseDiff(parseDiff(whole));
    expect(folded).toBe(true);
    expect(lines.map((l) => l.text)).toEqual(['--- last run', '+++ now', '@@ -1,12 +1,12 @@', '…', 'line 7', 'line 8', 'line 9', 'old', 'new']);
    const small = collapseDiff(parseDiff(['--- a', '+++ b', '@@ -1,2 +1,2 @@', ' keep', '-old', '+new'].join('\n')));
    expect(small.folded).toBe(false);
    expect(small.lines).toHaveLength(6);
  });
});
