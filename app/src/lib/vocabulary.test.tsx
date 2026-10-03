// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Real-data step 6 gate: Simple and Technical mode are one project in two vocabularies;
// the mapping is pinned here so both screens say the same words.

import { describe, expect, it } from 'vitest';
import type { PlannedModel } from './api';
import { changeSentence, humanSeconds, outOfDateName, planSummary, staleCount, stateSentence, testLabel, verdictSentence, words } from './vocabulary';

const model = (over: Partial<PlannedModel>): PlannedModel => ({
  name: 'stg',
  unique_id: 'model.p.stg',
  materialized: 'view',
  depends_on: [],
  compiled_sql: 'select 1',
  verdict: 'green',
  words: 'Green — about 2 s',
  reason: 'reads 1.2 MB',
  est_wall_local: 2,
  est_bytes: 1_200_000,
  error: null,
  description: '',
  path: 'models/stg.sql',
  tests: [],
  last_run: null,
  state: null,
  state_reason: null,
  state_since: null,
  ...over,
});

describe('the two vocabularies', () => {
  it('map model/test/run to question/check/refresh', () => {
    expect(words('technical')).toMatchObject({ screen: 'Models', model: 'model', tests: 'tests', runAll: 'Run all', runOne: 'Run this', view: 'view', table: 'table' });
    expect(words('simple')).toMatchObject({ screen: 'Questions', model: 'question', tests: 'checks', runAll: 'Refresh all', runOne: 'Refresh', view: 'answered live', table: 'saved as a table' });
  });

  it('name a test as dbt does, or as a sentence', () => {
    const notNull = { name: 'not_null_stg_id', kind: 'not_null', column: 'id', unique_id: 't1' };
    const unique = { name: 'unique_stg_id', kind: 'unique', column: 'id', unique_id: 't2' };
    const accepted = { name: 'accepted_values_stg_c__c0__c1', kind: 'accepted_values', column: 'c', unique_id: 't3' };
    const singular = { name: 'no_negative_totals', kind: 'singular', column: null, unique_id: 't4' };
    expect([notNull, unique, accepted, singular].map((t) => testLabel(t, 'technical'))).toEqual(['not_null(id)', 'unique(id)', 'accepted_values(c)', 'no_negative_totals']);
    expect([notNull, unique, accepted, singular].map((t) => testLabel(t, 'simple'))).toEqual(['id is never empty', 'id is never repeated', 'c is one of the allowed values', 'no negative totals']);
    expect(testLabel({ name: 'positive_amt', kind: 'is_positive', column: 'amt', unique_id: 't5' }, 'simple')).toBe('is positive on amt');
  });

  it('say the verdict as the gauge does, or as the wait', () => {
    expect(verdictSentence(model({}), 'technical')).toBe('Green — about 2 s');
    expect(verdictSentence(model({}), 'simple')).toBe('Ready in about 2 s.');
    expect(verdictSentence(model({ est_wall_local: 0.3 }), 'simple')).toBe('Ready right away.'); // not "about under a second"
    expect(verdictSentence(model({ verdict: 'yellow', est_wall_local: 240 }), 'simple')).toBe('Takes a while: about 4.0 min. Fine to start and come back.');
    expect(verdictSentence(model({ verdict: 'red', est_wall_local: 9000 }), 'simple')).toBe('Too big for this machine right now.');
    expect(verdictSentence(model({ error: 'Table with name x does not exist', verdict: null, words: null }), 'technical')).toBe('not estimated: Table with name x does not exist');
    expect(verdictSentence(model({ error: 'nope', verdict: null, words: null }), 'simple')).toContain('could not size');
    // the fourth state (trust round T3): a scan outside the catalog, never Green
    expect(verdictSentence(model({ verdict: 'none', words: 'Not estimated', reason: '1 scan outside the catalog: read_parquet', est_wall_local: null }), 'technical')).toBe('Not estimated');
    expect(verdictSentence(model({ verdict: 'none', words: 'Not estimated', est_wall_local: null }), 'simple')).toBe('Not sized: it reads something outside the project, so there is no estimate. It will run.');
  });

  it('summarise the plan', () => {
    const models = [model({}), model({ name: 'agg', verdict: 'yellow' }), model({ name: 'big', verdict: 'red' })];
    expect(planSummary(models, 'technical')).toBe('3 models · 1 Red, 1 Yellow');
    expect(planSummary(models, 'simple')).toBe('3 questions · 1 too big for this machine');
    expect(planSummary([model({})], 'technical')).toBe('1 model · all Green');
    expect(planSummary([model({})], 'simple')).toBe('1 question · all quick');
    expect(planSummary([model({ error: 'x', verdict: null })], 'technical')).toBe('1 model · 1 not estimated');
    expect(planSummary([model({ verdict: 'none', words: 'Not estimated' })], 'technical')).toBe('1 model · 1 not estimated');
    expect(planSummary([model({ verdict: 'none', words: 'Not estimated' })], 'simple')).toBe('1 question · 1 not sized');
    expect(planSummary([], 'simple')).toBe('0 questions');
  });

  it('say a wait in seconds, minutes or hours', () => {
    expect([0.3, 1.4, 5, 48, 240, 1800, 7200].map(humanSeconds)).toEqual(['under a second', '1.4 s', '5 s', '48 s', '4.0 min', '30 min', '2.0 h']);
  });

  it('say a model\'s state (V3) as the DAG\'s words or the card\'s sentence, with when', () => {
    const now = Date.parse('2026-09-16T12:00:00Z');
    const since = '2026-09-16T10:00:00+00:00';
    const cases: [Partial<PlannedModel>, string, string][] = [
      [{ state: 'fresh' }, 'fresh', 'Up to date.'],
      [{ state: 'edited', state_reason: 'the SQL changed since the last run' }, 'edited · the SQL changed since the last run', 'Changed since it was last refreshed.'],
      [{ state: 'upstream', state_reason: 'orders changed', state_since: since }, 'upstream · orders changed 2 h ago', 'Out of date: orders changed 2 h ago.'],
      [{ state: 'upstream', state_reason: 'by_c is out of date', state_since: since }, 'upstream · by_c is out of date', 'Out of date, because by_c is.'],
      [{ state: 'never', state_reason: 'never built' }, 'never · never built', 'Never refreshed.'],
      [{ state: 'never', state_reason: 'the last run failed', state_since: since }, 'never · the last run failed', 'The last refresh failed.'],
      [{ state: null }, '—', '—'],
    ];
    for (const [over, technical, simple] of cases) {
      expect(stateSentence(model(over), 'technical', now)).toBe(technical);
      expect(stateSentence(model(over), 'simple', now)).toBe(simple);
    }
    expect(staleCount([model({ state: 'fresh' }), model({ state: 'never' }), model({ state: 'edited' }), model({ state: null })])).toBe(2);
    expect(words('technical').runStale).toBe('Run what changed');
    expect(words('simple').runStale).toBe('Refresh what changed');
  });

  it('say what was committed to a table since the run, and name the model blamed', () => {
    const now = Date.parse('2026-09-16T12:00:00Z');
    const at = '2026-09-16T11:30:00+00:00';
    const append = { name: 'orders', operation: 'append', added_rows: 1200, deleted_rows: null, timestamp: at };
    const del = { name: 'orders', operation: 'delete', added_rows: null, deleted_rows: 10, timestamp: at };
    const both = { name: 'orders', operation: 'overwrite', added_rows: 1, deleted_rows: 1, timestamp: at };
    const view = { name: 'orders_v', operation: 'new version', added_rows: null, deleted_rows: null, timestamp: null };
    expect(changeSentence(append, 'technical', now)).toBe('orders · append +1,200 rows · 30 min ago');
    expect(changeSentence(del, 'technical', now)).toBe('orders · delete −10 rows · 30 min ago');
    expect(changeSentence(view, 'technical', now)).toBe('orders_v · new version');
    expect(changeSentence(append, 'simple', now)).toBe('orders: 1,200 rows added 30 min ago');
    expect(changeSentence(del, 'simple', now)).toBe('orders: 10 rows deleted 30 min ago');
    expect(changeSentence(both, 'simple', now)).toBe('orders: 1 row added, 1 row deleted 30 min ago');
    expect(changeSentence(view, 'simple', now)).toBe('orders_v: a new version');
    expect(outOfDateName('by_c is out of date')).toBe('by_c');
    expect(outOfDateName('orders changed')).toBeNull();
    expect(outOfDateName(null)).toBeNull();
  });
});
