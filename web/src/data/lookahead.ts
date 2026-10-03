// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
import { estimates } from './lookahead-estimates';

export type Question = keyof typeof estimates;
export type Storage = 'local' | 's3';
export const questions = [
  { id: 'summary', title: 'Sales by region', detail: 'Summarise two columns', action: 'Group & total',
    sql: 'SELECT region, SUM(amount)\nFROM orders\nGROUP BY region;',
    columns: ['region', 'amount'] },
  { id: 'join', title: 'Orders + customers', detail: 'Join two tables', action: 'Build a lookup & join',
    sql: 'SELECT o.order_id, o.amount, c.segment\nFROM orders o\nJOIN customers c ON o.customer_id = c.customer_id;',
    columns: ['order_id', 'customer_id', 'amount'] },
  { id: 'sort', title: 'Full order history', detail: 'Sort every order, all columns', action: 'Sort the full table',
    sql: 'SELECT *\nFROM orders\nORDER BY ordered_at;',
    columns: ['order_id', 'customer_id', 'region', 'amount', 'ordered_at', 'status', 'currency', 'channel', 'address', 'notes', 'payment_ref', 'metadata'] },
] as const;
export const columns = questions[2].columns;
export const words = { green: 'Runs here', yellow: 'Runs here, slowly', red: 'Needs more machine' };
const reasons = {
  summary: {
    local: 'Only region and amount are read. The small aggregation fits comfortably in memory.',
    s3: 'The aggregation needs little memory. Reading 1.2 GB over the connection drives the estimate.',
  },
  join: {
    local: 'The customer lookup needs about 3.1 GB of memory. It fits within the 12 GB query limit.',
    s3: 'The join fits in memory. Reading 3.2 GB from S3 is the main wait.',
  },
  sort: {
    local: 'Sorting every column needs more than the 12 GB query limit. Writing temporary data to disk adds work.',
    s3: 'Reading 24 GB from S3 exceeds the 10-minute threshold. The sort also needs temporary space on local disk.',
  },
};
export const formatBytes = (bytes: number) => bytes >= 1e9 ? `${(bytes / 1e9).toFixed(1)} GB` : `${Math.round(bytes / 1e6)} MB`;
export function stateFor(question: Question, storage: Storage) {
  const estimate = estimates[question][storage];
  const seconds = estimate.wall_local;
  return {
    ...estimate,
    verdict: estimate.verdict as keyof typeof words,
    bytes: formatBytes(estimate.bytes_scanned),
    memory: formatBytes(estimate.peak_memory),
    spill: formatBytes(estimate.spill_bytes),
    time: seconds < 60 ? `~${Math.max(1, Math.round(seconds))} sec` : `~${(seconds / 60).toFixed(1)} min`,
    remaining: formatBytes(26e9 - estimate.bytes_scanned),
    reason: reasons[question][storage],
    memoryPercent: Math.min(100, estimate.peak_memory / 12e9 * 100),
  };
}
