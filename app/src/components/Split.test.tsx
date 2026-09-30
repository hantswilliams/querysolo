// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions U1: the split opens where it was left, moves with a drag and the arrow keys,
// stays within its bounds, and is remembered.

import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { DEFAULT_SPLIT, SPLIT_KEY, Split, clampSplit, loadSplit } from './Split';

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

describe('Split', () => {
  it('opens at the default share, or at the remembered one', () => {
    expect(loadSplit()).toBe(DEFAULT_SPLIT);
    localStorage.setItem(SPLIT_KEY, '0.6');
    expect(loadSplit()).toBe(0.6);
    localStorage.setItem(SPLIT_KEY, 'nonsense');
    expect(loadSplit()).toBe(DEFAULT_SPLIT);
    localStorage.setItem(SPLIT_KEY, '0.01'); // outside the bounds: clamped
    expect(loadSplit()).toBe(clampSplit(0.01));
  });

  it('the arrow keys move the separator and the position is remembered', () => {
    render(<Split top={<p>editor</p>} bottom={<p>rows</p>} />);
    const bar = screen.getByTestId('splitter');
    expect(screen.getByTestId('split').dataset.split).toBe(DEFAULT_SPLIT.toFixed(2));
    fireEvent.keyDown(bar, { key: 'ArrowDown' });
    expect(screen.getByTestId('split').dataset.split).toBe((DEFAULT_SPLIT + 0.05).toFixed(2));
    fireEvent.keyDown(bar, { key: 'ArrowUp' });
    fireEvent.keyDown(bar, { key: 'ArrowUp' });
    expect(screen.getByTestId('split').dataset.split).toBe((DEFAULT_SPLIT - 0.05).toFixed(2));
    expect(Number(localStorage.getItem(SPLIT_KEY))).toBeCloseTo(DEFAULT_SPLIT - 0.05);
    for (let i = 0; i < 30; i++) fireEvent.keyDown(bar, { key: 'ArrowUp' });
    expect(screen.getByTestId('split').dataset.split).toBe('0.15'); // the floor
  });

  it('a drag sets the share from where the pointer is in the host', () => {
    render(<Split top={<p>editor</p>} bottom={<p>rows</p>} />);
    const host = screen.getByTestId('split');
    host.getBoundingClientRect = () => ({ top: 100, height: 400, bottom: 500, left: 0, right: 800, width: 800, x: 0, y: 100, toJSON: () => ({}) });
    const bar = screen.getByTestId('splitter');
    bar.setPointerCapture = () => {};
    bar.releasePointerCapture = () => {};
    // jsdom has no PointerEvent; a MouseEvent under the pointer name carries the y React reads
    const pointer = (type: string, clientY: number) => act(() => { bar.dispatchEvent(new MouseEvent(type, { bubbles: true, clientY })); });
    pointer('pointerdown', 268);
    pointer('pointermove', 340); // 240 of 400 down
    pointer('pointerup', 340);
    expect(host.dataset.split).toBe('0.60');
    pointer('pointermove', 120); // after the button is up: nothing
    expect(host.dataset.split).toBe('0.60');
    expect(localStorage.getItem(SPLIT_KEY)).toBe('0.6');
  });
});
