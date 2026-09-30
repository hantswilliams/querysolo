// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The screenshots in the README, the site and /docs/app, taken from the real app in its
// browser harness against a real sidecar (the same page the Tauri window loads), at 2x.
// Nothing is mocked: the rows, the verdict and the chart are the core's answers on the
// generated sample data (`examples/sample-data`). One command, so a retake after a UI
// change is cheap:
//
//   python3 examples/sample-data/make_sample.py /tmp/shots/sample
//   querysolo init /tmp/shots/lakeside --probe-mb 0 && cd /tmp/shots/lakeside
//   querysolo import ../sample/orders.csv   (and customers, products, daily_sales)
//   querysolo question save "Revenue by region" --sql "..."   (see examples/sample-data/README.md)
//   querysolo run
//   QUERYSOLO_DEV_ORIGIN=http://localhost:5173 querysolo serve &
//   cd app && npm run dev &
//   node scripts/screenshots.mjs /tmp/shots/lakeside <out-dir>
//
// Writes <out-dir>/<name>.png at 2x for each screen, light and dark where the docs show
// both. The browser is Playwright's Chromium (PLAYWRIGHT_CHROMIUM to point at one).

import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { chromium } from '@playwright/test';

const [project, outDir] = process.argv.slice(2);
if (!project || !outDir) {
  console.error('usage: node scripts/screenshots.mjs <project-folder> <out-dir>');
  process.exit(2);
}
const serve = JSON.parse(readFileSync(join(project, '.querysolo', 'serve.json'), 'utf8'));
const origin = process.env.QUERYSOLO_DEV_ORIGIN ?? 'http://localhost:5173';
const url = `${origin}/?port=${serve.port}&token=${serve.token}&project=${encodeURIComponent(resolve(project))}&ready_ms=412`;

const WIDTH = 1440;
const HEIGHT = 900;
const REVENUE = "select region, round(sum(amount)) as revenue from orders where status = 'paid' group by 1 order by 2 desc";
const DAILY = 'select day, revenue from daily_sales order by day';

const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM || undefined });
const context = await browser.newContext({ viewport: { width: WIDTH, height: HEIGHT }, deviceScaleFactor: 2, colorScheme: 'light' });
const page = await context.newPage();
// the key hints read the platform (⌘ on a Mac, Ctrl+ elsewhere); the docs show the Mac
await page.addInitScript(() => Object.defineProperty(navigator, 'platform', { get: () => 'MacIntel' }));

async function shot(name, height = HEIGHT) {
  await page.setViewportSize({ width: WIDTH, height });
  await page.waitForTimeout(400); // fonts, the chart's transition
  await page.screenshot({ path: join(outDir, `${name}.png`) });
  await page.setViewportSize({ width: WIDTH, height: HEIGHT });
  console.log(`  ${name}.png`);
}

async function runSql(sql) {
  const editor = page.getByTestId('sql-editor').locator('.cm-content');
  await editor.click();
  await page.keyboard.press('Meta+A') // the page believes it is a Mac (above), so the editor's select-all is Meta;
  await page.keyboard.insertText(sql);
  await page.keyboard.press('Escape');
  await page.getByTestId('run').click();
  await page.getByTestId('query').getAttribute('data-done-ms');
  await page.waitForFunction(() => /\d+/.test(document.querySelector('[data-testid="query"]')?.getAttribute('data-done-ms') ?? ''));
}

await page.goto(url);
await page.getByTestId('table-orders').waitFor();
await page.getByTestId('mode-technical').click();
await page.getByTestId('theme-light').click();

// 1. the workspace: the revenue question, the verdict, the chart and the grid
await runSql(REVENUE);
await shot('workspace');
await page.getByTestId('theme-dark').click();
await shot('workspace-dark');
await page.getByTestId('theme-light').click();

// 2. a line chart, from the daily table
await runSql(DAILY);
await shot('workspace-line');

// 3. a table's detail in the results pane (the explorer's entry)
await page.getByTestId('table-orders').locator('button.entry').click();
await page.getByTestId('detail').waitFor();
await shot('detail');

// 4. Questions (Simple) with See the answer, then the answer
await page.getByTestId('mode-simple').click();
await page.getByTestId('screen-models').click();
await page.getByTestId('card-revenue_by_region').waitFor();
await shot('questions', 720);
await page.getByTestId('answer-revenue_by_region').click();
await page.waitForFunction(() => /\d+/.test(document.querySelector('[data-testid="query"]')?.getAttribute('data-done-ms') ?? ''));
await shot('answer');

// 5. Models (Technical) with a model open
await page.getByTestId('mode-technical').click();
await page.getByTestId('screen-models').click();
await page.getByTestId('model-revenue_by_region').waitFor();
await page.getByTestId('model-revenue_by_region').click();
await page.getByTestId('model-detail').waitFor();
await shot('models');

// 6. Lineage, Changes, Gauge
await page.getByTestId('screen-lineage').click();
await page.getByTestId('lineage-screen').waitFor();
await shot('lineage', 720);
await page.getByTestId('screen-changes').click();
await page.getByTestId('changes-screen').waitFor();
await shot('changes');
await page.getByTestId('screen-gauge').click();
await page.getByTestId('gauge-screen').waitFor();
await shot('gauge', 900);

// 7. the welcome screen and New project…
await page.goto(`${origin}/`);
await page.getByTestId('new-project-button').waitFor();
await shot('welcome', 720);
await page.getByTestId('new-project-button').click();
await page.getByTestId('project-name').fill('lakeside');
await page.getByTestId('where-bucket').click();
await page.getByTestId('warehouse').fill('s3://lakeside-data/warehouse');
await shot('new-project');

await browser.close();
