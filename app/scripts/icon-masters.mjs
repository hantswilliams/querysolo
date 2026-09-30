// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Render the icon masters (src-tauri/icons/src/querysolo-{mac,linux}.svg) to 1024 px PNGs,
// transparent outside the tile, with the Chromium Playwright already installs. This replaces
// cairosvg, which needs a Cairo library a Mac does not have. Then `npx tauri icon` makes every
// size from the PNGs (icons/README.md).
//
//   node scripts/icon-masters.mjs

import { readFileSync } from 'node:fs';
import { chromium } from 'playwright';

const dir = new URL('../src-tauri/icons/src/', import.meta.url).pathname;
const browser = await chromium.launch();
for (const name of ['mac', 'linux']) {
  const page = await browser.newPage({ viewport: { width: 1024, height: 1024 }, deviceScaleFactor: 1 });
  await page.setContent(`<body style="margin:0;background:transparent">${readFileSync(`${dir}querysolo-${name}.svg`, 'utf8')}</body>`);
  await (await page.$('svg')).screenshot({ path: `${dir}querysolo-${name}.png`, omitBackground: true });
  await page.close();
  console.log(`wrote src-tauri/icons/src/querysolo-${name}.png`);
}
await browser.close();
