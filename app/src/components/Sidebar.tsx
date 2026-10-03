// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The sidebar (decisions U2): the five screens as entries — Tables, Models, Lineage,
// Changes, Gauge, in Simple mode's words when it is on — with ⌘/Ctrl+1…5 as their keys,
// and under Tables the explorer, so the tables are one click away from any screen. It
// collapses to icons, and its edge drags to the width wanted; both are remembered.

import { useRef, useState, type ReactNode } from 'react';
import type { Mode } from '../lib/vocabulary';
import { words } from '../lib/vocabulary';

export type Screen = 'tables' | 'models' | 'lineage' | 'changes' | 'gauge';

export const SCREENS: Screen[] = ['tables', 'models', 'lineage', 'changes', 'gauge'];

export function screenLabel(screen: Screen, mode: Mode): string {
  switch (screen) {
    case 'tables': return 'Tables';
    case 'models': return words(mode).screen;
    case 'lineage': return mode === 'simple' ? 'Map' : 'Lineage';
    case 'changes': return mode === 'simple' ? 'Recent' : 'Changes';
    case 'gauge': return 'Gauge';
  }
}

/** ⌘/Ctrl+1…5 (U2): the screen a key names, or nothing. */
export function screenForKey(e: { key: string; metaKey: boolean; ctrlKey: boolean; altKey: boolean }): Screen | undefined {
  if (!(e.metaKey || e.ctrlKey) || e.altKey) return undefined;
  const n = Number(e.key);
  return n >= 1 && n <= SCREENS.length ? SCREENS[n - 1] : undefined;
}

const SIDEBAR_KEY = 'querysolo.sidebar';

export function loadCollapsed(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === 'icons';
  } catch {
    return false;
  }
}

function saveCollapsed(collapsed: boolean): void {
  try {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? 'icons' : 'full');
  } catch {
    // a webview without storage: the choice lives for the window
  }
}

// 16px line icons, the palette's stroke: a grid, a branch, a graph, a clock, a dial
const ICONS: Record<Screen, ReactNode> = {
  tables: <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="2" y="3" width="12" height="10" rx="1.5" /><path d="M2 7h12M7 3v10" /></svg>,
  models: <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="4" cy="4" r="1.8" /><circle cx="4" cy="12" r="1.8" /><circle cx="12" cy="8" r="1.8" /><path d="M5.6 4.6 10.4 7.4M5.6 11.4l4.8-2.8" /></svg>,
  lineage: <svg viewBox="0 0 16 16" aria-hidden="true"><rect x="1.5" y="2" width="4" height="3" rx=".8" /><rect x="1.5" y="11" width="4" height="3" rx=".8" /><rect x="10.5" y="6.5" width="4" height="3" rx=".8" /><path d="M5.5 3.5c3 0 2 4.5 5 4.5M5.5 12.5c3 0 2-4.5 5-4.5" /></svg>,
  changes: <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6" /><path d="M8 4.5V8l2.5 1.5" /></svg>,
  gauge: <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M2.5 11.5a6 6 0 0 1 11 0" /><path d="M8 11.5 11 6.5" /><circle cx="8" cy="11.5" r="1" /></svg>,
};

export interface SidebarProps {
  screen: Screen;
  mode: Mode;
  onScreen: (screen: Screen) => void;
  /** The explorer, under Tables. */
  children?: ReactNode;
}

const WIDTH_KEY = 'querysolo.sidebar-width';
export const DEFAULT_WIDTH = 272;
const MIN_WIDTH = 200;
const MAX_WIDTH = 520;

export const clampWidth = (w: number) => Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(w)));

export function loadWidth(): number {
  try {
    const w = Number(localStorage.getItem(WIDTH_KEY));
    return w > 0 ? clampWidth(w) : DEFAULT_WIDTH;
  } catch {
    return DEFAULT_WIDTH;
  }
}

function saveWidth(w: number): void {
  try {
    localStorage.setItem(WIDTH_KEY, String(w));
  } catch {
    // a webview without storage
  }
}

const mod = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘' : 'Ctrl+';

export function Sidebar({ screen, mode, onScreen, children }: SidebarProps) {
  const [collapsed, setCollapsed] = useState<boolean>(loadCollapsed);
  const toggle = () => { saveCollapsed(!collapsed); setCollapsed(!collapsed); };
  const [width, setWidth] = useState<number>(loadWidth);
  const host = useRef<HTMLElement>(null);
  const dragging = useRef(false);

  // the edge drags the width; the pointer's x against the sidebar's left is the width
  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    e.preventDefault();
  }
  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (!dragging.current) return;
    const left = host.current?.getBoundingClientRect().left ?? 0;
    setWidth(clampWidth(e.clientX - left));
  }
  function onPointerUp(e: React.PointerEvent<HTMLDivElement>) {
    dragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    saveWidth(width);
  }
  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'ArrowLeft' || e.key === 'ArrowRight') {
      e.preventDefault();
      const w = clampWidth(width + (e.key === 'ArrowRight' ? 16 : -16));
      setWidth(w);
      saveWidth(w);
    }
  }

  return (
    <aside ref={host} className={`sidebar${collapsed ? ' icons' : ''}`} style={collapsed ? undefined : { width }} data-testid="sidebar" data-collapsed={collapsed ? 'true' : undefined} data-width={collapsed ? undefined : width}>
      <nav className="entries" aria-label="Screens" data-testid="screens">
        {SCREENS.map((s, i) => (
          <button
            key={s}
            type="button"
            className={screen === s ? 'on' : ''}
            onClick={() => onScreen(s)}
            aria-pressed={screen === s}
            title={`${screenLabel(s, mode)} (${mod}${i + 1})`}
            data-key={`${mod}${i + 1}`}
            data-testid={`screen-${s}`}
          >
            {ICONS[s]}
            <span className="label">{screenLabel(s, mode)}</span>
          </button>
        ))}
      </nav>
      {!collapsed && children}
      <button type="button" className="collapse" onClick={toggle} title={collapsed ? 'Show the sidebar' : 'Collapse the sidebar to icons'} aria-expanded={!collapsed} data-testid="sidebar-toggle">
        <svg viewBox="0 0 16 16" aria-hidden="true">{collapsed ? <path d="M6 3l5 5-5 5" /> : <path d="M10 3 5 8l5 5" />}</svg>
        {!collapsed && <span className="label">Collapse</span>}
      </button>
      {!collapsed && (
        <div
          className="sidebar-edge"
          role="separator"
          aria-orientation="vertical"
          aria-valuenow={width}
          aria-valuemin={MIN_WIDTH}
          aria-valuemax={MAX_WIDTH}
          tabIndex={0}
          title="Drag to resize the sidebar; ← and → move it too"
          data-testid="sidebar-edge"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onKeyDown={onKeyDown}
        />
      )}
    </aside>
  );
}
