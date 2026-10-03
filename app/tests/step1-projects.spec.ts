// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 1 gate (app brief §4): each window's sidecar reports the memory limit it was given,
// the second half the first's (A8), and the time from spawn to ready is on the panel. The
// folder dialog, `init` and the recent list are the shell's and are gated in Rust.

import { test, expect } from '@playwright/test';
import { pageUrl, readStates } from './sidecar';

const bytes = (text: string): number => {
  const m = /([\d.]+)\s*(B|KiB|MiB|GiB|TiB)/.exec(text);
  if (!m) throw new Error(`no size in ${JSON.stringify(text)}`);
  return Number(m[1]) * 1024 ** ['B', 'KiB', 'MiB', 'GiB', 'TiB'].indexOf(m[2]);
};

test('the panel shows this window\'s memory limit and how long the core took to be ready', async ({ page }) => {
  const [a] = readStates();
  await page.goto(pageUrl(a));
  await expect(page.getByRole('status')).toHaveText('core ready');
  const limit = page.getByTestId('health').locator('div', { hasText: 'memory limit, this window' });
  await expect(limit).toContainText('GiB'); // 2GB, as DuckDB reports it
  const ready = page.getByTestId('ready-ms');
  await expect(ready).toContainText(/\d+ ms/);
  const ms = Number(/(\d+) ms/.exec((await ready.textContent()) ?? '')![1]);
  expect(ms).toBeGreaterThan(0);
  expect(ms).toBeLessThan(20_000);
  console.log(`spawn to ready, measured as the shell measures it: ${ms} ms`);
});

test('a second window\'s sidecar has half the limit, and health reports it', async ({ page }) => {
  const [a, b] = readStates();
  expect(a.pid).not.toBe(b.pid);
  const limitOf = async (s: typeof a) => {
    await page.goto(pageUrl(s));
    await expect(page.getByRole('status')).toHaveText('core ready');
    const tile = page.getByTestId('health').locator('div', { hasText: 'memory limit, this window' });
    await expect(tile).toContainText(/iB/);
    return bytes((await tile.textContent()) ?? '');
  };
  const first = await limitOf(a);
  const second = await limitOf(b);
  expect(first / second).toBeGreaterThan(1.9);
  expect(first / second).toBeLessThan(2.1);
  await expect(page.getByTestId('project')).toHaveText(b.project.split('/').pop()!);
});
