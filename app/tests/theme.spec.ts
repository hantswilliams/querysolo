// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decision D1, in a real window: the switch changes what the window is actually painted in,
// the choice survives a reload, and System follows the machine. Asserted on the computed
// background rather than on a class name, because the thing that can go wrong is the CSS not
// reaching the page, which a class name would not catch.

import { test, expect, type Page } from '@playwright/test';
import { pageUrl, readState } from './sidecar';

/** The colour the window is actually painted, as the browser computes it. */
const background = (page: Page) =>
  page.evaluate(() => getComputedStyle(document.body).backgroundColor);

const dark = (colour: string) => {
  const [r, g, b] = colour.match(/\d+/g)!.map(Number);
  return (r * 299 + g * 587 + b * 114) / 1000 < 128; // the usual luminance line
};

test('the switch paints the window, and the choice survives a reload', async ({ page }) => {
  await page.goto(pageUrl(readState()));
  await expect(page.getByRole('status')).toHaveText('core ready');

  await page.getByTestId('theme-light').click();
  const light = await background(page);
  expect(dark(light)).toBe(false);

  await page.getByTestId('theme-dark').click();
  const night = await background(page);
  expect(dark(night)).toBe(true);
  expect(night).not.toBe(light);
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');

  // the panels move with it, not just the page behind them
  const panel = await page.getByTestId('tables').evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(dark(panel)).toBe(true);

  await page.reload();
  await expect(page.getByRole('status')).toHaveText('core ready');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  expect(await background(page)).toBe(night);
});

test('System follows the machine, in both directions, with nothing stored', async ({ page }) => {
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.goto(pageUrl(readState()));
  await expect(page.getByRole('status')).toHaveText('core ready');

  // nothing chosen: no attribute, and the media query decides
  await expect(page.locator('html')).not.toHaveAttribute('data-theme', /.*/);
  expect(dark(await background(page))).toBe(true);

  await page.emulateMedia({ colorScheme: 'light' });
  expect(dark(await background(page))).toBe(false);

  // and a choice still overrides the machine
  await page.getByTestId('theme-dark').click();
  expect(dark(await background(page))).toBe(true);
});
