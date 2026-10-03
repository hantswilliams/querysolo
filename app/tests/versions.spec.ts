// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Versions step 3 (G6): the Versions section on the model detail, against the eighth
// sidecar, whose question was saved twice by the CLI before the page opened. Technical
// lists the two versions with the diff between them, Gauge then is the estimate of the
// selected version's SQL, Restore this version makes a third and changes the SQL the plan
// compiles; Simple mode shows the same history as sentences with the one button. The save
// spec shares this sidecar and saves a different question, whose versions are not this one's.

import { test, expect } from '@playwright/test';
import { SEEDED_QUESTION, pageUrl, readStates } from './sidecar';

const sidecar = () => readStates()[7];
const name = SEEDED_QUESTION.slug;

test('the versions, the diff, Gauge then and now, Restore as a third version, and Simple mode', async ({ page }) => {
  test.setTimeout(240_000); // dbt compiles when the Models screen plans, and again after the restore
  const s = sidecar();
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status')).toHaveText('core ready');
  await page.getByTestId('mode-technical').click();
  await page.getByTestId('screen-models').click();
  const screen = page.getByTestId('models-screen');
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  await screen.getByTestId('dag').locator('tbody tr', { hasText: name }).click();
  const detail = screen.getByTestId('model-detail');
  await expect(detail).toContainText(SEEDED_QUESTION.title);
  await expect(detail.getByTestId('compiled-sql')).toContainText('order by 2 desc');

  // two versions, newest first, the second save's diff selected
  const versions = detail.getByTestId('versions');
  await expect(versions.getByTestId('git-line')).toHaveText('git · main · origin not set');
  const rows = versions.getByTestId('version-list').locator('tbody tr');
  // 30 s: on a slow macOS runner the list was seen to re-render and take longer than 5 s to
  // come back (CI, 2026-10-01); a laptop and Linux take a fraction of a second
  await expect(rows).toHaveCount(2, { timeout: 30_000 });
  await expect(rows.nth(0)).toContainText(`update question: ${SEEDED_QUESTION.title}`, { timeout: 30_000 });
  await expect(rows.nth(0)).toContainText('checks unchanged', { timeout: 30_000 });
  await expect(rows.nth(0)).toContainText(/[0-9a-f]{7}/, { timeout: 30_000 });
  await expect(rows.nth(1)).toContainText(`save question: ${SEEDED_QUESTION.title}`, { timeout: 30_000 });
  await expect(rows.nth(1)).toContainText('checks changed', { timeout: 30_000 });
  await expect(rows.nth(0)).toHaveClass('on', { timeout: 30_000 });
  await expect(versions.getByTestId('diff-summary')).toContainText('1 line changed');
  await expect(versions.getByTestId('diff').locator('.add')).toContainText('order by 2 desc');
  await expect(versions.getByTestId('diff').locator('.del')).toContainText(SEEDED_QUESTION.first);
  // a question is plain SQL: then is measured, and now is the plan's verdict
  await expect(versions.getByTestId('gauge-then')).toContainText('Runs here · ', { timeout: 30_000 });
  await expect(versions.getByTestId('gauge-now')).toContainText('Runs here · ');
  const firstId = (await rows.nth(1).locator('td').first().textContent())!.trim();
  expect(firstId).toMatch(/^[0-9a-f]{7}$/);

  // select the first version: the file arriving, and its line
  await rows.nth(1).click();
  await expect(rows.nth(1)).toHaveClass('on');
  await expect(versions.getByTestId('diff-summary')).toContainText(`${firstId} against the version before: 3 lines added`);
  await expect(versions.getByTestId('command')).toContainText(`querysolo restore ${name} ${firstId}`);

  // Restore this version: a third version, linear, and the plan compiles the old SQL again
  await versions.getByTestId('restore').click();
  await expect(versions.getByTestId('restored')).toContainText(`Restored ${firstId} as version`, { timeout: 30_000 });
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toContainText(`restore question: ${SEEDED_QUESTION.title} to ${firstId}`);
  await expect(rows.nth(0)).toHaveClass('on');
  await expect(versions.getByTestId('diff').locator('.del')).toContainText('order by 2 desc');
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  await screen.getByTestId('dag').locator('tbody tr', { hasText: name }).click();
  await expect(detail.getByTestId('compiled-sql')).not.toContainText('order by 2 desc', { timeout: 90_000 });
  await expect(detail.getByTestId('compiled-sql')).toContainText('group by 1');

  // Simple mode: History on the card, sentences with no id, and the one button
  await page.getByTestId('mode-simple').click();
  const card = screen.getByTestId(`card-${name}`);
  await expect(card).toBeVisible();
  await expect(card.getByTestId(`history-${name}`)).toHaveText('History');
  await card.getByTestId(`history-${name}`).click();
  const history = card.getByTestId('versions');
  await expect(history).toContainText('History · 3');
  const items = history.getByTestId('version-list').locator('li');
  await expect(items).toHaveCount(3);
  await expect(items.nth(0)).toContainText('just now');
  await expect(items.nth(0)).toContainText('Restored an earlier version · 1 line changed');
  await expect(items.nth(1)).toContainText('Updated · 1 line changed');
  await expect(items.nth(2)).toContainText('Saved · checks changed');
  await expect(history).not.toContainText(/\b[0-9a-f]{7}\b/);
  await expect(history).not.toContainText('git');
  await expect(history.getByTestId('gauge-then')).toContainText('Ready', { timeout: 30_000 });
  await expect(history.getByTestId('gauge-now')).toContainText('Ready');
  await expect(history.getByRole('button')).toHaveCount(1);
  await expect(history.getByRole('button')).toHaveText('Restore this version');
});

test('the Recent strip on the detail, and the Changes screen: the saves, the restore, a run, the tables (L2)', async ({ page }) => {
  test.setTimeout(240_000);
  const s = sidecar();
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status')).toHaveText('core ready');
  await page.getByTestId('mode-technical').click();
  await page.getByTestId('screen-models').click();
  const screen = page.getByTestId('models-screen');
  await expect(screen.getByTestId('dag')).toBeVisible({ timeout: 90_000 });
  await screen.getByTestId('dag').locator('tbody tr', { hasText: name }).click();
  const detail = screen.getByTestId('model-detail');
  const recent = detail.getByTestId('recent');
  // the strip is the last five entries about this question; which five depends on whether
  // the save spec (same sidecar, another worker) ran the DAG first, so only presence is
  // asserted here and the versions are checked on the Changes screen, which lists them all
  await expect(recent.locator('li').first()).toContainText('just now');
  await expect(recent.getByTestId('recent-more')).toBeVisible();
  // a run of the question: a run entry on the strip
  await detail.getByTestId('run-this').click();
  await expect(screen.getByTestId('run-report')).toBeVisible({ timeout: 90_000 });
  await screen.getByTestId('dag').locator('tbody tr', { hasText: name }).click();
  // every run is kept (history schema 2), so the newest run entry is the one just made
  await expect(recent.getByTestId('recent-run').first()).toContainText(`${name} built in`, { timeout: 30_000 });
  await expect(recent.getByTestId('recent-run').first()).toContainText('just now');

  // All changes: the screen arrives filtered to this name, with the CLI's line
  await detail.getByTestId('recent-more').click();
  const changes = page.getByTestId('changes-screen');
  await expect(changes.getByTestId('changes-filter')).toHaveValue(name);
  await expect(changes.getByTestId('feed')).toBeVisible();
  await expect(changes.getByTestId('command')).toContainText(`querysolo changes ${name} --last 100`);
  await expect(changes.getByTestId('entry-run').first()).toContainText(`${name} built in`);
  // the versions the CLI and the test before made: the restore, the update, the first save
  await expect(changes.getByTestId('entry-version').first()).toContainText(`restore question: ${SEEDED_QUESTION.title}`);
  await expect(changes.getByTestId('entry-version').nth(1)).toContainText(`update question: ${SEEDED_QUESTION.title}`);
  await expect(changes.getByTestId('entry-version').last()).toContainText(`save question: ${SEEDED_QUESTION.title}`);
  await expect(changes.getByTestId('entry-snapshot').first()).toContainText(`${name}:`); // the run wrote the question's table

  // the whole project: the import's snapshot and init's version at the bottom, the run at the top
  await changes.getByTestId('changes-filter').fill('');
  await expect(changes.getByTestId('command')).toContainText('querysolo changes --last 100');
  await expect(changes.getByTestId('entry-snapshot').last()).toContainText('orders: append +4 rows');
  await expect(changes.getByTestId('entry-version').last()).toContainText('querysolo init');
  // the run is at the top — unless the save-question spec, on the same sidecar, built its
  // question in the meantime, so the newest run entry about this name is what is asserted
  await expect(changes.getByTestId('entry-run').filter({ hasText: name }).first()).toContainText(`${name} built in`);
  // an entry is a link: the table's opens its detail on the Tables screen
  await changes.getByTestId('entry-snapshot').last().getByTestId('open-orders').click();
  await expect(page.getByTestId('detail')).toContainText('orders · 4 rows');
  await expect(page.getByTestId('detail').getByTestId('recent')).toContainText('orders: append +4 rows');

  // Simple mode: the screen is Recent, and its words
  await page.getByTestId('mode-simple').click();
  await page.getByTestId('screen-changes').click();
  await expect(changes.getByTestId('entry-run').filter({ hasText: name }).first()).toContainText(`${name} refreshed in`);
  await expect(changes.getByTestId('entry-snapshot').last()).toContainText('orders: 4 rows added');
});
