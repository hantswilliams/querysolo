// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// "Open…" in the bar (app brief A10): the recent projects, the folder dialog, and New
// project… (decisions P1). Each opens in a new window; the one this window shows is left out.

import { useEffect, useRef, useState } from 'react';
import type { RecentProject } from '../lib/session';

export interface OpenMenuProps {
  recent: RecentProject[];
  current?: string | null;
  disabled?: boolean;
  onOpen: (path: string) => void;
  /** The folder dialog. */
  onPick: () => void;
  /** The New project dialog (P1). */
  onNew: () => void;
}

export function OpenMenu({ recent, current, disabled, onOpen, onPick, onNew }: OpenMenuProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const others = recent.filter((p) => p.path !== current);

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', close);
    document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', close); document.removeEventListener('keydown', esc); };
  }, [open]);

  return (
    <div className="open-menu" ref={ref}>
      <button type="button" className="quiet" onClick={() => setOpen((o) => !o)} disabled={disabled} aria-haspopup="menu" aria-expanded={open} data-testid="open-menu">
        Open…
      </button>
      {open && (
        <ul role="menu">
          {others.map((p) => (
            <li key={p.path} role="none">
              <button type="button" role="menuitem" onClick={() => { setOpen(false); onOpen(p.path); }}>
                <b>{p.name}</b><span className="mono">{p.path}</span>
              </button>
            </li>
          ))}
          {others.length > 0 && <li role="separator" />}
          <li role="none">
            <button type="button" role="menuitem" onClick={() => { setOpen(false); onPick(); }}>Other folder…</button>
          </li>
          <li role="none">
            <button type="button" role="menuitem" data-testid="open-new" onClick={() => { setOpen(false); onNew(); }}>New project…<span>a name, and whether its tables live in the folder or in a bucket</span></button>
          </li>
        </ul>
      )}
    </div>
  );
}
