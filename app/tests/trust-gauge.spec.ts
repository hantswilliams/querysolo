// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Trust round T3: a scan the gauge cannot attribute is the fourth state on the query
// screen — "Not estimated", grey, the scan named — and the rows still arrive. Against the
// third sidecar, whose project folder holds the Parquet file its big table was imported
// from, read here directly with read_parquet, outside the catalog.

import { test, expect, type Page } from '@playwright/test';
import { pageUrl, readStates, type Started } from './sidecar';

const big = () => readStates()[2];

async function openReady(page: Page, s: Started) {
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status').first()).toHaveText('core ready');
  await expect(page.getByTestId('sql-editor')).toBeVisible();
}

test('a file read outside the catalog is Not estimated, never Green, and still runs', async ({ page }) => {
  const s = big();
  await openReady(page, s);
  const sql = `select id, c from read_parquet('${s.project}/big.parquet') where id < 10`;
  const editor = page.getByTestId('sql-editor').locator('.cm-content');
  await editor.click();
  await page.keyboard.insertText(sql);
  await page.keyboard.press('Escape');
  await page.getByTestId('run').click();
  const gauge = page.getByTestId('gauge');
  await expect(gauge).toHaveAttribute('data-verdict', 'none');
  await expect(gauge).toContainText('Not estimated');
  await expect(gauge).toContainText('1 scan outside the catalog: read_parquet');
  await expect(gauge).toHaveAttribute('data-state', 'done', { timeout: 120_000 });
  await expect(page.getByTestId('grid')).toHaveAttribute('data-rows', '10');
  await expect(page.getByTestId('run-anyway')).toHaveCount(0);
});
