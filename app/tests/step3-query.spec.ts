// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 3 gate (app brief §4): on a 20 M-row table the first rows are on screen before the
// query completes (timestamped); a lowered-threshold project shows Red with the sentence
// and runs on "Run anyway"; Esc during a slow query leaves the app responsive and history
// shows the closed run; Cmd/Ctrl+Enter runs; a bad statement is a line, not a crash.

import { test, expect, type Page } from '@playwright/test';
import { BIG_ROWS, pageUrl, readStates, type Started } from './sidecar';

const big = () => readStates()[2];
const red = () => readStates()[3];

// CodeMirror's Mod is ⌘ on macOS and Ctrl elsewhere; the tests run on both.
const mod = process.platform === 'darwin' ? 'Meta' : 'Control';

async function openReady(page: Page, s: Started) {
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status').first()).toHaveText('core ready');
  await expect(page.getByTestId('sql-editor')).toBeVisible();
}

async function typeSql(page: Page, sql: string) {
  const editor = page.getByTestId('sql-editor').locator('.cm-content');
  await editor.click();
  await page.keyboard.press(`${mod}+A`);
  // inserted as text, not typed key by key: keystrokes would meet the editor's own bindings
  await page.keyboard.insertText(sql);
  await expect(page.getByTestId('query').getByTestId('command')).toContainText(sql.slice(0, 20));
  await page.keyboard.press('Escape'); // closes the completion popup the insert opened; nothing is running
}

async function history(s: Started, last = 3): Promise<Array<Record<string, unknown>>> {
  const r = await fetch(`http://127.0.0.1:${s.port}/api/history?last=${last}`, { headers: { Authorization: `Bearer ${s.token}` } });
  return (await r.json()) as Array<Record<string, unknown>>;
}

test('the verdict comes before the rows and the first rows before the query completes', async ({ page }) => {
  const s = big();
  await openReady(page, s);
  await expect(page.getByTestId('table-big')).toContainText(BIG_ROWS.toLocaleString());
  const sql = 'select id, x, c from big where id % 300 = 0';
  await typeSql(page, sql);
  await expect(page.getByTestId('query').getByTestId('command').locator('code')).toHaveText(`querysolo sql '${sql}'`);
  await page.getByTestId('run').click();

  const gauge = page.getByTestId('gauge');
  await expect(gauge).toHaveAttribute('data-verdict', 'green');
  await expect(gauge).toContainText('Runs here');
  const grid = page.getByTestId('grid');
  await expect(gauge).toHaveAttribute('data-state', 'done', { timeout: 120_000 });
  const expected = Math.ceil(BIG_ROWS / 300); // ids 0, 300, … below 20 M
  await expect(gauge).toContainText(`${expected.toLocaleString()} rows in`);
  await expect(grid).toHaveAttribute('data-rows', String(expected));
  await expect(grid.locator('.grid-row').first()).toContainText(/c\d+/); // batches land in scan order, not id order

  // The screen stamps its own clock: the verdict, the first rows in the grid, the end.
  const q = page.getByTestId('query');
  const verdictMs = Number(await q.getAttribute('data-verdict-ms'));
  const firstMs = Number(await q.getAttribute('data-first-rows-ms'));
  const firstRows = Number(await q.getAttribute('data-first-rows'));
  const doneMs = Number(await q.getAttribute('data-done-ms'));
  console.log(`verdict at +${verdictMs} ms; first ${firstRows} rows in the grid at +${firstMs} ms; ${expected} rows done at +${doneMs} ms`);
  expect(verdictMs).toBeGreaterThan(0);
  expect(verdictMs).toBeLessThanOrEqual(firstMs);
  // The first rows on screen are one batch of the core's stream (real-data brief R9): the
  // server writes 1,000-row batches and nothing on the way holds them back.
  expect(firstRows).toBeGreaterThan(0);
  expect(firstRows).toBeLessThanOrEqual(1000);
  expect(firstMs).toBeLessThan(doneMs);
});

test('Red is a refusal with the sentence until "Run anyway"', async ({ page }) => {
  const s = red();
  await openReady(page, s);
  await typeSql(page, 'select count(*) as n from orders');
  await page.getByTestId('run').click();
  const gauge = page.getByTestId('gauge');
  await expect(gauge).toHaveAttribute('data-state', 'refused');
  await expect(gauge).toContainText('Needs more machine');
  await expect(gauge).toContainText('cap $');
  await expect(page.getByTestId('grid')).toHaveCount(0);
  await page.getByTestId('run-anyway').click();
  await expect(gauge).toHaveAttribute('data-state', 'done');
  await expect(page.getByTestId('grid')).toHaveAttribute('data-rows', '1');
  await expect(page.getByTestId('grid').locator('.grid-row').first()).toContainText('3');
  await expect(page.getByTestId('query').getByTestId('command').locator('code')).toHaveText("querysolo sql 'select count(*) as n from orders' --run-anyway");
  const runs = await history(s, 2);
  expect(runs.map((r) => r.ran_where)).toEqual(['local', 'refused']);
});

test('Esc during a slow query leaves the app responsive and history shows the closed run', async ({ page }) => {
  const s = big();
  await openReady(page, s);
  // 10^10 rows: minutes on any machine (a sort of 20 M rows is 0.2 s on a fast laptop)
  const sql = 'select count(*) as n from range(100000) a, range(100000) b';
  await typeSql(page, sql);
  await page.getByTestId('run').click();
  await expect(page.getByTestId('cancel')).toBeVisible();
  await page.waitForTimeout(500);
  await page.keyboard.press('Escape'); // from wherever the focus is (F0.8.6)
  const gauge = page.getByTestId('gauge');
  await expect(gauge).toHaveAttribute('data-state', 'stopped');
  await expect(page.getByTestId('run')).toBeVisible(); // responsive: ready for the next one
  // the core interrupts the statement and records the run once its result is closed
  await expect.poll(async () => {
    const runs = await history(s, 3);
    const run = runs.find((r) => r.sql_text === sql);
    return run ? { ran: run.ran, error: run.error } : null;
  }, { timeout: 30_000, intervals: [250, 500, 1000] }).toEqual({ ran: true, error: null });
  // and the next query runs at once: the engine is free
  await typeSql(page, 'select 1 as one');
  await page.keyboard.press(`${mod}+Enter`);
  await expect(gauge).toHaveAttribute('data-state', 'done', { timeout: 120_000 });
  await expect(page.getByTestId('grid')).toHaveAttribute('data-rows', '1');
});

test('a statement that does not bind is a line under the box, not a crash', async ({ page }) => {
  const s = big();
  await openReady(page, s);
  await typeSql(page, 'select nope from big');
  await page.keyboard.press(`${mod}+Enter`);
  const gauge = page.getByTestId('gauge');
  await expect(gauge).toHaveAttribute('data-state', 'error');
  await expect(page.getByTestId('sql-error')).toContainText('sql_error');
  await expect(page.getByTestId('run')).toBeVisible();
});
