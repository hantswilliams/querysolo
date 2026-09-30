// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Real-data brief R5, step 6: the Models screen against the seventh sidecar, whose dbt
// project has `stg` (a view over orders, two tests in schema.yml) and `by_customer` (a
// table over stg). The plan lists both with verdicts; the detail shows the compiled SQL,
// the lineage lines (versions brief G8: each name a link that opens that detail, across
// screens) and the tests; Run all builds through `querysolo run`, the view lands in the
// catalog with its own detail shape, and the Gauge screen has the two runs; Simple mode
// says question and check and the switch is remembered.

import { spawnSync } from 'node:child_process';
import { test, expect } from '@playwright/test';
import { pageUrl, readStates, sidecarExecutable } from './sidecar';

const sidecar = () => readStates()[6];

test('the plan, a model, Run all, the view detail, the runs, and Simple mode', async ({ page }) => {
  test.setTimeout(240_000); // dbt compiles on every plan
  const s = sidecar();
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status')).toHaveText('core ready');
  await expect(page.getByTestId('table-orders')).toContainText('4');
  await expect(page.getByTestId('screen-models')).toHaveText('Models');
  await page.getByTestId('screen-models').click();

  // the plan: both models, in dependency order, with verdicts (dbt compiles first, so give it time)
  const screen = page.getByTestId('models-screen');
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  await expect(screen).toContainText('2 models · all Green');
  const rows = screen.getByTestId('dag').locator('tbody tr');
  await expect(rows).toHaveCount(2);
  await expect(rows.nth(0)).toContainText('stg');
  await expect(rows.nth(0)).toContainText('view');
  await expect(rows.nth(0)).toContainText('Green');
  await expect(rows.nth(0)).toContainText('never');
  await expect(rows.nth(1)).toContainText('by_customer');
  await expect(rows.nth(1)).toContainText('table');
  await expect(screen.getByTestId('command').first()).toContainText('querysolo run');

  // the first model is open: its compiled SQL, lineage, tests, and its line
  const detail = screen.getByTestId('model-detail');
  await expect(detail).toContainText('models/stg.sql');
  await expect(detail).toContainText('Orders with a positive amount.');
  await expect(detail.getByTestId('compiled-sql')).toContainText('amt > 0');
  await expect(detail.getByTestId('compiled-sql')).toContainText('"querysolo"."main"."orders"');
  await expect(detail.getByTestId('reads-from')).toHaveText('orders (table, source)', { timeout: 60_000 });
  await expect(detail.getByTestId('feeds')).toHaveText('by_customer (model, ref)');
  await expect(detail.getByTestId('tests')).toContainText('not_null(id)');
  await expect(detail.getByTestId('tests')).toContainText('unique(id)');
  await expect(detail).toContainText('run: never');
  await expect(detail.getByTestId('command').first()).toContainText('querysolo run stg'); // the Versions section has its own line
  await rows.nth(1).click();
  await expect(detail.getByTestId('reads-from')).toHaveText('stg (model, ref)', { timeout: 60_000 });
  await expect(detail.getByTestId('feeds')).toHaveText('nothing');
  await expect(detail.getByTestId('compiled-sql')).toContainText('sum(amt)');
  await expect(detail.getByTestId('tests')).toContainText('none in schema.yml');

  // G8: a lineage name is a link. A model of this project is selected here; an imported
  // table opens its detail on the Tables screen, whose own lines lead back.
  await detail.getByTestId('lineage-stg').click();
  await expect(rows.nth(0)).toHaveClass('on');
  await expect(detail.getByTestId('feeds')).toHaveText('by_customer (model, ref)', { timeout: 60_000 });
  await detail.getByTestId('lineage-by_customer').click();
  await expect(rows.nth(1)).toHaveClass('on');
  await detail.getByTestId('lineage-stg').click();
  await detail.getByTestId('lineage-orders').click();
  const orders = page.getByTestId('detail');
  await expect(orders).toContainText('orders · 4 rows');
  await expect(orders.getByTestId('reads-from')).toHaveText('nothing', { timeout: 60_000 });
  await expect(orders.getByTestId('feeds')).toHaveText('stg (model, source)');
  await expect(orders.getByTestId('command').first()).toContainText('querysolo tables describe orders');
  await orders.getByTestId('lineage-stg').click();
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  await expect(rows.nth(0)).toHaveClass('on');
  await expect(detail).toContainText('models/stg.sql');

  // Run all is querysolo run: both build, the view is recorded, the plan re-reads with last runs
  await screen.getByTestId('run-all').click();
  await expect(screen.getByTestId('run-report')).toBeVisible({ timeout: 90_000 });
  await expect(screen.getByTestId('run-report')).toContainText('2 models built in');
  await expect(screen.getByTestId('run-report')).toContainText('Views in the catalog: stg.');
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  await expect(rows.nth(0)).toContainText('just now');
  await rows.nth(0).click();
  await expect(detail.getByTestId('last-run')).toContainText('just now, took');

  // the tables panel has the view and the table now; the view's detail has its own shape
  await page.getByTestId('screen-tables').click();
  await expect(page.getByTestId('table-by_customer')).toContainText('2');
  await expect(page.getByTestId('table-stg')).toBeVisible();
  await page.getByTestId('table-stg').click();
  const view = page.getByTestId('detail');
  // the orders detail opened above is still there when the screen comes back (U1: the
  // window holds it), so wait for stg's before reading its kind
  await expect(view).toContainText('stg · view · 3 columns');
  expect(await view.getAttribute('data-kind')).toBe('view');
  await expect(view.getByTestId('view-sql')).toContainText('amt > 0');
  await expect(view.getByTestId('view-sql')).toContainText('"main"."orders"');
  await expect(view.getByTestId('view-version')).toContainText('1 version · this one just now');
  await expect(view.getByTestId('view-model')).toContainText('querysolo run stg');
  await expect(view.getByTestId('reads-from')).toHaveText('orders (table, source)', { timeout: 60_000 });
  await expect(view.getByTestId('feeds')).toHaveText('by_customer (table, ref)');
  await expect(view).not.toContainText('0 rows');
  await expect(view.getByTestId('no-snapshots')).toContainText('nothing to expire');
  await expect(view.getByTestId('expire')).toHaveCount(0);
  await view.getByTestId('sample-rows').click();
  await expect(view.getByTestId('sample')).toContainText('c1');
  await expect(view.getByTestId('sample')).not.toContainText('-1');

  // L1: the Lineage screen draws the project — three nodes in three layers, two edges — and
  // a node is a link: a model to the Models screen with it selected, a table to its detail
  await page.getByTestId('screen-lineage').click();
  const lineage = page.getByTestId('lineage-screen');
  await expect(lineage.getByTestId('graph')).toBeVisible({ timeout: 60_000 });
  await expect(lineage).toContainText('3 nodes, 2 edges');
  await expect(lineage.getByTestId('edge-orders-stg')).toHaveClass('edge source');
  await expect(lineage.getByTestId('edge-stg-by_customer')).toHaveClass('edge ref');
  await expect(lineage.getByTestId('node-stg')).toHaveAttribute('data-state', 'fresh');
  await expect(lineage.getByTestId('node-by_customer')).toHaveAttribute('data-state', 'fresh');
  await expect(lineage.getByTestId('command')).toContainText('querysolo lineage --all');
  await lineage.getByTestId('node-by_customer').click();
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  await expect(rows.nth(1)).toHaveClass('on');
  await page.getByTestId('screen-lineage').click();
  await expect(lineage.getByTestId('graph')).toBeVisible({ timeout: 60_000 });
  await lineage.getByTestId('node-orders').click();
  await expect(page.getByTestId('detail')).toContainText('orders · 4 rows');
  await page.getByTestId('detail').getByRole('button', { name: 'Close' }).click();

  // L3: a commit to orders names the models it made out of date, and one button builds them
  const written = spawnSync(sidecarExecutable(), ['-C', s.project, 'sql', "insert into orders values (99, 'c9', 9.0)"], { encoding: 'utf8' });
  expect(written.status, written.stdout + written.stderr).toBe(0);
  await page.reload(); // the write came from another process; the panel reads the list on open
  await expect(page.getByRole('status')).toHaveText('core ready');
  await expect(page.getByTestId('table-orders')).toContainText('5');
  await page.getByTestId('table-orders').click();
  const ordersDetail = page.getByTestId('detail');
  await expect(ordersDetail).toContainText('orders · 5 rows');
  const newest = ordersDetail.getByTestId('snapshots').locator('tbody tr').first();
  await expect(newest.getByTestId('affects')).toHaveText('made out of date: stg, by_customer');
  await expect(ordersDetail.getByTestId('affected')).toContainText('2 models are out of date because of these commits.');
  await expect(ordersDetail.getByTestId('affected').getByTestId('command')).toContainText('querysolo run --stale');
  await page.getByTestId('screen-lineage').click();
  await expect(lineage.getByTestId('graph')).toBeVisible({ timeout: 60_000 });
  await expect(lineage.getByTestId('node-stg')).toHaveAttribute('data-state', 'upstream');
  await expect(lineage.getByTestId('node-by_customer')).toHaveAttribute('data-state', 'upstream');
  await expect(lineage).toContainText('2 models out of date');
  await page.getByTestId('screen-tables').click();
  await page.getByTestId('table-orders').click();
  await expect(ordersDetail).toContainText('orders · 5 rows');
  await ordersDetail.getByTestId('run-stale').click();
  await expect(page.getByTestId('imported')).toContainText('Built stg, by_customer', { timeout: 90_000 });
  await expect(ordersDetail.getByTestId('affected')).toHaveCount(0);
  await expect(ordersDetail.getByTestId('affects')).toHaveCount(0);
  await ordersDetail.getByRole('button', { name: 'Close' }).click();

  // the Gauge screen has every run: the two builds, the insert, and the two the stale run built
  await page.getByTestId('screen-gauge').click();
  await expect(page.getByTestId('tile-runs')).toHaveText('5');
  await expect(page.getByTestId('runs').locator('tbody tr')).toHaveCount(5);
  await expect(page.getByTestId('runs')).toContainText('Green');

  // Simple mode: questions, checks, the wait as a sentence, Refresh all; remembered across a reload
  await page.getByTestId('mode-simple').click();
  await expect(page.getByTestId('screen-models')).toHaveText('Questions');
  await page.getByTestId('screen-models').click();
  await expect(screen.getByTestId('cards')).toBeVisible({ timeout: 90_000 });
  await expect(screen).toContainText('2 questions · all quick');
  const card = screen.getByTestId('card-stg');
  await expect(card).toContainText('answered live · last refreshed just now');
  await expect(card).toContainText(/Ready (in about|right away)/);
  await expect(card).toContainText('2 checks: id is never empty; id is never repeated');
  await expect(screen.getByTestId('card-by_customer')).toContainText('saved as a table');
  await expect(screen.getByTestId('card-by_customer')).toContainText('no checks');
  await expect(screen.getByTestId('run-all')).toHaveText('Refresh all');
  await expect(screen).not.toContainText('Green');
  await expect(screen.getByTestId('compiled-sql')).toHaveCount(0);
  await page.reload();
  await expect(page.getByRole('status')).toHaveText('core ready');
  await expect(page.getByTestId('screen-models')).toHaveText('Questions');
  await page.getByTestId('mode-technical').click();
  await expect(page.getByTestId('screen-models')).toHaveText('Models');
});
