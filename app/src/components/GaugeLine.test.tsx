// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 3 gate, the gauge line: the verdict's words and colour, the running count, the
// done line with the cap's footer, Red as a refusal with the button.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { GaugeLine } from './GaugeLine';

const green = { verdict: 'green' as const, words: 'Runs here', reason: 'scans 61.4 MB · fits in memory · ~0.3 s' };
const red = { verdict: 'red' as const, words: 'Needs more machine', reason: 'scans 40 GB · cap $5.00' };
const yellow = { verdict: 'yellow' as const, words: 'Runs here, slowly', reason: 'scans 6.1 GB · spills 2 GB · ~4 min' };

describe('GaugeLine', () => {
  it('is nothing until there is a verdict, then the words, the colour and the count', () => {
    const { container, rerender } = render(<GaugeLine state={{ kind: 'idle' }} onRunAnyway={() => {}} />);
    expect(container.textContent).toBe('');
    rerender(<GaugeLine state={{ kind: 'running', verdict: green, rows: 12_000 }} onRunAnyway={() => {}} />);
    const line = screen.getByTestId('gauge');
    expect(line.className).toContain('green');
    expect(line.textContent).toContain('Runs here');
    expect(line.textContent).toContain('61.4 MB');
    expect(line.textContent).toContain('12,000 rows so far');
  });

  it('Yellow runs, in its own colour, with the sentence', () => {
    render(<GaugeLine state={{ kind: 'running', verdict: yellow, rows: 10 }} onRunAnyway={() => {}} />);
    const line = screen.getByTestId('gauge');
    expect(line.className).toContain('yellow');
    expect(line.textContent).toContain('Runs here, slowly');
    expect(line.textContent).toContain('~4 min');
    expect(screen.queryByTestId('run-anyway')).toBeNull();
  });

  it('Not estimated is the fourth state: grey, the scan named, and the rows still come (T3)', () => {
    const none = { verdict: 'none' as const, words: 'Not estimated', reason: '1 scan outside the catalog: read_parquet' };
    render(<GaugeLine state={{ kind: 'done', verdict: none, rows: 50, seconds: 0.2, complete: true, capped: false }} onRunAnyway={() => {}} />);
    const line = screen.getByTestId('gauge');
    expect(line.className).toContain('none');
    expect(line.getAttribute('data-verdict')).toBe('none');
    expect(line.textContent).toContain('Not estimated');
    expect(line.textContent).toContain('read_parquet');
    expect(line.textContent).toContain('50 rows in');
    expect(screen.queryByTestId('run-anyway')).toBeNull();
  });

  it('says how many rows in how long, and names the CLI when the stream was capped', () => {
    render(<GaugeLine state={{ kind: 'done', verdict: green, rows: 100_000, seconds: 3.21, complete: false, capped: true }} onRunAnyway={() => {}} />);
    const text = screen.getByTestId('gauge').textContent ?? '';
    expect(text).toContain('100,000 rows in 3.21 s');
    expect(text).toContain('querysolo sql --format parquet');
  });

  it('Red is a refusal with the sentence and a button', () => {
    const onRunAnyway = vi.fn();
    render(<GaugeLine state={{ kind: 'refused', verdict: red }} onRunAnyway={onRunAnyway} />);
    const line = screen.getByTestId('gauge');
    expect(line.className).toContain('red');
    expect(line.textContent).toContain('Needs more machine');
    expect(line.textContent).toContain('cap $5.00');
    fireEvent.click(screen.getByTestId('run-anyway'));
    expect(onRunAnyway).toHaveBeenCalledTimes(1);
  });

  it('a stop and an error are lines too', () => {
    const { rerender } = render(<GaugeLine state={{ kind: 'stopped', verdict: green, rows: 4_000, seconds: 1.5 }} onRunAnyway={() => {}} />);
    expect(screen.getByTestId('gauge').textContent).toContain('stopped after 4,000 rows');
    rerender(<GaugeLine state={{ kind: 'error', message: 'sql_error: Binder Error: nope' }} onRunAnyway={() => {}} />);
    expect(screen.getByTestId('sql-error').textContent).toContain('Binder Error');
  });
});
