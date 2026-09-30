// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 0 gate (app brief §4): the window reaches "core ready", the status strip shows what
// health says, and the explorer is the empty-project state; a table imported through the
// CLI appears in it.

import { test, expect } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pageUrl, readState, sidecarExecutable } from './sidecar';

test('the dot goes green and health renders the versions', async ({ page }) => {
  const s = readState();
  const t0 = Date.now();
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status')).toHaveText('core ready');
  const ready = Date.now() - t0;
  await expect(page.getByTestId('health')).toContainText('querysolo');
  await expect(page.getByTestId('health')).toContainText('DuckDB');
  await expect(page.getByTestId('health')).toContainText('GiB'); // the 2GB limit the sidecar was given
  await expect(page.getByTestId('tables')).toContainText('No tables yet');
  console.log(`page open to core ready: ${ready} ms (browser, warm sidecar)`);
});

test('a table imported through the CLI appears in the panel', async ({ page }) => {
  const s = readState();
  const csv = join(s.project, 'orders.csv');
  writeFileSync(csv, 'id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n');
  const imported = spawnSync(sidecarExecutable(), ['-C', s.project, 'import', csv], { encoding: 'utf8' });
  expect(imported.status, imported.stderr).toBe(0);
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status')).toHaveText('core ready');
  await expect(page.getByTestId('table-orders')).toContainText('3 rows'); // the explorer's entry (U2)
});

test('without a session the window is the welcome screen and says how to get one', async ({ page }) => {
  await page.goto('/');  // no ?port=&token=: no project, as a fresh app launch is (step 1)
  await expect(page.getByTestId('welcome')).toContainText('Open a folder');
  await expect(page.getByTestId('hint')).toContainText('QUERYSOLO_SIDECAR');
  await expect(page.getByRole('status')).toHaveCount(0);
});
