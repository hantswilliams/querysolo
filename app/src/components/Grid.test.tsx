// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The grid's columns are sized to what they hold (TASKS, 2026-09-16: an equal share of the
// width put a two-column result's number far from its header).

import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { Column, Row } from '../lib/arrow';
import { Grid, cell, columnWidths, template } from './Grid';

afterEach(cleanup);

const columns: Column[] = [{ name: 'customer', type: 'Utf8' }, { name: 'revenue', type: 'Decimal(18, 2)' }];
const rows: Row[] = [['c1', '1234.50'], ['a much longer customer name here', '2.00']];

describe('the grid', () => {
  it('shows binary as its size and first bytes, not as a JSON object of indices', () => {
    const wkb = new Uint8Array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 240, 63, 0, 0, 0, 0, 0, 0, 0, 64]);
    expect(cell(wkb, 'Binary')).toBe('21 bytes · 0101000000000000…');
    expect(cell(new Uint8Array([255]), 'Binary')).toBe('1 byte · ff');
    expect(cell(null, 'Binary')).toBe('∅');
    expect(cell({ a: 1 }, 'Struct')).toBe('{"a":1}');
  });

  it('sizes a column to the longest of its header and its cells, between a floor and a cap', () => {
    const [name, revenue] = columnWidths(columns, rows);
    expect(name).toBe(Math.ceil('a much longer customer name here'.length * 7.8) + 28);
    expect(revenue).toBe(96); // "1,234.50" and "revenue" are short: the floor
    // a date is ten characters; its column shows all ten (it was one pixel short once)
    expect(columnWidths([{ name: 'day', type: 'Date32' }], [['2026-01-04']])[0]).toBeGreaterThanOrEqual(Math.ceil(10 * 7.83) + 24 + 1);
    expect(columnWidths([{ name: 'x', type: 'Utf8' }], [['y'.repeat(500)]])[0]).toBe(480);
    expect(template([100, 96])).toBe('100px minmax(96px, 1fr)');
  });

  it('applies the widths to the head and every row, with the last column taking the rest', () => {
    render(<Grid columns={columns} rows={rows} />);
    const head = screen.getByTestId('grid').querySelector('.grid-head') as HTMLElement;
    expect(head.style.gridTemplateColumns).toBe(`${columnWidths(columns, rows)[0]}px minmax(96px, 1fr)`);
  });
});
