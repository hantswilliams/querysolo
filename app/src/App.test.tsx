// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 4 gate, crash recovery (A11) as the window sees it: a restarted sidecar shows "core
// restarted" and the tables are fetched again from the new port; a sidecar that stopped
// shows its last lines and a way to try again. The supervisor itself is `cargo test`'s.

import { act, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { SidecarEvent } from './lib/session';

let handler: ((e: SidecarEvent) => void) | undefined;
const session = (port: number) => ({ port, token: 't', pid: 1, project: '/p/acme', ready_ms: 400, initialised: null });

vi.mock('./lib/session', () => ({
  inTauri: () => true,
  windowProject: async () => '/p/acme',
  recentProjects: async () => [],
  getSession: async () => session(4001),
  onSidecarEvent: async (h: (e: SidecarEvent) => void) => { handler = h; return () => {}; },
  openProject: async () => {},
  pickFolder: async () => null,
  pickFiles: async () => [],
  onDrop: async () => () => {},
  restartSidecar: async () => {},
}));

const calls: string[] = [];
function fakeFetch(url: string): Promise<Response> {
  calls.push(url);
  const json = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } }));
  if (url.endsWith('/health')) return json({ querysolo: '0.1', duckdb: '1.5.5', project: 'acme', root: '/p/acme', machine: { memory_limit_text: '1 GiB' }, throughput_local_mbps: 100, bandwidth_mbps: null });
  if (url.endsWith('/tables')) return json([]);
  return json({});
}

describe('App and the sidecar events', () => {
  beforeEach(() => { calls.length = 0; vi.stubGlobal('fetch', vi.fn(fakeFetch)); });
  afterEach(() => { vi.unstubAllGlobals(); handler = undefined; });

  it('a restart says so and refetches from the new port; a stop shows the last lines and a restart button', async () => {
    const { default: App } = await import('./App');
    render(<App />);
    await screen.findByText('core ready');
    await waitFor(() => expect(calls.some((u) => u.includes(':4001/api/tables'))).toBe(true));
    expect(handler).toBeDefined();

    await act(async () => { handler!({ kind: 'restarted', session: session(4002) }); });
    await screen.findByText('core restarted');
    await waitFor(() => expect(calls.some((u) => u.includes(':4002/api/tables'))).toBe(true));

    await act(async () => { handler!({ kind: 'down', stderr: 'Traceback: the sidecar fell over' }); });
    await screen.findByText('core stopped');
    expect(screen.getByTestId('error').textContent).toContain('the sidecar fell over');
    expect(screen.getByTestId('restart')).toBeTruthy();
  });

  it('a sidecar killed from outside says nothing; the panel and the button are still there', async () => {
    const { default: App } = await import('./App');
    render(<App />);
    await screen.findByText('core ready');
    await act(async () => { handler!({ kind: 'down', stderr: '' }); });
    await screen.findByText('core stopped');
    expect(screen.getByTestId('error').textContent).toContain('printed nothing');
    expect(screen.getByTestId('restart')).toBeTruthy();
  });
});
