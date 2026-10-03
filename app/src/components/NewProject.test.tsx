// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions P1: the dialog takes a name under a parent, offers the two places for the
// tables, checks a bucket before the folder is made and refuses to make it when the check
// fails, and shows the `querysolo init` line it runs.

import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { BucketCheck } from '../lib/session';
import { NO_AWS, NewProject, credentialsLine, isProjectName } from './NewProject';

const creds = { configured: true, source: 'environment' as const, profile: null, region: 'us-east-1', endpoint: null };
const pass = (prefix: string): BucketCheck => ({ prefix, ok: true, read: true, write: true, error: null, sentence: `${prefix} is writable with keys from the environment; one object was written and removed.`, credentials: creds });
const fail = (prefix: string): BucketCheck => ({ prefix, ok: false, read: true, write: false, error: 'ACCESS_DENIED during PutObject operation', sentence: `${prefix}: ACCESS_DENIED during PutObject operation (keys from the environment).`, credentials: creds });

const base = { canCreate: true, defaultParent: '/home/h/Documents', onChooseParent: async () => null, onClose: () => {} };

describe('NewProject', () => {
  it('a project name is one folder name', () => {
    expect(isProjectName(' acme ')).toBe(true);
    for (const bad of ['', ' ', '.', '..', 'a/b', 'a\\b']) expect(isProjectName(bad)).toBe(false);
  });

  it('in this folder: the name under the parent, the init line, Create makes it', async () => {
    const onCreate = vi.fn(async () => {});
    render(<NewProject {...base} check={async (p) => pass(p)} onCreate={onCreate} />);
    const create = screen.getByTestId('create-project') as HTMLButtonElement;
    expect(create.disabled).toBe(true);
    expect(screen.getByTestId('project-parent').textContent).toBe('/home/h/Documents');
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: 'a/b' } });
    expect(screen.getByTestId('name-error')).toBeTruthy();
    expect(create.disabled).toBe(true);
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: ' acme ' } });
    expect(screen.queryByTestId('name-error')).toBeNull();
    expect(screen.getByTestId('project-folder').textContent).toBe('/home/h/Documents/acme');
    expect(screen.getByTestId('command').textContent).toContain('querysolo init /home/h/Documents/acme');
    expect(screen.getByTestId('command').textContent).not.toContain('--warehouse');
    expect(create.disabled).toBe(false);
    expect(create.textContent).toBe('Create');
    fireEvent.click(create);
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith('/home/h/Documents', 'acme', undefined, undefined));
  });

  it('Choose… changes the parent', async () => {
    render(<NewProject {...base} onChooseParent={async () => '/data/lakes'} check={async (p) => pass(p)} onCreate={async () => {}} />);
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: 'acme' } });
    await act(async () => { fireEvent.click(screen.getByTestId('choose-parent')); });
    expect(screen.getByTestId('project-parent').textContent).toBe('/data/lakes');
    expect(screen.getByTestId('project-folder').textContent).toBe('/data/lakes/acme');
  });

  it('in a bucket: the prefix is checked before the folder is made, and a failed check stops it', async () => {
    const check = vi.fn(async (p: string) => (p.startsWith('s3://denied') ? fail(p) : pass(p)));
    const onCreate = vi.fn(async () => {});
    render(<NewProject {...base} check={check} onCreate={onCreate} aws={{ ...creds, configured: false, source: 'none' }} />);
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: 'acme' } });
    fireEvent.click(screen.getByTestId('where-bucket'));
    const create = screen.getByTestId('create-project') as HTMLButtonElement;
    expect(create.disabled).toBe(true); // no prefix yet
    expect(screen.getByTestId('no-credentials')).toBeTruthy(); // the core has none, said before the check
    fireEvent.change(screen.getByTestId('warehouse'), { target: { value: 's3://acme-lake' } });
    expect(screen.getByTestId('warehouse-error')).toBeTruthy();
    fireEvent.change(screen.getByTestId('warehouse'), { target: { value: ' s3://denied-lake/analytics ' } });
    expect(screen.queryByTestId('warehouse-error')).toBeNull();
    expect(screen.getAllByTestId('command').at(-1)?.textContent).toContain('querysolo init /home/h/Documents/acme --warehouse s3://denied-lake/analytics'); // the last line is the footer's; `aws configure` sits above it (C2)
    expect(create.textContent).toBe('Check and create');
    fireEvent.click(create);
    await waitFor(() => expect(screen.getByTestId('check-result').dataset.ok).toBe('false'));
    expect(check).toHaveBeenCalledWith('s3://denied-lake/analytics', undefined);
    expect(screen.getByTestId('check-result').textContent).toContain('ACCESS_DENIED');
    expect(onCreate).not.toHaveBeenCalled();
    // a prefix that passes: the check's sentence, then Create makes the folder with the warehouse
    fireEvent.change(screen.getByTestId('warehouse'), { target: { value: 's3://acme-lake/analytics' } });
    expect(screen.queryByTestId('check-result')).toBeNull(); // the result was for the other prefix
    fireEvent.click(screen.getByTestId('check-bucket'));
    await waitFor(() => expect(screen.getByTestId('check-result').dataset.ok).toBe('true'));
    expect(screen.queryByTestId('no-credentials')).toBeNull();
    expect(create.textContent).toBe('Create');
    fireEvent.click(create);
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith('/home/h/Documents', 'acme', 's3://acme-lake/analytics', undefined));
    expect(check).toHaveBeenCalledTimes(2); // not checked again on Create
  });

  it('C2: the line under the prefix is one of three sentences', () => {
    expect(credentialsLine('acme-data', [], undefined)).toBe('Using profile acme-data.');
    expect(credentialsLine('', ['default', 'work'], undefined)).toBe('No profile chosen; the AWS default profile will be used.');
    expect(credentialsLine('', undefined, creds)).toBe('No profile chosen; the AWS default profile will be used.');
    expect(credentialsLine('', [], undefined)).toBe(NO_AWS);
    expect(credentialsLine('', undefined, { ...creds, configured: false, source: 'none' })).toBe(NO_AWS);
    expect(credentialsLine('', undefined, undefined)).toBeUndefined(); // nothing known yet
  });

  it('C1: the profile picker names the machine\'s profiles, the check and the folder use the choice, and the lines say so', async () => {
    const check = vi.fn(async (p: string, profile?: string) => ({ ...pass(p), credentials: { ...creds, source: 'profile' as const, profile: profile ?? 'default' } }));
    const onCreate = vi.fn(async () => {});
    render(<NewProject {...base} check={check} onCreate={onCreate} profiles={['default', 'client-b', 'work']} />);
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: 'acme' } });
    fireEvent.click(screen.getByTestId('where-bucket'));
    const picker = screen.getByTestId('profile') as HTMLSelectElement;
    expect([...picker.options].map((o) => o.textContent)).toEqual(['the AWS default', 'client-b', 'work']); // default is the blank choice, not a second entry
    expect(screen.getByTestId('credentials-line').textContent).toBe('No profile chosen; the AWS default profile will be used.');
    expect(screen.queryByTestId('no-credentials')).toBeNull();
    fireEvent.change(picker, { target: { value: 'client-b' } });
    expect(screen.getByTestId('credentials-line').textContent).toBe('Using profile client-b.');
    fireEvent.change(screen.getByTestId('warehouse'), { target: { value: 's3://acme-lake/analytics' } });
    expect(screen.getByText(/querysolo --profile client-b bucket check s3:\/\/acme-lake\/analytics/)).toBeTruthy();
    fireEvent.click(screen.getByTestId('check-bucket'));
    await waitFor(() => expect(screen.getByTestId('check-result').dataset.ok).toBe('true'));
    expect(check).toHaveBeenCalledWith('s3://acme-lake/analytics', 'client-b');
    // another profile: the result was for the other one, so it is checked again on Create
    fireEvent.change(picker, { target: { value: 'work' } });
    expect(screen.queryByTestId('check-result')).toBeNull();
    expect(screen.getByTestId('create-project').textContent).toBe('Check and create');
    fireEvent.click(screen.getByTestId('create-project'));
    await waitFor(() => expect(onCreate).toHaveBeenCalledWith('/home/h/Documents', 'acme', 's3://acme-lake/analytics', 'work'));
    expect(check).toHaveBeenLastCalledWith('s3://acme-lake/analytics', 'work');
    expect(screen.getAllByTestId('command').some((c) => c.textContent?.includes("querysolo --profile work init /home/h/Documents/acme --warehouse s3://acme-lake/analytics"))).toBe(true);
  });

  it('C2: a machine with no AWS files gets the aws configure line to copy, and no picker in a browser', () => {
    const { unmount } = render(<NewProject {...base} check={async (p) => pass(p)} onCreate={async () => {}} profiles={[]} />);
    fireEvent.click(screen.getByTestId('where-bucket'));
    expect(screen.getByTestId('no-credentials').textContent).toContain('run aws configure in a terminal once');
    expect(screen.getAllByTestId('command').map((c) => c.querySelector('code')?.textContent)).toContain('aws configure');
    expect((screen.getByTestId('profile') as HTMLSelectElement).options.length).toBe(1);
    unmount();
    render(<NewProject {...base} canCreate={false} check={async (p) => pass(p)} onCreate={async () => {}} aws={{ ...creds, configured: false, source: 'none' }} />);
    fireEvent.click(screen.getByTestId('where-bucket'));
    expect(screen.queryByTestId('profile')).toBeNull();
    expect(screen.getByTestId('no-credentials').textContent).toContain(NO_AWS);
  });

  it('a check that cannot run, and a create that fails, are lines in the dialog; Esc closes it', async () => {
    const onClose = vi.fn();
    render(<NewProject {...base} onClose={onClose} check={async () => { throw new Error('could not run querysolo bucket check'); }} onCreate={async () => { throw new Error('querysolo init failed: no'); }} />);
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: 'acme' } });
    fireEvent.click(screen.getByTestId('where-bucket'));
    fireEvent.change(screen.getByTestId('warehouse'), { target: { value: 's3://acme-lake/analytics' } });
    fireEvent.click(screen.getByTestId('check-bucket'));
    await waitFor(() => expect(screen.getByTestId('new-project-error').textContent).toContain('could not run'));
    fireEvent.click(screen.getByTestId('where-folder'));
    fireEvent.click(screen.getByTestId('create-project'));
    await waitFor(() => expect(screen.getByTestId('new-project-error').textContent).toContain('querysolo init failed'));
    expect((screen.getByTestId('create-project') as HTMLButtonElement).disabled).toBe(false); // try again
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(onClose).toHaveBeenCalled();
  });

  it('in a browser the folder cannot be made but the form and the check still work', () => {
    render(<NewProject {...base} canCreate={false} defaultParent={null} check={async (p) => pass(p)} onCreate={async () => {}} />);
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: 'acme' } });
    expect((screen.getByTestId('create-project') as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByTestId('choose-parent')).toBeNull();
    expect(screen.getByText(/In a browser the folder cannot be made/)).toBeTruthy();
  });
});
