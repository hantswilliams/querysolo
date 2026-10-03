// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Real-data brief R4, step 2: an s3:// prefix typed where a path goes is previewed (one
// footer's columns, the files and bytes), attached in place on a click, shown in the panel
// with where it is, and refreshed when the bucket gains a file; the public-bucket switch
// attaches without credentials; every action's line is the CLI's. Against the fifth
// sidecar, whose bucket is a Moto server with public-read ACLs.

import { test, expect, type Page } from '@playwright/test';
import { spawnSync } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { pageUrl, readStates, sidecarExecutable } from './sidecar';

const sidecar = () => readStates()[4];

async function openReady(page: Page) {
  await page.goto(pageUrl(sidecar()));
  await expect(page.getByRole('status')).toHaveText('core ready');
}

test('a prefix is previewed, attached in place, shown with its source, and refreshed', async ({ page }) => {
  const s = sidecar();
  const prefix = s.s3!.prefix;
  await openReady(page);
  await expect(page.getByTestId('tables')).toContainText('No tables yet');

  // Typing an s3:// path changes the line beside the box to the CLI's discover.
  await page.getByTestId('path').fill(prefix);
  await expect(page.getByTestId('drop-zone').getByTestId('command')).toContainText(`querysolo tables discover ${prefix}`);
  await expect(page.getByTestId('public-bucket')).toBeVisible();
  await expect(page.getByTestId('no-credentials')).toHaveCount(0); // this sidecar has keys
  await page.getByTestId('preview-path').click();

  // The preview: one footer's columns with their Iceberg types, three files, the bytes.
  await expect(page.getByTestId('preview')).toBeVisible();
  await expect(page.getByTestId('remote-summary')).toContainText('3 Parquet files');
  await expect(page.getByTestId('remote-summary')).toContainText('read in place; nothing is copied');
  await expect(page.getByTestId('preview-events')).toContainText('customer');
  await expect(page.getByTestId('preview-events')).toContainText('string');
  await expect(page.getByTestId('table-name')).toHaveValue('events');
  await expect(page.getByTestId('preview').getByTestId('command')).toContainText(`querysolo tables attach events ${prefix}`);

  // Attach: the panel shows the table, its rows, and where its data is.
  await page.getByTestId('attach').click();
  await expect(page.getByTestId('imported')).toContainText('Attached events (3,000 rows in 3 files) in place; nothing was copied.');
  await expect(page.getByTestId('imported').getByTestId('command')).toContainText(`querysolo tables attach events ${prefix}`);
  await expect(page.getByTestId('table-events')).toContainText('3,000');
  await expect(page.getByTestId('where-events')).toContainText('attached');
  await expect(page.getByTestId('where-events')).toHaveAttribute('title', prefix);

  // The bucket gains a file; Refresh picks it up (D27).
  writeFileSync(s.s3!.flag, '');
  await expect.poll(async () => {
    const r = await fetch(`${s.s3!.endpoint}/querysolo-test/raw/events/part-3.parquet`, { method: 'HEAD' });
    return r.status;
  }, { timeout: 15_000 }).toBe(200);
  await page.getByTestId('refresh-events').click();
  await expect(page.getByTestId('imported')).toContainText('Refreshed events: 1 file added; 4 files, 4,000 rows.');
  await expect(page.getByTestId('imported').getByTestId('command')).toContainText('querysolo tables refresh events');
  await expect(page.getByTestId('table-events')).toContainText('4,000');

  // The same name again is refused with the reason, not a second table.
  await page.getByTestId('path').fill(prefix);
  await page.getByTestId('preview-path').click();
  await page.getByTestId('attach').click();
  await expect(page.getByTestId('import-error')).toContainText('already exists');
});

test('the public-bucket switch attaches without credentials and the panel says public', async ({ page }) => {
  const s = sidecar();
  const prefix = s.s3!.prefix;
  await openReady(page);
  await page.getByTestId('path').fill(prefix);
  await page.getByTestId('public-bucket').locator('input').check();
  await expect(page.getByTestId('drop-zone').getByTestId('command')).toContainText(`querysolo tables discover --anonymous ${prefix}`);
  await page.getByTestId('preview-path').click();
  await expect(page.getByTestId('remote-summary')).toContainText('read in place without credentials');
  await page.getByTestId('table-name').fill('open_events');
  await expect(page.getByTestId('preview').getByTestId('command')).toContainText(`querysolo tables attach open_events --anonymous ${prefix}`);
  await page.getByTestId('attach').click();
  await expect(page.getByTestId('imported')).toContainText('Attached open_events');
  await expect(page.getByTestId('where-open_events')).toContainText('public');
});

test('a local table is published into the bucket from its detail: weighed first, then moved with its history (W2)', async ({ page }) => {
  const s = sidecar();
  // a local table, imported from another process; the panel reads the list on open
  writeFileSync(join(s.project, 'orders.csv'), 'id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n');
  const imported = spawnSync(sidecarExecutable(), ['-C', s.project, 'import', join(s.project, 'orders.csv')], { encoding: 'utf8' });
  expect(imported.status, imported.stdout + imported.stderr).toBe(0);
  await openReady(page);
  await expect(page.getByTestId('table-orders')).toContainText('local');
  await page.getByTestId('table-orders').click();
  const detail = page.getByTestId('detail');
  await expect(detail.getByTestId('detail-where')).not.toContainText('bucket');

  await detail.getByTestId('publish-open').click();
  await detail.getByTestId('publish-prefix').fill('s3://querysolo-test/published');
  await expect(detail.getByTestId('publish-box').getByTestId('command')).toContainText('querysolo tables publish orders s3://querysolo-test/published --dry-run');
  await detail.getByTestId('publish-weigh').click();
  await expect(detail.getByTestId('publish-weighed')).toContainText('to copy to s3://querysolo-test/published/main/orders');
  await expect(detail.getByTestId('publish-box').getByTestId('command')).toContainText('querysolo tables publish orders s3://querysolo-test/published');

  await detail.getByTestId('publish-go').click();
  await expect(page.getByTestId('imported')).toContainText('Published orders to s3://querysolo-test/published/main/orders');
  await expect(page.getByTestId('imported')).toContainText('the local files are orphans for expire');
  await expect(page.getByTestId('imported').getByTestId('command')).toContainText('querysolo tables publish orders s3://querysolo-test/published');
  await expect(page.getByTestId('where-orders')).toContainText('bucket');
  await expect(detail.getByTestId('detail-where')).toContainText('in a bucket');
  await expect(detail.getByTestId('detail-where')).toContainText('s3://querysolo-test/published/main/orders');
  await expect(detail.getByTestId('local-copy')).toContainText('of the local copy still under the project\'s warehouse');
  await expect(detail.getByTestId('publish-open')).toHaveCount(0);
  await expect(detail.getByTestId('snapshots').locator('tbody tr')).toHaveCount(1);
});
