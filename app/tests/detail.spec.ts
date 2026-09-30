// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Real-data brief R7, step 3: a row in the tables panel opens the table's detail: the
// columns, where the data is, the snapshots newest first, what `expire` would reclaim at
// the project's retention, and the sample, expire and refresh buttons with their CLI lines.
// Against the sixth sidecar, whose retention is zero days, so a rebuild (delete then insert,
// the dbt path) leaves expirable snapshots with files only they use.

import { test, expect } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { pageUrl, readStates, sidecarExecutable } from './sidecar';

const sidecar = () => readStates()[5];

function sql(project: string, statement: string) {
  const r = spawnSync(sidecarExecutable(), ['-C', project, 'sql', statement], { encoding: 'utf8' });
  expect(r.status, r.stdout + r.stderr).toBe(0);
}

test('the detail shows columns, snapshots and what expire would reclaim; expire does it', async ({ page }) => {
  const s = sidecar();
  // Two rebuilds in place: five snapshots, the older ones referencing files the current one does not.
  sql(s.project, 'delete from orders');
  sql(s.project, "insert into orders select range as id, 'c' || (range % 3) as customer, range * 2.5 as amt from range(100)");
  sql(s.project, 'delete from orders');
  sql(s.project, "insert into orders select range as id, 'c' || (range % 3) as customer, range * 3.5 as amt from range(200)");

  await page.goto(pageUrl(s));
  await expect(page.getByRole('status')).toHaveText('core ready');
  await expect(page.getByTestId('table-orders')).toContainText('200');
  await page.getByTestId('table-orders').click();

  const detail = page.getByTestId('detail');
  await expect(detail).toBeVisible();
  await expect(detail).toContainText('orders');
  await expect(detail).toContainText('200 rows');
  await expect(detail).toContainText('3 columns');
  await expect(detail.getByTestId('detail-where')).toContainText('local');
  await expect(detail).toContainText('unpartitioned');
  await expect(detail.getByTestId('command').first()).toContainText('querysolo tables describe orders');

  // Five snapshots, newest first, the current one marked, the rest expirable at zero days.
  const rows = detail.getByTestId('snapshots').locator('tbody tr');
  await expect(rows).toHaveCount(5);
  await expect(rows.first()).toContainText('current');
  await expect(rows.nth(1)).toContainText('expirable');
  await expect(detail.getByTestId('reclaimable')).toContainText('4 snapshots older than 0 days');
  await expect(detail.getByTestId('reclaimable')).not.toContainText('0 B reclaimable');

  // Sample rows is `querysolo tables sample`.
  await detail.getByTestId('sample-rows').click();
  await expect(detail.getByTestId('sample')).toContainText('customer');
  await expect(detail.getByTestId('sample').getByTestId('command')).toContainText('querysolo tables sample orders');

  // Expire is `querysolo tables expire`: the report, then one snapshot and nothing to reclaim.
  await expect(detail.getByTestId('expire')).toBeEnabled();
  await detail.getByTestId('expire').click();
  await expect(page.getByTestId('imported')).toContainText('Expired 4 of 5 snapshots of orders');
  await expect(page.getByTestId('imported').getByTestId('command')).toContainText('querysolo tables expire orders');
  await expect(detail.getByTestId('snapshots').locator('tbody tr')).toHaveCount(1);
  await expect(detail.getByTestId('reclaimable')).toContainText('Nothing to expire');
  await expect(detail.getByTestId('expire')).toBeDisabled();
  await expect(page.getByTestId('table-orders')).toContainText('200');
});
