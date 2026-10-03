// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 2 gate (app brief §4): a CSV is previewed with its columns and notes, imported on a
// click, and the panel shows the table with rows and size; a folder lists its files and
// imports one table each; the command beside every action is the exact CLI line. In a
// browser a path is typed where the app takes a drop (the drop itself is Tauri's event).

import { test, expect, type Page } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pageUrl, readStates, venvPython } from './sidecar';

// The second sidecar: nothing imported into it by the earlier steps.
const sidecar = () => readStates()[1];

async function openReady(page: Page) {
  await page.goto(pageUrl(sidecar()));
  await expect(page.getByRole('status')).toHaveText('core ready');
}

async function previewPath(page: Page, path: string) {
  await page.getByTestId('path').fill(path);
  await page.getByTestId('preview-path').click();
  await expect(page.getByTestId('preview')).toBeVisible();
}

function writeParquet(path: string) {
  // A UTINYINT column carries a coercion note.
  const r = spawnSync(venvPython(), ['-c', `import duckdb; duckdb.sql("COPY (SELECT 1::UTINYINT AS tiny, 'x' AS name) TO '${path}' (FORMAT parquet)")`], { encoding: 'utf8' });
  expect(r.status, r.stderr).toBe(0);
}

test('a CSV is previewed, imported on a click, and lands in the panel with rows and size', async ({ page, context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write']);
  const s = sidecar();
  const csv = join(s.project, 'orders.csv');
  writeFileSync(csv, 'id,customer,amt,when\n1,c1,1.5,2026-09-01\n2,c2,3.0,2026-09-02\n3,c1,4.5,2026-09-03\n');
  await openReady(page);
  await expect(page.getByTestId('tables')).toContainText('No tables yet');

  // the command beside the drop zone follows the typed path
  await page.getByTestId('path').fill(csv);
  await expect(page.getByTestId('drop-zone').getByTestId('command')).toContainText(`querysolo import ${csv}`);

  await previewPath(page, csv);
  const preview = page.getByTestId('preview-orders');
  await expect(preview).toContainText('customer');
  await expect(preview).toContainText('long');    // id
  await expect(preview).toContainText('double');  // amt
  await expect(preview).toContainText('date');    // when
  await expect(preview).toContainText('c1');      // the first rows
  await expect(page.getByTestId('tables')).toContainText('No tables yet'); // a preview writes nothing

  // the command is the exact CLI line, and copy puts it on the clipboard
  const command = page.getByTestId('preview').getByTestId('command');
  await expect(command.locator('code')).toHaveText(`querysolo import ${csv}`);
  await command.getByRole('button').click();
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(`querysolo import ${csv}`);

  await page.getByTestId('import').click();
  await expect(page.getByTestId('imported')).toContainText('Imported orders (3 rows)');
  // the explorer's entry (U2): rows, where, and the freshness dot with the time on hover;
  // the size is on the detail
  const row = page.getByTestId('table-orders');
  await expect(row).toContainText('3 rows');
  await expect(row).toContainText('local');
  await expect(page.getByTestId('fresh-orders')).toHaveAttribute('title', 'updated just now');
  await expect(page.getByTestId('fresh-orders')).toHaveClass(/today/);
  await row.locator('button.entry').click();
  await expect(page.getByTestId('detail')).toContainText(/\d+ (B|KB|MB)/);
});

test('a table that exists offers replace or append, and the line says which', async ({ page }) => {
  const s = sidecar();
  const csv = join(s.project, 'orders.csv');
  await openReady(page);
  await expect(page.getByTestId('table-orders')).toBeVisible();
  await previewPath(page, csv);
  await page.getByTestId('import').click();
  await expect(page.getByTestId('exists')).toContainText('orders');
  await page.getByTestId('append').click();
  await expect(page.getByTestId('imported')).toContainText('Imported orders (6 rows)');
  await expect(page.getByTestId('imported').getByTestId('command').locator('code')).toHaveText(`querysolo import ${csv} --append`);
  await expect(page.getByTestId('table-orders')).toContainText('6');
});

test('a folder drop lists three files with their notes and imports one table each', async ({ page }) => {
  const s = sidecar();
  const folder = join(s.project, 'incoming');
  mkdirSync(folder, { recursive: true });
  writeFileSync(join(folder, 'customers.csv'), 'customer,name\nc1,Ann\nc2,Bo\n');
  writeFileSync(join(folder, 'regions.csv'), 'region,n\nnorth,1\nsouth,2\neast,3\nwest,4\n');
  writeParquet(join(folder, 'tiny.parquet'));
  writeFileSync(join(folder, 'notes.txt'), 'skipped');
  await openReady(page);
  await previewPath(page, folder);
  const preview = page.getByTestId('preview');
  await expect(preview).toContainText('incoming');
  await expect(preview).toContainText('3 tables');
  await expect(preview.getByTestId('preview-customers')).toBeVisible();
  await expect(preview.getByTestId('preview-regions')).toBeVisible();
  await expect(preview.getByTestId('preview-tiny')).toContainText('unsigned widened');
  await expect(preview).not.toContainText('notes.txt');
  await expect(preview.getByTestId('command').locator('code')).toHaveText(`querysolo import ${folder}`);
  await page.getByTestId('import').click();
  await expect(page.getByTestId('imported')).toContainText('customers (2 rows)');
  await expect(page.getByTestId('table-regions')).toContainText('4');
  await expect(page.getByTestId('table-tiny')).toContainText('1');
  await expect(page.getByTestId('tables').locator('li')).toHaveCount(4); // orders and the three
});

test('a path that is not data says so without leaving the screen', async ({ page }) => {
  const s = sidecar();
  await openReady(page);
  await page.getByTestId('path').fill(join(s.project, 'querysolo.toml'));
  await page.getByTestId('preview-path').click();
  await expect(page.getByTestId('drop-error')).toContainText('QuerySolo imports');
  await expect(page.getByTestId('drop-zone')).toBeVisible();
});
