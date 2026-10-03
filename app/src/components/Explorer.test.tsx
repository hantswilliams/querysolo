// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Decisions U2: the explorer lists every table with its rows, where its data is and the
// freshness dot; a row opens the detail; an attached table has Refresh; the empty state
// points at the drop zone above it.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { TableInfo } from '../lib/api';
import { Explorer, freshnessClass } from './Explorer';

const HOUR = 3600 * 1000;
const now = Date.now();
const table = (over: Partial<TableInfo>): TableInfo => ({
  name: 't', rows: 0, bytes: 0, columns: [], location: '/w/main/t', snapshot_id: 1, freshness: null, ...over,
});

const tables: TableInfo[] = [
  table({ name: 'orders', rows: 1234, columns: [['id', 'long']], freshness: new Date(now - 2 * HOUR).toISOString() }),
  table({ name: 'events', rows: 3000, source: 's3://acme-exports/events/', freshness: new Date(now - 3 * 24 * HOUR).toISOString() }),
  table({ name: 'open_events', rows: 10, source: 's3://public-data/x/', public: true, freshness: new Date(now - 40 * 24 * HOUR).toISOString() }),
  table({ name: 'by_c', kind: 'view', view_sql: 'select 1', freshness: null }),
  table({ name: 'old', rows: 5, needs_relocate: true, freshness: new Date(now - HOUR).toISOString() }),
];

const props = { native: false, over: false, onPaths: () => {}, onChoose: () => {}, onRefresh: () => {}, onOpen: () => {} };

describe('Explorer', () => {
  it('the dot is today, this week, or older; nothing when never written', () => {
    expect(freshnessClass(new Date(now - HOUR).toISOString(), now)).toBe('today');
    expect(freshnessClass(new Date(now - 3 * 24 * HOUR).toISOString(), now)).toBe('week');
    expect(freshnessClass(new Date(now - 30 * 24 * HOUR).toISOString(), now)).toBe('old');
    expect(freshnessClass(null)).toBe('none');
    expect(freshnessClass('nonsense')).toBe('none');
  });

  it('lists the tables with rows, Where and the dot, and a row opens the detail', () => {
    const onOpen = vi.fn();
    const onRefresh = vi.fn();
    render(<Explorer {...props} tables={tables} onOpen={onOpen} onRefresh={onRefresh} open="events" />);
    expect(screen.getByTestId('tables').textContent).toContain('Tables · 5');
    expect(screen.getByTestId('table-events').querySelector('button.entry')!.getAttribute('aria-current')).toBe('true');
    expect(screen.getByTestId('table-orders').querySelector('button.entry')!.getAttribute('aria-current')).toBeNull();
    expect(screen.getByTestId('table-orders').textContent).toContain('1,234 rows');
    expect(screen.getByTestId('table-orders').textContent).toContain('local');
    expect(screen.getByTestId('fresh-orders').className).toContain('today');
    expect(screen.getByTestId('fresh-orders').getAttribute('title')).toBe('updated 2 h ago');
    expect(screen.getByTestId('where-events').textContent).toContain('attached');
    expect(screen.getByTestId('where-events').getAttribute('title')).toBe('s3://acme-exports/events/');
    expect(screen.getByTestId('fresh-events').className).toContain('week');
    expect(screen.getByTestId('where-open_events').textContent).toContain('public');
    expect(screen.getByTestId('fresh-open_events').className).toContain('old');
    expect(screen.getByTestId('where-by_c').textContent).toBe('view');
    expect(screen.getByTestId('table-by_c').textContent).toContain('—');
    expect(screen.getByTestId('fresh-by_c').className).toContain('none');
    expect(screen.getByTestId('moved-old').textContent).toBe('needs relocate');
    // Refresh is on the attached tables only, and does not open the detail
    expect(screen.queryByTestId('refresh-orders')).toBeNull();
    fireEvent.click(screen.getByTestId('refresh-events'));
    expect(onRefresh).toHaveBeenCalledWith('events');
    expect(onOpen).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('table-orders').querySelector('button.entry')!);
    expect(onOpen).toHaveBeenCalledWith('orders');
  });

  it('with no tables says so under the drop zone, and Import… is the dialog inside the app', () => {
    const onChoose = vi.fn();
    const { rerender } = render(<Explorer {...props} tables={[]} native={false} onChoose={onChoose} />);
    expect(screen.getByTestId('tables').textContent).toContain('No tables yet');
    expect(screen.getByTestId('drop-zone')).toBeTruthy();
    expect(screen.queryByTestId('choose-files')).toBeNull();
    rerender(<Explorer {...props} tables={[]} native onChoose={onChoose} />);
    expect(screen.getByTestId('choose-files').textContent).toBe('Import…');
    fireEvent.click(screen.getByTestId('choose-files'));
    expect(onChoose).toHaveBeenCalled();
  });
});
