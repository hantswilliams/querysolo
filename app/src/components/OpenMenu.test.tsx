// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// "Open…" in the bar: the recent projects, the folder dialog, and — since the welcome
// screen is never seen once a project exists — New project… (decisions P1).

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { OpenMenu } from './OpenMenu';

afterEach(cleanup);

const recent = [{ path: '/home/h/acme', name: 'acme', opened: 1 }, { path: '/home/h/demo', name: 'demo', opened: 2 }];

describe('the Open menu', () => {
  it('lists the other recent projects, opens the dialog, and New project…', () => {
    const onOpen = vi.fn();
    const onPick = vi.fn();
    const onNew = vi.fn();
    render(<OpenMenu recent={recent} current="/home/h/demo" onOpen={onOpen} onPick={onPick} onNew={onNew} />);
    fireEvent.click(screen.getByTestId('open-menu'));
    expect(screen.queryByText('demo')).toBeNull(); // this window's own project is left out
    fireEvent.click(screen.getByText('acme'));
    expect(onOpen).toHaveBeenCalledWith('/home/h/acme');
    fireEvent.click(screen.getByTestId('open-menu'));
    fireEvent.click(screen.getByText('Other folder…'));
    expect(onPick).toHaveBeenCalledWith();
    fireEvent.click(screen.getByTestId('open-menu'));
    fireEvent.click(screen.getByTestId('open-new'));
    expect(onNew).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('menu')).toBeNull(); // the menu closed
  });
});
