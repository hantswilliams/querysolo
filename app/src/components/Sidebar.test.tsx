// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions U2: the five entries in the mode's words, the one that is on, the keys, the
// explorer under them, and the collapse to icons that is remembered.

import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_WIDTH, SCREENS, Sidebar, clampWidth, loadCollapsed, loadWidth, screenForKey, screenLabel } from './Sidebar';

// Node 22 and newer expose a `localStorage` global of their own that shadows jsdom's and
// has no `clear()` (it failed on the Mac); this storage depends on neither.
function emptyStorage() {
  const items = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => items.get(k) ?? null,
    setItem: (k: string, v: string) => { items.set(k, v); },
    removeItem: (k: string) => { items.delete(k); },
  });
}

beforeEach(emptyStorage);
afterEach(() => vi.unstubAllGlobals());

// the key's modifier as the sidebar spells it on this machine (the key hint is CSS text from `data-key`)
const modKey = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl+';

describe('Sidebar', () => {
  it('lists the five screens in order, in Technical and Simple words, with the one that is on pressed', () => {
    const onScreen = vi.fn();
    const { rerender } = render(<Sidebar screen="lineage" mode="technical" onScreen={onScreen}><p>the explorer</p></Sidebar>);
    const nav = screen.getByTestId('screens');
    expect([...nav.querySelectorAll('button')].map((b) => b.textContent)).toEqual(['Tables', 'Models', 'Lineage', 'Changes', 'Gauge']);
    expect([...nav.querySelectorAll('button')].map((b) => b.dataset.key)).toEqual(['⌘1', '⌘2', '⌘3', '⌘4', '⌘5'].map((k) => k.replace('⌘', modKey)));
    expect(screen.getByTestId('screen-lineage').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('screen-tables').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByText('the explorer')).toBeTruthy();
    fireEvent.click(screen.getByTestId('screen-gauge'));
    expect(onScreen).toHaveBeenCalledWith('gauge');

    rerender(<Sidebar screen="changes" mode="simple" onScreen={onScreen} />);
    expect(SCREENS.map((s) => screenLabel(s, 'simple'))).toEqual(['Tables', 'Questions', 'Map', 'Recent', 'Gauge']);
    expect(screen.getByTestId('screen-models').textContent).toContain('Questions');
    expect(screen.getByTestId('screen-changes').getAttribute('aria-pressed')).toBe('true');
  });

  it('⌘/Ctrl+1…5 name the screens; other keys and Alt do not', () => {
    const key = (k: string, mods: Partial<{ metaKey: boolean; ctrlKey: boolean; altKey: boolean }> = {}) => screenForKey({ key: k, metaKey: false, ctrlKey: false, altKey: false, ...mods });
    expect(key('1', { metaKey: true })).toBe('tables');
    expect(key('2', { ctrlKey: true })).toBe('models');
    expect(key('5', { metaKey: true })).toBe('gauge');
    expect(key('6', { metaKey: true })).toBeUndefined();
    expect(key('1')).toBeUndefined();
    expect(key('1', { metaKey: true, altKey: true })).toBeUndefined();
    expect(key('k', { metaKey: true })).toBeUndefined();
  });

  it('collapses to icons on a click, hides the explorer, and remembers it', () => {
    const { unmount } = render(<Sidebar screen="tables" mode="technical" onScreen={() => {}}><p>the explorer</p></Sidebar>);
    expect(screen.getByTestId('sidebar').dataset.collapsed).toBeUndefined();
    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.getByTestId('sidebar').dataset.collapsed).toBe('true');
    expect(screen.queryByText('the explorer')).toBeNull();
    expect(screen.getByTestId('screen-tables').getAttribute('title')).toMatch(/^Tables \((⌘|Ctrl\+)1\)$/); // the name survives as the tooltip
    expect(loadCollapsed()).toBe(true);
    unmount();
    render(<Sidebar screen="tables" mode="technical" onScreen={() => {}}><p>the explorer</p></Sidebar>);
    expect(screen.getByTestId('sidebar').dataset.collapsed).toBe('true');
    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.getByText('the explorer')).toBeTruthy();
    expect(loadCollapsed()).toBe(false);
  });

  it('the edge drags the width, the arrows move it, both within bounds, and it is remembered', () => {
    expect(loadWidth()).toBe(DEFAULT_WIDTH);
    const { unmount } = render(<Sidebar screen="tables" mode="technical" onScreen={() => {}}><p>the explorer</p></Sidebar>);
    const aside = screen.getByTestId('sidebar');
    aside.getBoundingClientRect = () => ({ left: 0, top: 0, width: DEFAULT_WIDTH, height: 800, right: DEFAULT_WIDTH, bottom: 800, x: 0, y: 0, toJSON: () => ({}) });
    const edge = screen.getByTestId('sidebar-edge');
    edge.setPointerCapture = () => {};
    edge.releasePointerCapture = () => {};
    // jsdom has no PointerEvent; a MouseEvent under the pointer name carries the x React reads
    const pointer = (type: string, clientX: number) => act(() => { edge.dispatchEvent(new MouseEvent(type, { bubbles: true, clientX })); });
    pointer('pointerdown', DEFAULT_WIDTH);
    pointer('pointermove', 340);
    expect(aside.dataset.width).toBe('340');
    expect(aside.style.width).toBe('340px');
    pointer('pointermove', 900); // past the ceiling
    expect(aside.dataset.width).toBe(String(clampWidth(900)));
    pointer('pointerup', 900);
    expect(loadWidth()).toBe(clampWidth(900));
    pointer('pointermove', 300); // after the button is up: nothing
    expect(aside.dataset.width).toBe(String(clampWidth(900)));
    fireEvent.keyDown(edge, { key: 'ArrowLeft' });
    expect(aside.dataset.width).toBe(String(clampWidth(900) - 16));
    expect(loadWidth()).toBe(clampWidth(900) - 16);
    for (let i = 0; i < 40; i++) fireEvent.keyDown(edge, { key: 'ArrowLeft' });
    expect(aside.dataset.width).toBe(String(clampWidth(0))); // the floor
    // collapsed: no edge, no inline width; the remembered width comes back with the explorer
    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.queryByTestId('sidebar-edge')).toBeNull();
    expect(aside.style.width).toBe('');
    unmount();
    render(<Sidebar screen="tables" mode="technical" onScreen={() => {}} />);
    fireEvent.click(screen.getByTestId('sidebar-toggle'));
    expect(screen.getByTestId('sidebar').dataset.width).toBe(String(clampWidth(0)));
  });
});
