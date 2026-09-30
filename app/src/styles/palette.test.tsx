// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions U3: one palette for the site and the app. `web/src/styles/palette.css` is the
// only place a colour is defined; the app and the site's live layouts and stylesheets read
// tokens and hold no hex of their own (the chart's fallbacks are the palette's own values).
// The exploration concept pages and the site's illustration components (diagrams, the
// demo) are artwork with their own colours and are not held to it; the `.story` palette
// block in exploration.css, which the live site wore, is.

import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const root = join(__dirname, '..', '..', '..');
const PALETTE = join(root, 'web', 'src', 'styles', 'palette.css');
const HEX = /#[0-9a-fA-F]{3,8}\b/g;

const walk = (dir: string, out: string[] = []): string[] => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(css|ts|tsx)$/.test(name) && !name.endsWith('.test.tsx')) out.push(p);
  }
  return out;
};

const SITE_FILES = ['styles/website.css', 'layouts/Base.astro', 'layouts/Docs.astro', 'components/Nav.astro', 'components/Footer.astro', 'components/Brand.astro', 'components/Waitlist.astro'];

describe('the palette', () => {
  const palette = readFileSync(PALETTE, 'utf8');
  const allowed = new Set((palette.match(HEX) ?? []).map((h) => h.toLowerCase()));

  it('defines both sets, and the verdicts keep their three hues in each', () => {
    expect(allowed.size).toBeGreaterThan(20);
    expect(palette).toContain("@media (prefers-color-scheme: dark)");
    expect(palette).toContain(":root[data-theme='dark']");
    for (const token of ['--bg', '--panel', '--ink', '--muted', '--line', '--lake', '--on-lake', '--local', '--slow', '--burst', '--paper', '--accent']) {
      expect(palette).toContain(`${token}:`);
    }
  });

  it('is what the app and the site import, and neither defines a colour outside it', () => {
    expect(readFileSync(join(root, 'app', 'src', 'main.tsx'), 'utf8')).toContain("web/src/styles/palette.css");
    expect(readFileSync(join(root, 'web', 'src', 'layouts', 'Base.astro'), 'utf8')).toContain("styles/palette.css");
    expect(existsSync(join(root, 'app', 'src', 'styles', 'tokens.css'))).toBe(false); // the copy is gone
    expect(existsSync(join(root, 'app', 'src', 'styles', 'theme.css'))).toBe(false);
    const strays: string[] = [];
    const check = (file: string) => {
      const text = readFileSync(file, 'utf8');
      for (const line of text.split('\n')) {
        if (line.includes('theme-color')) continue; // the browser chrome's colour is a meta tag, not CSS
        for (const hex of line.match(HEX) ?? []) {
          if (!allowed.has(hex.toLowerCase())) strays.push(`${relative(root, file)}: ${hex}`);
        }
      }
    };
    for (const file of walk(join(root, 'app', 'src'))) check(file);
    for (const file of SITE_FILES) check(join(root, 'web', 'src', file));
    expect(strays).toEqual([]);
    // the story concept's palette block reads the shared set rather than repeating it
    const story = /\.story\{[^}]*\}/.exec(readFileSync(join(root, 'web', 'src', 'styles', 'exploration.css'), 'utf8'))?.[0] ?? '';
    expect(story.match(HEX)).toBeNull();
  });
});
