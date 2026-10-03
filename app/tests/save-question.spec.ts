// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Versions step 2 (G7): Save as question on the query screen, against the eighth sidecar.
// Its own, not the seventh's: saving writes a model, and the seventh's models test counts
// the models in that project. Run a statement, save it with a title, see the checks and the
// version in the notice, meet the 409 on the same title and take Replace it, then find the
// question on the Models screen with its title as the description — which is the whole of
// G7's sentence, end to end against a real core. Then V3 (decisions 2026-09-16): the
// question is `never` until Refresh what changed builds it, an edit through Save makes it
// `edited`, and refreshing what changed makes it `fresh` again.

import { test, expect } from '@playwright/test';
import { pageUrl, readStates } from './sidecar';

const sidecar = () => readStates()[7];

test('a question is saved from the query screen and appears on the Models screen', async ({ page }) => {
  test.setTimeout(240_000); // dbt compiles when the Models screen plans
  const s = sidecar();
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status')).toHaveText('core ready');

  // Save is offered only once the gauge has spoken.
  await expect(page.getByTestId('save-question')).toHaveCount(0);
  const sql = 'select customer, sum(amt) as total from orders group by 1';
  const editor = page.getByTestId('sql-editor').locator('.cm-content');
  await editor.click();
  await page.keyboard.insertText(sql); // as text: keystrokes meet the editor's own bindings
  await page.keyboard.press('Escape'); // the completion popup the insert opened
  await page.getByTestId('run').click();
  await expect(page.getByTestId('query')).toHaveAttribute('data-done-ms', /\d+/);
  await expect(page.getByTestId('save-question')).toHaveText('Save as question');

  // the title is the only thing asked, and the box says what it will write
  await page.getByTestId('save-question').click();
  await page.getByTestId('question-title').fill('Total by customer');
  const box = page.getByTestId('save-question-box');
  await expect(box).toContainText('models/questions/total_by_customer.sql');
  await expect(box).toContainText('returns at least one row');
  await expect(box).toContainText('`customer` is never empty');
  await expect(box.getByTestId('command')).toContainText("querysolo question save 'Total by customer'");

  await page.getByTestId('question-save').click();
  const saved = page.getByTestId('saved-question');
  await expect(saved).toContainText('Total by customer');
  await expect(saved).toContainText('total_by_customer.sql');
  await expect(page.getByTestId('saved-version')).toContainText(/Version [0-9a-f]{7}\./);
  await page.getByTestId('saved-close').click();

  // the same title again is the core's 409, and Replace it goes through
  await page.getByTestId('save-question').click();
  await page.getByTestId('question-title').fill('Total by customer');
  await page.getByTestId('question-save').click();
  await expect(page.getByTestId('question-exists')).toContainText('total_by_customer');
  await expect(page.getByTestId('question-save')).toHaveCount(0);
  await page.getByTestId('question-replace').click();
  await expect(page.getByTestId('saved-question')).toContainText('Total by customer');
  await page.getByTestId('saved-close').click();

  // the Models screen lists it on its next plan, with the title as its description
  await page.getByTestId('screen-models').click();
  const screen = page.getByTestId('models-screen');
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  const row = screen.getByTestId('dag').locator('tbody tr', { hasText: 'total_by_customer' });
  await expect(row).toHaveCount(1);
  await row.click();
  await expect(screen.getByTestId('model-detail')).toContainText('Total by customer');
  await expect(screen.getByTestId('model-detail')).toContainText('models/questions/total_by_customer.sql');

  // V3: never built; Run what changed is `querysolo run --stale` and builds it
  await expect(row.getByTestId('state')).toHaveText('never');
  await expect(screen.getByTestId('model-detail').getByTestId('state-sentence')).toHaveText('never · never built');
  await expect(screen.getByTestId('run-stale')).toHaveText(/^Run what changed \(\d+\)$/);
  await expect(screen.getByTestId('command').filter({ hasText: 'querysolo run --stale' })).toHaveCount(1);
  // Q1: never built, the detail's button says so and does the run first
  await expect(screen.getByTestId('answer-total_by_customer')).toHaveText('Run, then rows');
  await screen.getByTestId('run-stale').click();
  await expect(screen.getByTestId('run-report')).toContainText('built in', { timeout: 90_000 });
  await expect(row.getByTestId('state')).toHaveText('fresh', { timeout: 90_000 });

  // Q1: Rows is the workspace with `select * from total_by_customer` run — the verdict, the
  // grid with the question's rows, the line beside the box
  await expect(screen.getByTestId('answer-total_by_customer')).toHaveText('Rows');
  await screen.getByTestId('answer-total_by_customer').click();
  await expect(page.getByTestId('workspace')).toBeVisible();
  await expect(page.getByTestId('gauge')).toHaveAttribute('data-verdict', /green|yellow/, { timeout: 30_000 });
  await expect(page.getByTestId('query')).toHaveAttribute('data-done-ms', /\d+/);
  await expect(page.getByTestId('grid')).toContainText('c1');
  await expect(page.getByTestId('query').getByTestId('command').locator('code')).toHaveText("querysolo sql 'select * from total_by_customer'");

  // an edit through Save (the same title, Replace it) makes it edited; refreshing what
  // changed makes it fresh again
  await page.getByTestId('screen-tables').click();
  await editor.click();
  // select-all is ⌘A on a Mac and Ctrl+A elsewhere; Ctrl+A on a Mac moves to the line's start,
  // which prepends the new SQL to the old and fails the query (macOS CI, 2026-10-01)
  await page.keyboard.press('ControlOrMeta+a');
  await page.keyboard.insertText('select customer, sum(amt) as total, count(*) as orders from orders group by 1');
  await page.keyboard.press('Escape');
  await page.getByTestId('run').click();
  await expect(page.getByTestId('query')).toHaveAttribute('data-done-ms', /\d+/);
  await page.getByTestId('save-question').click();
  await page.getByTestId('question-title').fill('Total by customer');
  await page.getByTestId('question-save').click();
  await expect(page.getByTestId('question-exists')).toContainText('total_by_customer');
  await page.getByTestId('question-replace').click();
  await expect(page.getByTestId('saved-question')).toContainText('Total by customer');
  await page.getByTestId('saved-close').click();
  await page.getByTestId('screen-models').click();
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  await expect(row.getByTestId('state')).toHaveText('edited');
  await row.click();
  await expect(screen.getByTestId('model-detail').getByTestId('state-sentence')).toContainText('edited · the SQL changed since the last run');
  // and what changed is shown: the diff of the compiled SQL since the run
  const diff = screen.getByTestId('model-detail').getByTestId('state-diff');
  await expect(diff.locator('.del')).toContainText('sum(amt) as total from');
  await expect(diff.locator('.add')).toContainText('count(*) as orders');
  // the review above the DAG lists it with the same diff, to read before running
  const review = screen.getByTestId('review');
  await expect(review).toContainText('Out of date');
  await expect(review.getByTestId('review-total_by_customer').getByTestId('state-diff').locator('.add')).toContainText('count(*) as orders');
  await screen.getByTestId('run-stale').click();
  await expect(row.getByTestId('state')).toHaveText('fresh', { timeout: 90_000 });
  await expect(screen.getByTestId('model-detail').getByTestId('state-sentence')).toHaveText('fresh');
  await expect(screen.getByTestId('model-detail').getByTestId('what-changed')).toHaveCount(0);
  // and it has left the review — which may still list the seeded question when the
  // versions spec, on the same sidecar, restored it in parallel
  await expect(screen.getByTestId('review-total_by_customer')).toHaveCount(0);
});
