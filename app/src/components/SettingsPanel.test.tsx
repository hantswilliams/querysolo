// Copyright 2026 Lakelet contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions C1: the Bucket row is the shell's — the profiles on this machine, the
// project's choice, and a change that goes to the shell (which starts the core again).
// The rows from lakelet.toml are covered by the Playwright settings spec.

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { Api } from '../lib/api';
import { SettingsPanel } from './SettingsPanel';

const api = {
  settings: async () => ({ path: '/p/lakelet.toml', settings: { 'engine.memory_limit': 'auto', 'engine.threads': 'auto', 'gauge.share_calibration': false, 'catalog.keep_snapshots_days': 30, 'git.auto_commit': true } }),
  setSetting: async () => { throw new Error('not in this test'); },
} as unknown as Api;

describe('SettingsPanel', () => {
  it('has no Bucket row without the shell, and with it names the profiles and sends the change', async () => {
    const { unmount } = render(<SettingsPanel api={api} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByTestId('setting-engine.threads')).toBeTruthy());
    expect(screen.queryByTestId('setting-bucket')).toBeNull();
    unmount();

    const onProfile = vi.fn(async () => {});
    render(<SettingsPanel api={api} bucket={{ profiles: ['default', 'acme-data', 'personal'], profile: 'acme-data', onProfile }} onClose={() => {}} />);
    const picker = screen.getByTestId('input-bucket-profile') as HTMLSelectElement;
    expect(picker.value).toBe('acme-data');
    expect([...picker.options].map((o) => o.textContent)).toEqual(['the AWS default', 'acme-data', 'personal']);
    expect(screen.getByTestId('setting-bucket').textContent).toContain('lakelet --profile acme-data');
    fireEvent.change(picker, { target: { value: '' } });
    await waitFor(() => expect(onProfile).toHaveBeenCalledWith(null));
    fireEvent.change(picker, { target: { value: 'personal' } });
    await waitFor(() => expect(onProfile).toHaveBeenCalledWith('personal'));
  });

  it('the About row names the version and where the core came from, inside the app only', async () => {
    const { unmount } = render(<SettingsPanel api={api} onClose={() => {}} />);
    await waitFor(() => expect(screen.getByTestId('setting-engine.threads')).toBeTruthy());
    expect(screen.queryByTestId('setting-about')).toBeNull();
    unmount();
    render(<SettingsPanel api={api} about={{ version: '0.1.0', sidecar: '/Applications/Lakelet.app/Contents/Resources/lakelet/lakelet', sidecar_source: 'bundled' }} onClose={() => {}} />);
    expect(screen.getByTestId('setting-about').textContent).toContain('Lakelet 0.1.0');
    expect(screen.getByTestId('setting-about').textContent).toContain('the core that came with the app');
    expect(screen.getByTestId('about-sidecar').textContent).toContain('Resources/lakelet/lakelet');
  });

  it('a change the shell refuses is a line in the panel', async () => {
    render(<SettingsPanel api={api} bucket={{ profiles: ['work'], profile: null, onProfile: async () => { throw new Error('could not save the profile: read-only'); } }} onClose={() => {}} />);
    fireEvent.change(screen.getByTestId('input-bucket-profile'), { target: { value: 'work' } });
    await waitFor(() => expect(screen.getByTestId('settings-error').textContent).toContain('could not save the profile'));
    expect((screen.getByTestId('input-bucket-profile') as HTMLSelectElement).disabled).toBe(false);
  });
});
