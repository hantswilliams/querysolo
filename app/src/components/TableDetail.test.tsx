// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Real-data brief R7: the detail's reclaimable line, the snapshot marks, and the buttons
// that are `tables sample`, `tables expire` and `tables refresh`.

import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { TableDescription } from '../lib/api';
import { TableDetail } from './TableDetail';

const local: TableDescription = {
  name: 'orders',
  rows: 200,
  bytes: 12_000,
  columns: [['id', 'long'], ['customer', 'string'], ['amt', 'decimal(21, 1)']],
  location: 'file:///p/warehouse/main/orders',
  snapshot_id: 2,
  freshness: new Date().toISOString(),
  source: null,
  public: false,
  partitioning: 'unpartitioned',
  expirable_snapshots: 2,
  reclaimable_bytes: 4_000,
  keep_days: 7,
  last_commit: { snapshot_id: 2, operation: 'append', timestamp: new Date().toISOString() },
  snapshots: 3,
  format_version: 2,
  snapshot_list: [
    { id: 3, timestamp: new Date().toISOString(), operation: 'append', added_rows: 200, added_bytes: null, added_files: 1, deleted_rows: null, total_rows: 200, current: true, expirable: false },
    { id: 2, timestamp: new Date(Date.now() - 864e5 * 9).toISOString(), operation: 'delete', added_rows: null, added_bytes: null, added_files: null, deleted_rows: 100, total_rows: 0, current: false, expirable: true },
    { id: 1, timestamp: new Date(Date.now() - 864e5 * 10).toISOString(), operation: 'append', added_rows: 100, added_bytes: null, added_files: 1, deleted_rows: null, total_rows: 100, current: false, expirable: true },
  ],
};

const noop = () => {};

describe('TableDetail', () => {
  it('shows the reclaimable line, marks the snapshots, and expire is the verb', () => {
    const onExpire = vi.fn();
    render(<TableDetail table={local} onSample={noop} onExpire={onExpire} onRefresh={noop} onClose={noop} />);
    expect(screen.getByTestId('reclaimable').textContent).toBe('2 snapshots older than 7 days, 4 KB reclaimable.');
    expect(screen.getByTestId('snapshot-3').textContent).toContain('current');
    expect(screen.getByTestId('snapshot-1').textContent).toContain('expirable');
    expect(screen.getByTestId('snapshot-2').textContent).toContain('delete');
    expect(screen.getAllByTestId('command').map((c) => c.textContent)).toEqual(expect.arrayContaining([
      expect.stringContaining('querysolo tables describe orders'),
      expect.stringContaining('querysolo tables expire orders'),
    ]));
    fireEvent.click(screen.getByTestId('expire'));
    expect(onExpire).toHaveBeenCalled();
    expect(screen.queryByTestId('refresh')).toBeNull();
  });

  it('an attached table offers refresh instead, and says it is never expired', () => {
    const onRefresh = vi.fn();
    const attached = { ...local, name: 'place', source: 's3://b/release/type=place/', public: true, expirable_snapshots: 0, reclaimable_bytes: 0 };
    render(<TableDetail table={attached} onSample={noop} onExpire={noop} onRefresh={onRefresh} onClose={noop} />);
    expect(screen.getByTestId('detail-where').textContent).toContain('public bucket, read without credentials');
    expect(screen.getByTestId('reclaimable').textContent).toContain('never expired');
    expect(screen.queryByTestId('expire')).toBeNull();
    fireEvent.click(screen.getByTestId('refresh'));
    expect(onRefresh).toHaveBeenCalled();
    expect(screen.getAllByTestId('command').some((c) => c.textContent?.includes('querysolo tables refresh place'))).toBe(true);
  });

  it('says when the attached files were verified, and a changed file turns Refresh into Register again (T2)', () => {
    const onReattach = vi.fn();
    const verified = { ...local, name: 'place', source: 's3://b/release/type=place/', public: true, verified_at: new Date(Date.now() - 240_000).toISOString(), changed_files: [] as [string, string][] };
    const { unmount } = render(<TableDetail table={verified} onSample={noop} onExpire={noop} onRefresh={noop} onReattach={onReattach} onClose={noop} />);
    expect(screen.getByTestId('files-verified').textContent).toBe('Files verified against the prefix 4 min ago.');
    expect(screen.getByTestId('refresh')).toBeTruthy();
    expect(screen.queryByTestId('reattach')).toBeNull();
    unmount();
    const changed = { ...verified, changed_files: [['s3://b/release/type=place/part-1.parquet', 'size 1.2 MB → 3.4 MB']] as [string, string][] };
    render(<TableDetail table={changed} onSample={noop} onExpire={noop} onRefresh={noop} onReattach={onReattach} onClose={noop} />);
    expect(screen.getByTestId('files-verified').textContent).toContain('1 file changed under the same path since the attach: part-1.parquet (size 1.2 MB → 3.4 MB)');
    expect(screen.queryByTestId('refresh')).toBeNull();
    fireEvent.click(screen.getByTestId('reattach'));
    expect(onReattach).toHaveBeenCalled();
    expect(screen.getAllByTestId('command').some((c) => c.textContent?.includes('querysolo tables attach place --anonymous --replace s3://b/release/type=place/'))).toBe(true);
  });

  it('renders the sample when it has been read, with its line', () => {
    render(<TableDetail table={local} sample={[{ id: 1, customer: 'c1', amt: null }]} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} />);
    expect(screen.getByTestId('sample').textContent).toContain('c1');
    expect(screen.getByTestId('sample').textContent).toContain('∅');
    expect(screen.getByTestId('sample').textContent).toContain('querysolo tables sample orders');
  });

  it('a view has its own shape: the query, its version, the model it came from, no snapshots, no expire', () => {
    const view: TableDescription = {
      ...local,
      name: 'big_orders',
      rows: 0,
      bytes: 0,
      kind: 'view',
      view_sql: 'select * from "main"."orders" where amount > 100',
      partitioning: 'a view',
      snapshots: 2,
      format_version: 1,
      snapshot_list: [],
      expirable_snapshots: 0,
      reclaimable_bytes: 0,
      last_commit: { operation: 'view version 2', timestamp: new Date().toISOString() },
      properties: { 'querysolo.dbt-model': 'model.demo.big_orders' },
    };
    render(<TableDetail table={view} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} />);
    const detail = screen.getByTestId('detail');
    expect(detail.dataset.kind).toBe('view');
    expect(screen.getByTestId('view-sql').textContent).toBe('select * from "main"."orders" where amount > 100');
    expect(screen.getByTestId('view-version').textContent).toBe('2 versions · this one just now');
    expect(screen.getByTestId('view-model').textContent).toContain('model.demo.big_orders');
    expect(screen.getByTestId('view-model').textContent).toContain('querysolo run big_orders');
    expect(screen.queryByTestId('snapshots')).toBeNull();
    expect(screen.queryByTestId('expire')).toBeNull();
    expect(screen.queryByTestId('refresh')).toBeNull();
    expect(screen.queryByTestId('reclaimable')).toBeNull();
    expect(screen.getByTestId('no-snapshots').textContent).toContain('nothing to expire');
    expect(detail.textContent).not.toContain('0 rows');
    expect(screen.getAllByTestId('command').map((c) => c.textContent)).toEqual(expect.arrayContaining([
      expect.stringContaining('querysolo tables describe big_orders'),
      expect.stringContaining('querysolo run big_orders'),
    ]));
    // Simple mode says question and Refresh
    cleanup();
    render(<TableDetail table={view} mode="simple" onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} />);
    expect(screen.getByTestId('detail').textContent).toContain('a question, answered live');
    expect(screen.getByTestId('view-model').textContent).toContain('the question big_orders');
    // a view put in the catalog directly names no model and offers no run line
    cleanup();
    render(<TableDetail table={{ ...view, properties: {} }} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} />);
    expect(screen.getByTestId('view-model').textContent).toContain('not a dbt model');
    expect(screen.getAllByTestId('command').some((c) => c.textContent?.includes('querysolo run'))).toBe(false);
  });

  it('a snapshot names the models it made out of date, as links, with Run what changed (L3)', () => {
    const onOpen = vi.fn();
    const onRunStale = vi.fn();
    const table = {
      ...local,
      snapshot_list: [
        { ...local.snapshot_list[0], affects: ['stg', 'by_customer'] },
        { ...local.snapshot_list[1], affects: [] },
      ],
    };
    render(<TableDetail table={table} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} onOpen={onOpen} onRunStale={onRunStale} />);
    expect(screen.getByTestId('snapshot-3').textContent).toContain('made out of date: stg, by_customer');
    expect(screen.getByTestId('snapshot-2').textContent).not.toContain('out of date');
    fireEvent.click(screen.getByTestId('affects-by_customer'));
    expect(onOpen).toHaveBeenCalledWith('by_customer', 'model');
    expect(screen.getByTestId('affected').textContent).toContain('2 models are out of date because of these commits.');
    expect(screen.getByTestId('affected').textContent).toContain('querysolo run --stale');
    fireEvent.click(screen.getByTestId('run-stale'));
    expect(onRunStale).toHaveBeenCalled();
    cleanup();
    // Simple mode's words, and no line without a handler
    render(<TableDetail table={table} mode="simple" onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} />);
    expect(screen.getByTestId('snapshot-3').textContent).toContain('2 questions need refreshing because of this: stg, by_customer');
    expect(screen.queryByTestId('affected')).toBeNull();
  });

  it('publishes a local table into a bucket: weigh first, the cap offers Publish anyway (W2)', async () => {
    const report = { name: 'orders', source: 'file:///p/warehouse/main/orders', target: 's3://b/lake/main/orders', files: 4, bytes: 12_000, copied: 0, skipped: 0, metadata_files: 3, data_files: 1, seconds: 2.4, dry_run: true };
    const onPublish = vi.fn(async (_prefix: string, dryRun: boolean, yes: boolean) => {
      if (dryRun) return report;
      if (!yes) throw new Error('orders: 12 KB is about 2 s at the measured bandwidth, over the cap of 1 s; --yes moves it anyway');
      return { ...report, copied: 4, dry_run: false };
    });
    render(<TableDetail table={local} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} onPublish={onPublish} />);
    expect(screen.queryByTestId('publish-box')).toBeNull();
    fireEvent.click(screen.getByTestId('publish-open'));
    const go = screen.getByTestId('publish-go') as HTMLButtonElement;
    expect(go.disabled).toBe(true);
    fireEvent.change(screen.getByTestId('publish-prefix'), { target: { value: 's3://b/lake' } });
    expect(go.disabled).toBe(false);
    expect(screen.getAllByTestId('command').some((c) => c.textContent?.includes('querysolo tables publish orders s3://b/lake --dry-run'))).toBe(true);
    fireEvent.click(screen.getByTestId('publish-weigh'));
    expect(onPublish).toHaveBeenCalledWith('s3://b/lake', true, false);
    expect((await screen.findByTestId('publish-weighed')).textContent).toBe('4 files, 12 KB to copy to s3://b/lake/main/orders, about 2 s at the measured bandwidth.');
    expect(screen.getAllByTestId('command').some((c) => c.textContent?.includes('querysolo tables publish orders s3://b/lake') && !c.textContent.includes('--dry-run'))).toBe(true);
    fireEvent.click(go);
    expect((await screen.findByTestId('publish-error')).textContent).toContain('over the cap');
    fireEvent.click(screen.getByTestId('publish-anyway'));
    expect(onPublish).toHaveBeenLastCalledWith('s3://b/lake', false, true);
    await vi.waitFor(() => expect(screen.queryByTestId('publish-box')).toBeNull());
    cleanup();
    // a table already in a bucket, or an attached one, has no box; a published one names its local copy
    render(<TableDetail table={{ ...local, location: 's3://b/lake/main/orders', local_copy_files: 4 }} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} onPublish={onPublish} />);
    expect(screen.queryByTestId('publish-open')).toBeNull();
    expect(screen.getByTestId('detail-where').textContent).toContain('in a bucket');
    expect(screen.getByTestId('local-copy').textContent).toBe("4 files of the local copy still under the project's warehouse, until expire sweeps them.");
    cleanup();
    render(<TableDetail table={{ ...local, source: 's3://b/release/type=place/' }} onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} onPublish={onPublish} />);
    expect(screen.queryByTestId('publish-open')).toBeNull();
    cleanup();
    render(<TableDetail table={local} mode="simple" onSample={noop} onExpire={noop} onRefresh={noop} onClose={noop} onPublish={onPublish} />);
    expect(screen.getByTestId('publish-open').textContent).toBe('Move to a bucket…');
  });
});
