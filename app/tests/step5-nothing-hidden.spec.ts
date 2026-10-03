// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 5 gate, the "nothing hidden" line of the definition of done (app brief §6): across
// screens 1 and 2, a chart and the settings panel, the window makes no request to any host
// but the page's own server and the sidecar on loopback. Every request is recorded and
// the hosts are asserted, so a library that phones home would fail this test.

import { test, expect } from '@playwright/test';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pageUrl, readStates } from './sidecar';

const mod = process.platform === 'darwin' ? 'Meta' : 'Control';

test('every request goes to the dev server or the sidecar on loopback, nowhere else', async ({ page }) => {
  test.setTimeout(180_000);
  const s = readStates()[2]; // the big-table sidecar: screen 2 is up
  const hosts = new Set<string>();
  const urls: string[] = [];
  page.on('request', (r) => { const u = new URL(r.url()); hosts.add(u.host); urls.push(r.url()); });

  await page.goto(pageUrl(s));
  await expect(page.getByRole('status').first()).toHaveText('core ready');

  // screen 1: preview a file and import it (a name the other specs do not use)
  const csv = join(s.project, 'audit.csv');
  writeFileSync(csv, 'k,n\na,1\nb,2\nc,3\n');
  await page.getByTestId('path').fill(csv);
  await page.getByTestId('preview-path').click();
  await expect(page.getByTestId('preview')).toBeVisible();
  await page.getByTestId('import').click();
  await expect(page.getByTestId('imported')).toContainText('audit');

  // screen 2: a query with a chart, and a refused one is not needed; then settings
  const editor = page.getByTestId('sql-editor').locator('.cm-content');
  await editor.click();
  await page.keyboard.press(`${mod}+A`);
  await page.keyboard.insertText('select k, n from audit order by k');
  await page.keyboard.press('Escape');
  await page.getByTestId('run').click();
  await expect(page.getByTestId('gauge')).toHaveAttribute('data-state', 'done', { timeout: 60_000 });
  await expect(page.getByTestId('chart').locator('svg .mark-rect.role-mark path')).toHaveCount(3, { timeout: 15_000 });
  await page.keyboard.press(`${mod}+,`);
  await expect(page.getByTestId('settings')).toBeVisible();
  await page.keyboard.press('Escape');
  // The Gauge screen (real-data round): the scatter, and an export that writes a file, sends nothing.
  await page.getByTestId('screen-gauge').click();
  await expect(page.getByTestId('scatter').locator('svg')).toBeVisible({ timeout: 15_000 });
  await page.getByTestId('export').click();
  await expect(page.getByTestId('gauge-notice')).toContainText('written to');
  // The Models screen (step 6): dbt compiles the project (it has no models) and the plan comes back empty; nothing leaves.
  await page.getByTestId('screen-models').click();
  await expect(page.getByTestId('no-models')).toBeVisible({ timeout: 90_000 });

  const allowed = new Set(['localhost:5173', `127.0.0.1:${s.port}`]);
  const strangers = [...hosts].filter((h) => !allowed.has(h));
  expect(strangers, `requests left the machine: ${urls.filter((u) => strangers.some((h) => u.includes(h))).join(', ')}`).toEqual([]);
  expect(urls.length).toBeGreaterThan(10);
  console.log(`${urls.length} requests, hosts: ${[...hosts].join(', ')}`);
});
