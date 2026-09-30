// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// F0.8.2: sidecar readiness is a small dot with a word, never a splash screen.

export type Status = 'starting' | 'ready' | 'restarted' | 'down';

const WORDS: Record<Status, string> = {
  starting: 'starting the core',
  ready: 'core ready',
  restarted: 'core restarted',
  down: 'core stopped',
};

export function StatusDot({ status, detail }: { status: Status; detail?: string }) {
  return (
    <span className={`status ${status}`} role="status" aria-live="polite" title={detail}>
      <i aria-hidden="true" />
      {WORDS[status]}
    </span>
  );
}
