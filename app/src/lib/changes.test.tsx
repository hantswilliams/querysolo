// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions L2: each entry of the feed as one sentence, in both modes, and where it links.

import { describe, expect, it } from 'vitest';
import type { Change } from './api';
import { changeLine, changeLinks, matchesName, versionWhat } from './changes';

const base: Change = {
  when: '2026-09-18T10:00:00+00:00', kind: 'snapshot', name: 'orders', target: 'table',
  operation: null, snapshot_id: null, added_rows: null, deleted_rows: null, affects: [],
  ok: null, seconds: null, verdict: null, error: null, id: null, author: null, message: null, names: [],
};

describe('the changes feed', () => {
  it("a snapshot: the operation and rows, and the models it made out of date, in the mode's words", () => {
    const append: Change = { ...base, operation: 'append', snapshot_id: 3, added_rows: 1200, affects: ['stg', 'by_customer'] };
    expect(changeLine(append, 'technical')).toBe('orders: append +1,200 rows · made out of date: stg, by_customer');
    expect(changeLine(append, 'simple')).toBe('orders: 1,200 rows added · 2 questions need refreshing: stg, by_customer');
    const del: Change = { ...base, operation: 'delete', deleted_rows: 1, affects: ['stg'] };
    expect(changeLine(del, 'technical')).toBe('orders: delete −1 row · made out of date: stg');
    expect(changeLine(del, 'simple')).toBe('orders: 1 row deleted · 1 question needs refreshing: stg');
    expect(changeLine({ ...base, operation: 'overwrite' }, 'simple')).toBe('orders: replaced');
    expect(changeLine({ ...base, operation: 'append', added_rows: 3, deleted_rows: 2 }, 'technical')).toBe('orders: append +3 rows −2 rows');
    expect(changeLinks(append)).toEqual([{ name: 'orders', where: 'table' }]);
  });

  it('a run: built or answered, the time and the verdict; a failure says so', () => {
    const run: Change = { ...base, kind: 'run', name: 'by_c', target: 'model', ok: true, seconds: 1.23, verdict: 'green' };
    expect(changeLine(run, 'technical')).toBe('by_c built in 1.2 s, Green');
    expect(changeLine(run, 'simple')).toBe('by_c refreshed in 1.2 s');
    const asked: Change = { ...run, name: 'total', target: 'question', seconds: 0.3, verdict: 'yellow' };
    expect(changeLine(asked, 'technical')).toBe('total answered in under a second, Yellow');
    expect(changeLine(asked, 'simple')).toBe('total asked in under a second');
    const failed: Change = { ...run, ok: false, seconds: null, error: 'dbt: error' };
    expect(changeLine(failed, 'technical')).toBe('by_c failed to build: dbt: error');
    expect(changeLine(failed, 'simple')).toBe('by_c could not be refreshed');
    expect(changeLinks(run)).toEqual([{ name: 'by_c', where: 'model' }]);
    expect(changeLinks(asked)).toEqual([{ name: 'total', where: 'model' }]);
  });

  it("a version: the message as the mode says it, the author's name, a link per file touched", () => {
    const save: Change = { ...base, kind: 'version', name: 'total', target: 'question', id: '3f2a1c9', author: 'Ada Lovelace <ada@example.org>', message: 'save question: Total', names: ['total'] };
    expect(changeLine(save, 'technical')).toBe('save question: Total · Ada Lovelace');
    expect(changeLine(save, 'simple')).toBe('Total saved, a new version · Ada Lovelace');
    expect(versionWhat({ ...save, message: 'update question: Total' }, 'simple')).toBe('Total updated, a new version');
    expect(versionWhat({ ...save, message: 'restore question: Total to 3f2a1c9' }, 'simple')).toBe('Total restored to 3f2a1c9');
    expect(versionWhat({ ...save, message: 'restore model: by_c to 3f2a1c9' }, 'technical')).toBe('restore model: by_c to 3f2a1c9');
    const run: Change = { ...save, name: null, target: 'project', message: 'run: by_c, stg changed', names: ['by_c', 'stg'] };
    expect(versionWhat(run, 'simple')).toBe('by_c, stg changed before a refresh');
    expect(versionWhat(run, 'technical')).toBe('run: by_c, stg changed');
    expect(changeLinks(run)).toEqual([{ name: 'by_c', where: 'model' }, { name: 'stg', where: 'model' }]);
    const init: Change = { ...save, name: null, target: 'project', message: 'querysolo init', names: [], author: 'hants' };
    expect(changeLine(init, 'simple')).toBe('querysolo init · hants');
    expect(changeLinks(init)).toEqual([]);
    expect(matchesName(run, 'stg')).toBe(true);
    expect(matchesName(save, 'total')).toBe(true);
    expect(matchesName(save, 'orders')).toBe(false);
  });
});
