// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Step 2 gate, the preview: the columns with their notes, the name that shapes the command,
// and the replace-or-append choice when the table exists.

import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PreviewPanel } from './PreviewPanel';

const preview = {
  name: 'orders',
  source: '/data/orders.csv',
  columns: [
    { name: 'id', duckdb_type: 'BIGINT', iceberg_type: 'long', note: '' },
    { name: 'big', duckdb_type: 'HUGEINT', iceberg_type: 'decimal(38, 0)', note: '128-bit integer becomes decimal(38, 0)' },
  ],
  sample: [[1, 5], [2, null]],
};

describe('PreviewPanel', () => {
  it('shows the columns, the notes and the command for the name given', () => {
    const onImport = vi.fn();
    render(<PreviewPanel path="/data/orders.csv" folder={false} previews={[preview]} name="sales" mode="create" onName={() => {}} onImport={onImport} onCancel={() => {}} />);
    expect(screen.getByText('decimal(38, 0)')).toBeTruthy();
    expect(screen.getByText('128-bit integer becomes decimal(38, 0)')).toBeTruthy();
    expect(screen.getByText('∅')).toBeTruthy();
    expect(screen.getByTestId('command').textContent).toContain('querysolo import /data/orders.csv --name sales');
    fireEvent.click(screen.getByTestId('import'));
    expect(onImport).toHaveBeenCalledWith('create');
  });

  it('offers replace or append when the table exists, and the line follows', () => {
    const onImport = vi.fn();
    const { rerender } = render(<PreviewPanel path="/data/orders.csv" folder={false} previews={[preview]} name="orders" mode="create" exists="orders" onName={() => {}} onImport={onImport} onCancel={() => {}} />);
    expect(screen.queryByTestId('import')).toBeNull();
    fireEvent.click(screen.getByTestId('append'));
    expect(onImport).toHaveBeenCalledWith('append');
    rerender(<PreviewPanel path="/data/orders.csv" folder={false} previews={[preview]} name="orders" mode="append" exists="orders" onName={() => {}} onImport={onImport} onCancel={() => {}} />);
    expect(screen.getByTestId('command').textContent).toContain('querysolo import /data/orders.csv --append');
  });

  it('a folder lists its files and the button counts the tables', () => {
    const b = { ...preview, name: 'customers', source: '/data/in/customers.parquet' };
    render(<PreviewPanel path="/data/in" folder previews={[b, preview]} name="" mode="create" onName={() => {}} onImport={() => {}} onCancel={() => {}} />);
    expect(screen.getByTestId('import').textContent).toBe('Import 2 tables');
    expect(screen.getByText('customers.parquet')).toBeTruthy();
    expect(screen.getByTestId('command').textContent).toContain('querysolo import /data/in');
  });
});

describe('PreviewPanel for a remote prefix (real-data R4)', () => {
  const remote = {
    name: 'place',
    source: 's3://overturemaps-us-west-2/release/2026-08-19.0/theme=places/type=place/',
    columns: [
      { name: 'id', duckdb_type: 'string', iceberg_type: 'string', note: '' },
      { name: 'bbox', duckdb_type: 'struct<xmin: float, ...>', iceberg_type: 'struct<...>', note: '' },
    ],
    sample: [],
    remote: true,
    files: 16,
    bytes: 10_500_000_000,
    anonymous: true,
  };

  it('shows the files and bytes, Attach, and the tables attach line with --anonymous', () => {
    const onAttach = vi.fn();
    render(<PreviewPanel path={remote.source} folder={false} previews={[remote]} name="places" mode="create" onName={() => {}} onImport={() => {}} onAttach={onAttach} onCancel={() => {}} />);
    expect(screen.getByTestId('remote-summary').textContent).toContain('16 Parquet files, 10.5 GB, read in place without credentials');
    expect(screen.getByText('Arrow')).toBeTruthy();
    expect(screen.getByTestId('command').textContent).toContain(`querysolo tables attach places --anonymous ${remote.source}`);
    expect(screen.getByTestId('attach').textContent).toBe('Attach as places');
    fireEvent.click(screen.getByTestId('attach'));
    expect(onAttach).toHaveBeenCalled();
    expect(screen.queryByTestId('import')).toBeNull();
  });
});
