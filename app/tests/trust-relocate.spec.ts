// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Trust round T5: a project whose folder was moved opens with the sentence and the Relocate
// button on the Tables screen; the table is listed, marked, never invisible; Relocate is
// `querysolo relocate`, after which the table has its rows again. Against the ninth sidecar.

import { test, expect } from '@playwright/test';
import { pageUrl, readStates } from './sidecar';

const sidecar = () => readStates()[8];

test('a moved project says where it was, and Relocate makes its tables resolve again', async ({ page }) => {
  const s = sidecar();
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status').first()).toHaveText('core ready');
  const moved = page.getByTestId('moved');
  await expect(moved).toBeVisible();
  await expect(moved).toContainText('This project was moved from');
  await expect(moved).toContainText('1 table points at the old folder');
  await expect(moved.getByTestId('command')).toContainText('querysolo relocate');
  await expect(page.getByTestId('moved-orders')).toHaveText('needs relocate');
  await expect(page.getByTestId('table-orders')).toContainText('—');

  await page.getByTestId('relocate').click();
  await expect(page.getByTestId('imported')).toContainText('Relocated 1 table from');
  await expect(page.getByTestId('imported')).toContainText('orders');
  await expect(moved).toHaveCount(0);
  await expect(page.getByTestId('table-orders')).toContainText('3');
  await expect(page.getByTestId('moved-orders')).toHaveCount(0);
  await page.getByTestId('table-orders').click();
  await expect(page.getByTestId('detail')).toContainText('orders · 3 rows');
  await expect(page.getByTestId('detail')).toContainText('local, under the project\'s warehouse');
});
