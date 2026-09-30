// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Light and dark (decision D1, September 12). Three choices: System follows the machine,
// Light and Dark override it. The palette itself is CSS (`web/src/styles/palette.css`, shared
// with the site since decisions U3); this file only
// decides which of the three is in force and writes it where CSS can see it.

export type Theme = 'system' | 'light' | 'dark';

export const THEMES: Theme[] = ['system', 'light', 'dark'];

/** The choice the window last made; System when nothing is remembered, so a fresh window
 *  opens the way the machine is set. */
export function loadTheme(): Theme {
  try {
    const stored = localStorage.getItem('querysolo.theme');
    return stored === 'light' || stored === 'dark' ? stored : 'system';
  } catch {
    return 'system';
  }
}

export function saveTheme(theme: Theme): void {
  try {
    localStorage.setItem('querysolo.theme', theme);
  } catch {
    // a webview without storage: the choice lives for the window
  }
}

/** System leaves `data-theme` off, so the media query in the palette decides; Light
 *  and Dark set it, and those rules outrank the media query. */
export function applyTheme(theme: Theme, root: HTMLElement = document.documentElement): void {
  if (theme === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', theme);
}

/** Which of the two palettes is actually showing, for anything that has to draw its own
 *  colours rather than read a token — the chart. */
export function resolvedTheme(theme: Theme = loadTheme()): 'light' | 'dark' {
  if (theme !== 'system') return theme;
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  } catch {
    return 'light';
  }
}

export const themeLabel: Record<Theme, string> = {
  system: 'System',
  light: 'Light',
  dark: 'Dark',
};
