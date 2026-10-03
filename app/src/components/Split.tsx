// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Two panes stacked with a draggable split (decisions U1): the editor above, the results
// below. The top pane's share of the height is remembered for the window, so the next
// launch opens the way it was left; the separator also moves with the arrow keys.

import { useEffect, useRef, useState, type ReactNode } from 'react';

export const SPLIT_KEY = 'querysolo.split';
export const DEFAULT_SPLIT = 0.36;
const MIN = 0.15;
const MAX = 0.85;

export const clampSplit = (f: number) => Math.min(MAX, Math.max(MIN, f));

export function loadSplit(): number {
  try {
    const f = Number(localStorage.getItem(SPLIT_KEY));
    return f > 0 && f < 1 ? clampSplit(f) : DEFAULT_SPLIT;
  } catch {
    return DEFAULT_SPLIT;
  }
}

export function saveSplit(f: number): void {
  try {
    localStorage.setItem(SPLIT_KEY, String(f));
  } catch {
    // a webview without storage: the split lives for the window
  }
}

export interface SplitProps {
  top: ReactNode;
  bottom: ReactNode;
}

export function Split({ top, bottom }: SplitProps) {
  const [split, setSplit] = useState<number>(loadSplit);
  const host = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  useEffect(() => { saveSplit(split); }, [split]);

  function fromPointer(y: number) {
    const box = host.current?.getBoundingClientRect();
    if (!box || box.height === 0) return;
    setSplit(clampSplit((y - box.top) / box.height));
  }

  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    dragging.current = true;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    e.preventDefault();
  }
  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    if (dragging.current) fromPointer(e.clientY);
  }
  function onPointerUp(e: React.PointerEvent<HTMLDivElement>) {
    dragging.current = false;
    (e.target as HTMLElement).releasePointerCapture(e.pointerId);
  }
  function onKeyDown(e: React.KeyboardEvent<HTMLDivElement>) {
    if (e.key === 'ArrowUp') { e.preventDefault(); setSplit((f) => clampSplit(f - 0.05)); }
    else if (e.key === 'ArrowDown') { e.preventDefault(); setSplit((f) => clampSplit(f + 0.05)); }
  }

  return (
    <div className="split" ref={host} data-testid="split" data-split={split.toFixed(2)}>
      <div className="pane top" style={{ flexBasis: `${split * 100}%` }}>{top}</div>
      <div
        className="splitter"
        role="separator"
        aria-orientation="horizontal"
        aria-valuenow={Math.round(split * 100)}
        aria-valuemin={Math.round(MIN * 100)}
        aria-valuemax={Math.round(MAX * 100)}
        tabIndex={0}
        title="Drag to resize; ↑ and ↓ move it too"
        data-testid="splitter"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onKeyDown={onKeyDown}
      />
      <div className="pane bottom">{bottom}</div>
    </div>
  );
}
