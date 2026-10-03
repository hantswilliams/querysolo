// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// "Copy as command": the CLI line an action is, shown beside it, with a copy button. The
// app never does anything the terminal cannot, and this is where it proves it.

import { useEffect, useState } from 'react';

export function Command({ line, label = 'Copy as command' }: { line: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const t = setTimeout(() => setCopied(false), 1500);
    return () => clearTimeout(t);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(line);
      setCopied(true);
    } catch {
      // no clipboard (an insecure context): the line is selectable text
    }
  }

  return (
    <div className="command" data-testid="command">
      <code>{line}</code>
      <button type="button" className="quiet" onClick={copy} aria-label={label} title={label}>
        {copied ? 'copied' : 'copy'}
      </button>
    </div>
  );
}
