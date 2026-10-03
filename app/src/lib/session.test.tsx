// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// A window hears the shell's sidecar events for itself only (2026-09-21): the global
// listener of `@tauri-apps/api/event` receives events sent to any window, so a second
// window's "ready" reached the first and swapped its project in.

import { afterEach, describe, expect, it, vi } from 'vitest';

const windowListen = vi.fn(async () => () => {});
const globalListen = vi.fn(async () => () => {});
vi.mock('@tauri-apps/api/webviewWindow', () => ({ getCurrentWebviewWindow: () => ({ listen: windowListen }) }));
vi.mock('@tauri-apps/api/event', () => ({ listen: globalListen }));

afterEach(() => vi.unstubAllGlobals());

describe('onSidecarEvent', () => {
  it('listens on this window, never on every window', async () => {
    vi.stubGlobal('window', Object.assign(window, { __TAURI_INTERNALS__: {} }));
    const { onSidecarEvent } = await import('./session');
    const handler = vi.fn();
    await onSidecarEvent(handler);
    expect(windowListen).toHaveBeenCalledWith('sidecar', expect.any(Function));
    expect(globalListen).not.toHaveBeenCalled();
    // the payload is what reaches the handler
    const cb = (windowListen.mock.calls[0] as unknown as [string, (e: { payload: unknown }) => void])[1];
    cb({ payload: { kind: 'down', stderr: 'x' } });
    expect(handler).toHaveBeenCalledWith({ kind: 'down', stderr: 'x' });
  });
});
