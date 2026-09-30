// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Real-data brief R8, step 4: the Gauge screen shows the runs recorded with their
// estimates and actuals, the tiles, the scatter, and the four verbs: export writes a file
// into the project with no names in it, probe measures the disk again, reset forgets.
// Against the first sidecar, with statements that create no table (step 0 counts its tables).

import { test, expect } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { pageUrl, readState } from './sidecar';

async function run(s: ReturnType<typeof readState>, sql: string) {
  const r = await fetch(`http://127.0.0.1:${s.port}/api/query`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${s.token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql }),
  });
  await r.arrayBuffer(); // drain: the run is recorded when the stream ends
  return r.status;
}

test('the gauge screen lists the runs, draws the scatter, exports without names, probes and resets', async ({ page }) => {
  const s = readState();
  expect(await run(s, 'select sum(range) as total from range(2000000)')).toBe(200);
  expect(await run(s, "select count(*) as n from range(500000) where range % 7 = 0")).toBe(200);
  expect(await run(s, 'select * from nope_table_zz')).toBe(400);

  await page.goto(pageUrl(s));
  await expect(page.getByRole('status')).toHaveText('core ready');
  await page.getByTestId('screen-gauge').click();
  const screen = page.getByTestId('gauge-screen');
  await expect(screen).toBeVisible();
  await expect(page.getByTestId('workspace')).toHaveCount(0); // the Tables screen is the other one; the explorer stays in the sidebar (U2)

  // Tiles and the list (the tiles say — until the summary arrives; wait for it).
  await expect(page.getByTestId('tile-runs')).not.toHaveText('—');
  const runsBefore = Number(await page.getByTestId('tile-runs').textContent());
  expect(runsBefore).toBeGreaterThanOrEqual(3);
  await expect(page.getByTestId('tile-within')).not.toHaveText('—');
  await expect(page.getByTestId('runs')).toContainText('Green');
  await expect(page.getByTestId('runs')).toContainText('failed');
  await expect(page.getByTestId('runs')).not.toContainText('nope_table_zz'); // the sentence is not the SQL
  await expect(screen.getByTestId('command').first()).toContainText('querysolo gauge history');

  // The scatter has a point per completed run with both numbers.
  await expect(page.getByTestId('scatter')).toBeVisible();
  expect(Number(await page.getByTestId('scatter').getAttribute('data-points'))).toBeGreaterThanOrEqual(2);
  await expect(page.getByTestId('scatter').locator('svg')).toBeVisible();

  // Export: a file in the project, the F0.3.9 fields, no SQL in it.
  await page.getByTestId('export').click();
  const notice = page.getByTestId('gauge-notice');
  await expect(notice).toContainText('written to');
  await expect(notice.getByTestId('command')).toContainText('querysolo gauge export');
  const path = /written to (\S+\.jsonl)/.exec((await notice.textContent()) ?? '')![1];
  const lines = readFileSync(path, 'utf8').trim().split('\n');
  expect(lines.length).toBe(runsBefore);
  expect(readFileSync(path, 'utf8')).not.toContain('nope_table_zz');
  expect(readFileSync(path, 'utf8')).not.toContain('select');
  expect(JSON.parse(lines[0])).toHaveProperty('machine.ram_gb');

  // Probe: the machine line carries the new figure.
  await page.getByTestId('probe').click();
  await expect(notice).toContainText('Local disk reads at', { timeout: 60_000 });
  await expect(notice.getByTestId('command')).toContainText('querysolo gauge probe');
  await expect(page.getByTestId('machine')).toContainText('MB/s local disk');

  // Reset asks first, then forgets.
  await page.getByTestId('reset').click();
  await expect(page.getByTestId('confirm-reset')).toBeVisible();
  await page.getByTestId('reset-yes').click();
  await expect(notice).toContainText('forgotten');
  await expect(notice.getByTestId('command')).toContainText('querysolo gauge reset --yes');
  await expect(page.getByTestId('tile-runs')).toHaveText('0');
  await expect(page.getByTestId('runs')).toContainText('No runs yet');
  await expect(page.getByTestId('reset')).toBeDisabled();
});
