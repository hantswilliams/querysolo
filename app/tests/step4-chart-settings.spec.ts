// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 4 gate (app brief §4): a bar chart for a group-by and none for two numbers (A5);
// settings write querysolo.toml in place and the CLI reads them. Crash recovery is gated in
// Rust (the supervisor) and Vitest (the window's reaction); a browser has no sidecar to kill.

import { test, expect, type Page } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pageUrl, readStates, sidecarExecutable, type Started } from './sidecar';

const mod = process.platform === 'darwin' ? 'Meta' : 'Control';

async function openReady(page: Page, s: Started) {
  await page.goto(pageUrl(s));
  await expect(page.getByRole('status').first()).toHaveText('core ready');
}

async function runSql(page: Page, sql: string) {
  const editor = page.getByTestId('sql-editor').locator('.cm-content');
  await editor.click();
  await page.keyboard.press(`${mod}+A`);
  await page.keyboard.insertText(sql);
  await page.keyboard.press('Escape');
  await page.getByTestId('run').click();
  await expect(page.getByTestId('gauge')).toHaveAttribute('data-state', 'done', { timeout: 60_000 });
}

test('a group-by draws a bar chart with one bar per group, and two numbers draw nothing', async ({ page }) => {
  const s = readStates()[2]; // the 20 M-row table
  await openReady(page, s);
  await runSql(page, 'select c, count(*) as n from big group by c order by c limit 12');
  const chart = page.getByTestId('chart');
  await expect(chart).toHaveAttribute('data-kind', 'bar');
  await expect(chart).toContainText('n by c');
  const bars = chart.locator('svg .mark-rect.role-mark path');
  await expect(bars).toHaveCount(12, { timeout: 15_000 });
  await expect(chart.locator('svg')).toContainText('c0'); // the axis names the groups
  // no dual axis, no legend, one hue
  await expect(chart.locator('svg .role-legend')).toHaveCount(0);
  expect(await bars.first().getAttribute('fill')).toBe('#164F44');

  await runSql(page, 'select id, x from big where id < 20');
  await expect(page.getByTestId('chart')).toHaveCount(0);
  await expect(page.getByTestId('grid')).toHaveAttribute('data-rows', '20');
});

test('dates, timestamps and decimals read as dates, timestamps and numbers in the grid', async ({ page }) => {
  // The big-table sidecar, not the second one: step 2 counts the second one's tables, and
  // the spec files run on several workers at once outside CI.
  const s = readStates()[2];
  const csv = join(s.project, 'dated.csv');
  writeFileSync(csv, 'when,amt\n2026-09-01,1.5\n2026-09-02,3.0\n2026-09-03,4.5\n');
  const imported = spawnSync(sidecarExecutable(), ['-C', s.project, 'import', csv, '--replace'], { encoding: 'utf8' });
  expect(imported.status, imported.stderr).toBe(0);
  await openReady(page, s);
  await runSql(page, "select \"when\", cast(amt as decimal(10, 2)) as d, timestamp '2026-09-01 10:11:12' as ts, time '10:11:12' as t from dated order by 1 limit 1");
  const row = page.getByTestId('grid').locator('.grid-row').first();
  await expect(row).toContainText('2026-09-01');
  await expect(row).toContainText('1.50');
  await expect(row).toContainText('2026-09-01T10:11:12');
  await expect(row).toContainText('10:11:12');
  await expect(row).not.toContainText('1,7'); // not milliseconds
  // a date and a decimal is still a line chart
  await runSql(page, 'select "when", cast(amt as decimal(10, 2)) as amount from dated order by 1');
  await expect(page.getByTestId('chart')).toHaveAttribute('data-kind', 'line');
  await expect(page.getByTestId('chart').locator('svg')).toContainText('amount');
});

test('settings write querysolo.toml in place and `querysolo config show` reads them', async ({ page }) => {
  const s = readStates()[1];
  await openReady(page, s);
  const toml = join(s.project, 'querysolo.toml');
  const before = readFileSync(toml, 'utf8');
  expect(before).toContain('threads = "auto"');

  await page.keyboard.press(`${mod}+,`); // the settings key
  const panel = page.getByTestId('settings');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('querysolo.toml');

  const threads = page.getByTestId('input-engine.threads');
  await threads.fill('3');
  await expect(page.getByTestId('setting-engine.threads').getByTestId('command').locator('code')).toHaveText('querysolo config set engine.threads 3');
  await page.getByTestId('save-engine.threads').click();
  await expect(page.getByTestId('save-engine.threads')).toHaveText('saved');
  await page.getByTestId('input-gauge.share_calibration').check();
  await expect(page.getByTestId('setting-gauge.share_calibration').getByTestId('command').locator('code')).toHaveText('querysolo config set gauge.share_calibration true');

  await expect.poll(() => readFileSync(toml, 'utf8')).toContain('share_calibration = true');
  const after = readFileSync(toml, 'utf8');
  expect(after).toContain('threads = 3');
  expect(after).toContain('# DuckDB default, 80% of RAM'); // edited in place, comments kept
  expect(after.split('\n').length).toBe(before.split('\n').length);

  // a bad value is a line in the panel, not a write
  await page.getByTestId('input-engine.memory_limit').fill('lots');
  await page.getByTestId('save-engine.memory_limit').click();
  await expect(page.getByTestId('settings-error')).toContainText('takes auto or a size');
  expect(readFileSync(toml, 'utf8')).toContain('memory_limit = "auto"');

  // the CLI reads them
  const shown = spawnSync(sidecarExecutable(), ['-C', s.project, 'config', 'show'], { encoding: 'utf8' });
  expect(shown.status, shown.stderr).toBe(0);
  expect(shown.stdout).toContain('engine.threads = 3');
  expect(shown.stdout).toContain('gauge.share_calibration = True');

  await page.keyboard.press('Escape');
  await expect(panel).toHaveCount(0);
});
