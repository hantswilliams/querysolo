// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Simple and Technical mode (screens 7 and 8 of the mockups, real-data step 6): the same
// project in two vocabularies. Technical says model, test, view, verdict, `querysolo run`;
// Simple says question, check, "answered live", a sentence about the wait, Refresh. The
// mapping lives here so a test can pin it and every screen says the same words.

import { ago, type ModelTest, type PlannedModel, type StateChange } from './api';

export type Mode = 'simple' | 'technical';

export interface Words {
  /** The screen's name in the bar. */
  screen: string;
  model: string;
  models: string;
  test: string;
  tests: string;
  /** What a `view` model is: answered live from its query. */
  view: string;
  /** What a `table` model is: rows written, rebuilt on a run. */
  table: string;
  runAll: string;
  runOne: string;
  runAnyway: string;
  /** The verb in a sentence about the last run: "last run", "last refreshed". */
  lastRun: string;
  planning: string;
  running: string;
  /** The model panel's history section (versions brief G6): "Versions", or "History". */
  versions: string;
  /** `querysolo run --stale` (V3): the button beside Run all. */
  runStale: string;
  /** The rows (decisions Q1): the workspace with `select * from <name>` run. */
  answer: string;
  /** The same for a model never built: the run first, then the rows. */
  answerAfterRun: string;
}

const TECHNICAL: Words = {
  screen: 'Models',
  model: 'model',
  models: 'models',
  test: 'test',
  tests: 'tests',
  view: 'view',
  table: 'table',
  runAll: 'Run all',
  runOne: 'Run this',
  runAnyway: 'Run anyway',
  lastRun: 'Last run',
  planning: 'planning…',
  running: 'running…',
  versions: 'Versions',
  runStale: 'Run what changed',
  answer: 'Rows',
  answerAfterRun: 'Run, then rows',
};

const SIMPLE: Words = {
  screen: 'Questions',
  model: 'question',
  models: 'questions',
  test: 'check',
  tests: 'checks',
  view: 'answered live',
  table: 'saved as a table',
  runAll: 'Refresh all',
  runOne: 'Refresh',
  runAnyway: 'Refresh anyway',
  lastRun: 'Last refreshed',
  planning: 'looking…',
  running: 'refreshing…',
  versions: 'History',
  runStale: 'Refresh what changed',
  answer: 'See the answer',
  answerAfterRun: 'Refresh, then see the answer',
};

export const words = (mode: Mode): Words => (mode === 'simple' ? SIMPLE : TECHNICAL);

/** The mode the window last used; Technical when nothing is remembered. */
export function loadMode(): Mode {
  try {
    return localStorage.getItem('querysolo.mode') === 'simple' ? 'simple' : 'technical';
  } catch {
    return 'technical';
  }
}

export function saveMode(mode: Mode): void {
  try {
    localStorage.setItem('querysolo.mode', mode);
  } catch {
    // a webview without storage: the mode lives for the window
  }
}

/** "2 s", "48 s", "3.5 min", "1.2 h": a wait the way a sentence says it. */
export function humanSeconds(s: number): string {
  if (s < 1) return 'under a second';
  if (s < 10) return `${Number.isInteger(s) ? s : s.toFixed(1)} s`;
  if (s < 90) return `${Math.round(s)} s`;
  if (s < 3600) return `${(s / 60).toFixed(s < 600 ? 1 : 0)} min`;
  return `${(s / 3600).toFixed(1)} h`;
}

const humanise = (name: string) => name.replace(/[_-]+/g, ' ').trim();

/** A test the way each mode names it: Technical `not_null(id)`; Simple "id is never empty". */
export function testLabel(t: ModelTest, mode: Mode): string {
  if (mode === 'technical') return t.column ? `${t.kind}(${t.column})` : t.kind === 'singular' ? t.name : `${t.kind} · ${t.name}`;
  const c = t.column ?? '';
  switch (t.kind) {
    case 'not_null': return `${c} is never empty`;
    case 'unique': return `${c} is never repeated`;
    case 'accepted_values': return `${c} is one of the allowed values`;
    case 'relationships': return `every ${c} points at a real row`;
    case 'singular': return humanise(t.name);
    default: return c ? `${humanise(t.kind)} on ${c}` : humanise(t.name);
  }
}

/** The gauge's verdict as a sentence. Technical is the gauge's own words; Simple says
 *  what it means for the wait, without the colour or the bytes. */
export function verdictSentence(m: Pick<PlannedModel, 'verdict' | 'words' | 'reason' | 'error' | 'est_wall_local'>, mode: Mode): string {
  if (m.error) return mode === 'technical' ? `not estimated: ${m.error}` : 'QuerySolo could not size this one yet; refreshing will say.';
  if (mode === 'technical') return m.words ?? m.reason ?? m.verdict ?? '—';
  const wait = m.est_wall_local !== null && m.est_wall_local !== undefined ? humanSeconds(m.est_wall_local) : null;
  switch (m.verdict) {
    // "about under a second" is not a sentence: a sub-second estimate is "right away"
    case 'green': return wait && wait !== 'under a second' ? `Ready in about ${wait}.` : 'Ready right away.';
    case 'yellow': return wait ? `Takes a while: about ${wait}. Fine to start and come back.` : 'Takes a while. Fine to start and come back.';
    case 'red': return 'Too big for this machine right now.';
    case 'none': return 'Not sized: it reads something outside the project, so there is no estimate. It will run.';
    default: return '—';
  }
}

/** The DAG's summary line: "3 models · all Green" or "4 models · 1 Red, 1 Yellow". */
export function planSummary(models: PlannedModel[], mode: Mode): string {
  const w = words(mode);
  const n = models.length;
  const head = `${n} ${n === 1 ? w.model : w.models}`;
  if (n === 0) return head;
  const count = (v: string) => models.filter((m) => m.verdict === v).length;
  const red = count('red');
  const yellow = count('yellow');
  const unknown = models.filter((m) => m.error || m.verdict === 'none').length;
  if (mode === 'simple') {
    if (red) return `${head} · ${red} too big for this machine`;
    if (yellow) return `${head} · ${yellow} ${yellow === 1 ? 'takes' : 'take'} a while`;
    if (unknown) return `${head} · ${unknown} not sized`;
    return `${head} · all quick`;
  }
  const parts = [red && `${red} Red`, yellow && `${yellow} Yellow`, unknown && `${unknown} not estimated`].filter(Boolean);
  return `${head} · ${parts.length ? parts.join(', ') : 'all Green'}`;
}

/** A model's state (V3) as the DAG's words or the card's sentence. Technical: `fresh`,
 *  `edited · the SQL changed since the last run`, `upstream · orders changed 2 h ago`,
 *  `upstream · by_c is out of date`, `never · never built`. Simple: "Up to date.",
 *  "Changed since it was last refreshed.", "Out of date: orders changed 2 h ago.",
 *  "Out of date, because by_c is.", "Never refreshed." */
export function stateSentence(m: Pick<PlannedModel, 'state' | 'state_reason' | 'state_since'>, mode: Mode, now = Date.now()): string {
  if (!m.state) return '—';
  const reason = m.state_reason ?? '';
  const changed = /changed$/.test(reason) && m.state_since ? `${reason} ${ago(m.state_since, now)}` : reason;
  if (mode === 'technical') return m.state === 'fresh' ? 'fresh' : changed ? `${m.state} · ${changed}` : m.state;
  switch (m.state) {
    case 'fresh': return 'Up to date.';
    case 'edited': return 'Changed since it was last refreshed.';
    case 'upstream': return / is out of date$/.test(reason) ? `Out of date, because ${reason.replace(/ is out of date$/, '')} is.` : `Out of date: ${changed || 'something it reads changed'}.`;
    case 'never': return reason === 'the last run failed' ? 'The last refresh failed.' : 'Never refreshed.';
  }
}

/** How many models are not fresh, for the button: null when every one is. */
export function staleCount(models: PlannedModel[]): number {
  return models.filter((m) => m.state && m.state !== 'fresh').length;
}

/** One commit behind an `upstream` state, as a line. Technical: `orders · append +1,200 rows · 2 h ago`;
 *  Simple: "orders: 1,200 rows added 2 h ago". */
export function changeSentence(c: StateChange, mode: Mode, now = Date.now()): string {
  const when = c.timestamp ? ago(c.timestamp, now) : '';
  const rows = (v: number) => `${v.toLocaleString()} ${v === 1 ? 'row' : 'rows'}`;
  if (mode === 'technical') {
    const what = [c.operation ?? 'commit', c.added_rows ? `+${rows(c.added_rows)}` : '', c.deleted_rows ? `−${rows(c.deleted_rows)}` : ''].filter(Boolean).join(' ');
    return [c.name, what, when].filter(Boolean).join(' · ');
  }
  const parts = [c.added_rows ? `${rows(c.added_rows)} added` : '', c.deleted_rows ? `${rows(c.deleted_rows)} deleted` : ''].filter(Boolean);
  const what = parts.length ? parts.join(', ')
    : c.operation === 'new version' ? 'a new version'
      : c.operation === 'overwrite' || c.operation === 'replace' ? 'replaced'
        : c.operation === 'delete' ? 'rows deleted'
          : 'changed';
  return `${c.name}: ${what}${when ? ` ${when}` : ''}`;
}

/** The name in "<name> is out of date", or null for any other reason. */
export const outOfDateName = (reason: string | null): string | null => {
  const m = /^(.+) is out of date$/.exec(reason ?? '');
  return m ? m[1] : null;
};
