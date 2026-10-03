// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Versions step 2 (G7): the save box. The title is the only thing asked, the slug is derived
// the way the CLI derives it, a title already saved comes back as a 409 and becomes "Replace
// it", and the notice says the two checks and the version.

import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { Api } from '../lib/api';
import { SaveQuestion, checksSentence } from './SaveQuestion';

const session = { port: 1234, token: 't', pid: 1, ready_ms: 1 };
const SQL = 'select customer, sum(amt) as revenue from orders group by 1';

const saved = {
  slug: 'revenue_by_customer',
  title: 'Revenue by customer',
  sql: SQL,
  path: '/p/models/questions/revenue_by_customer.sql',
  created: '2026-09-12T10:00:00+00:00',
  last_run: null,
  commit: '6c89b4f1234567890abcdef1234567890abcdef1',
  git: null,
};

function api() {
  return new Api(session as never);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

function answer(status: number, body: unknown) {
  return Promise.resolve({
    ok: status < 400,
    status,
    headers: new Headers({ 'Content-Type': 'application/json' }),
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  } as Response);
}

describe('the checks sentence', () => {
  it('names the first column when there is one', () => {
    expect(checksSentence('customer')).toBe('returns at least one row; `customer` is never empty');
    expect(checksSentence(undefined)).toContain('its first column is never empty');
  });
});

describe('the save box', () => {
  it('asks only for a title, shows the slug and the checks, and posts', async () => {
    const fetchMock = vi.fn().mockReturnValue(answer(200, saved));
    vi.stubGlobal('fetch', fetchMock);
    render(<SaveQuestion api={api()} sql={SQL} mode="technical" firstColumn="customer" />);

    fireEvent.click(screen.getByTestId('save-question'));
    fireEvent.change(screen.getByTestId('question-title'), { target: { value: 'Revenue by customer' } });

    expect(screen.getByTestId('save-question-box').textContent).toContain('models/questions/revenue_by_customer.sql');
    expect(screen.getByTestId('save-question-box').textContent).toContain('`customer` is never empty');
    expect(screen.getByTestId('save-question-box').textContent).toContain("querysolo question save 'Revenue by customer'");

    fireEvent.click(screen.getByTestId('question-save'));
    await waitFor(() => expect(screen.getByTestId('saved-question')).toBeTruthy());

    const [, init] = fetchMock.mock.calls[0];
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({
      title: 'Revenue by customer',
      sql: SQL,
      replace: false,
    });
    expect(screen.getByTestId('saved-version').textContent).toContain('6c89b4f');
    expect(screen.getByTestId('saved-question').textContent).toContain('revenue_by_customer.sql');
  });

  it('offers Replace it when the core says the title is taken, and posts replace', async () => {
    const fetchMock = vi
      .fn()
      .mockReturnValueOnce(answer(409, { error: 'question_exists', message: 'already saved', slug: 'revenue_by_customer' }))
      .mockReturnValueOnce(answer(200, saved));
    vi.stubGlobal('fetch', fetchMock);
    render(<SaveQuestion api={api()} sql={SQL} mode="technical" firstColumn="customer" />);

    fireEvent.click(screen.getByTestId('save-question'));
    fireEvent.change(screen.getByTestId('question-title'), { target: { value: 'Revenue by customer' } });
    fireEvent.click(screen.getByTestId('question-save'));

    await waitFor(() => expect(screen.getByTestId('question-exists')).toBeTruthy());
    expect(screen.queryByTestId('question-save')).toBeNull();

    fireEvent.click(screen.getByTestId('question-replace'));
    await waitFor(() => expect(screen.getByTestId('saved-question')).toBeTruthy());
    expect(JSON.parse((fetchMock.mock.calls[1][1] as RequestInit).body as string).replace).toBe(true);
  });

  it('says a Red statement can still be saved', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(answer(200, saved)));
    render(<SaveQuestion api={api()} sql={SQL} mode="technical" red />);
    fireEvent.click(screen.getByTestId('save-question'));
    expect(screen.getByTestId('save-question-red').textContent).toContain('bigger than this laptop');
  });

  it('says question and check in Simple mode', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(answer(200, saved)));
    render(<SaveQuestion api={api()} sql={SQL} mode="simple" firstColumn="customer" />);
    expect(screen.getByTestId('save-question').textContent).toBe('Save this question');
    fireEvent.click(screen.getByTestId('save-question'));
    fireEvent.change(screen.getByTestId('question-title'), { target: { value: 'Revenue by customer' } });
    expect(screen.getByTestId('save-question-box').textContent).toContain('checks');
  });

  it('shows the git reason when the save wrote the files but recorded no version', async () => {
    vi.stubGlobal('fetch', vi.fn().mockReturnValue(answer(200, { ...saved, commit: null, git: 'PermissionError: .git' })));
    render(<SaveQuestion api={api()} sql={SQL} mode="technical" firstColumn="customer" />);
    fireEvent.click(screen.getByTestId('save-question'));
    fireEvent.change(screen.getByTestId('question-title'), { target: { value: 'Revenue by customer' } });
    fireEvent.click(screen.getByTestId('question-save'));
    await waitFor(() => expect(screen.getByTestId('saved-git')).toBeTruthy());
    expect(screen.queryByTestId('saved-version')).toBeNull();
  });
});
