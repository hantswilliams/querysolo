// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The query path (app brief §3.3): POST /api/query, the verdict from the headers before any
// row, then Arrow record batches as the core produces them, each handed to the caller as it
// lands. Esc aborts the fetch, which closes the response and the core's result.

import { DataType, RecordBatchReader, type RecordBatch } from 'apache-arrow';
import { ApiError, type Api } from './api';

/** The three colours, and 'none' for a scan the gauge could not attribute (trust round T3). */
export type Verdict = 'green' | 'yellow' | 'red' | 'none';

export interface VerdictLine {
  verdict: Verdict;
  words: string;
  reason: string;
}

/** The estimate as `/api/estimate` and a 409 `red_refused` carry it. */
export interface Estimate extends VerdictLine {
  line: string;
  bytes_scanned: number;
  peak_memory: number;
  wall_local: number;
  wall_burst: number;
  cost_burst: number;
  cap: number;
  memory_limit?: number;
}

export class RedRefused extends Error {
  constructor(public readonly estimate: Estimate) {
    super(estimate.reason);
  }
}

export interface Column {
  name: string;
  type: string;
}

export type Row = unknown[];

export interface QueryEvents {
  /** The headers arrived: the verdict, before any row. */
  onVerdict: (v: VerdictLine) => void;
  /** The first batch names the columns. */
  onSchema: (columns: Column[]) => void;
  /** Rows of one batch, as it arrived. Return false to stop reading (the cap, A4). */
  onRows: (rows: Row[]) => boolean | void;
}

/** A cell as the grid shows it: BigInt and Arrow's wrappers become plain values. */
export function plain(v: unknown): unknown {
  if (v === null || v === undefined) return null;
  if (typeof v === 'bigint') return Number.isSafeInteger(Number(v)) ? Number(v) : v.toString();
  if (v instanceof Date) return v.toISOString();
  if (typeof v === 'object' && v !== null && 'toJSON' in v && typeof (v as { toJSON: unknown }).toJSON === 'function') {
    return (v as { toJSON: () => unknown }).toJSON();
  }
  return v;
}

const pad = (n: number, w = 2) => String(n).padStart(w, '0');

/** A 128-bit two's-complement decimal, as Arrow JS hands it over (four little-endian
 *  32-bit words), as the number it is, with its scale applied. */
export function decimalText(words: ArrayLike<number>, scale: number): string {
  let n = 0n;
  for (let i = 3; i >= 0; i--) n = (n << 32n) | BigInt(words[i] >>> 0);
  if (n >= 1n << 127n) n -= 1n << 128n;
  const negative = n < 0n;
  let digits = (negative ? -n : n).toString();
  if (scale > 0) {
    digits = digits.padStart(scale + 1, '0');
    digits = `${digits.slice(0, -scale)}.${digits.slice(-scale)}`;
  }
  return (negative ? '-' : '') + digits;
}

/** How one column's cells become plain values: dates as `YYYY-MM-DD`, timestamps as ISO
 *  text (with the zone when they have one), times as `HH:MM:SS`, decimals as their digits;
 *  Arrow JS returns those as milliseconds, microseconds and words otherwise. */
export function cellConverter(type: DataType): (v: unknown) => unknown {
  if (DataType.isDate(type)) {
    return (v) => (v == null ? null : new Date(Number(v)).toISOString().slice(0, 10));
  }
  if (DataType.isTimestamp(type)) {
    const zoned = Boolean((type as { timezone?: string | null }).timezone);
    return (v) => {
      if (v == null) return null;
      const iso = new Date(Number(v)).toISOString();
      const text = iso.endsWith('.000Z') ? iso.slice(0, 19) : iso.slice(0, 23);
      return zoned ? `${text}Z` : text;
    };
  }
  if (DataType.isTime(type)) {
    const unit = (type as { unit: number }).unit; // 0 s, 1 ms, 2 µs, 3 ns
    const perSecond = [1n, 1_000n, 1_000_000n, 1_000_000_000n][unit] ?? 1_000_000n;
    return (v) => {
      if (v == null) return null;
      const n = BigInt(v as bigint | number);
      const seconds = n / perSecond;
      const fraction = n % perSecond;
      const base = `${pad(Number(seconds / 3600n))}:${pad(Number((seconds / 60n) % 60n))}:${pad(Number(seconds % 60n))}`;
      return fraction === 0n ? base : `${base}.${fraction.toString().padStart(Number(perSecond.toString().length - 1), '0').replace(/0+$/, '')}`;
    };
  }
  if (DataType.isDecimal(type)) {
    const scale = (type as { scale: number }).scale;
    return (v) => (v == null ? null : decimalText(v as ArrayLike<number>, scale));
  }
  return plain;
}

function rowsOf(batch: RecordBatch): Row[] {
  const n = batch.numRows;
  const columns = batch.schema.fields.map((_, i) => batch.getChildAt(i)!);
  const convert = batch.schema.fields.map((f) => cellConverter(f.type));
  const rows: Row[] = new Array(n);
  for (let r = 0; r < n; r++) {
    const row: Row = new Array(columns.length);
    for (let c = 0; c < columns.length; c++) row[c] = convert[c](columns[c].get(r));
    rows[r] = row;
  }
  return rows;
}

const header = (r: Response, name: string) => r.headers.get(name) ?? '';

/**
 * Run SQL and stream its rows. Resolves when the stream ends or the caller stopped it;
 * rejects with RedRefused (409), ApiError (any other core error) or the abort's DOMException.
 */
export async function runQuery(api: Api, sql: string, allowRed: boolean, signal: AbortSignal, events: QueryEvents): Promise<{ rows: number; complete: boolean }> {
  const r = await fetch(`${api.base}/query`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${api.token}`, 'Content-Type': 'application/json', Accept: 'application/vnd.apache.arrow.stream' },
    body: JSON.stringify({ sql, allow_red: allowRed, batch_rows: 1000 }),
    signal,
  });
  if (!r.ok) {
    const body = (await r.json().catch(() => ({}))) as { error?: string; message?: string; estimate?: Estimate };
    if (r.status === 409 && body.error === 'red_refused' && body.estimate) throw new RedRefused(body.estimate);
    throw new ApiError(r.status, body.error ?? 'http', body.message ?? `${r.status}`);
  }
  events.onVerdict({
    verdict: (header(r, 'X-QuerySolo-Verdict') || 'green') as Verdict,
    words: header(r, 'X-QuerySolo-Words'),
    reason: header(r, 'X-QuerySolo-Reason'),
  });
  if (!r.body) throw new Error('no response body');
  const reader = await RecordBatchReader.from(r.body);
  let rows = 0;
  let named = false;
  try {
    for await (const batch of reader) {
      if (!named) {
        events.onSchema(batch.schema.fields.map((f) => ({ name: f.name, type: String(f.type) })));
        named = true;
      }
      rows += batch.numRows;
      if (events.onRows(rowsOf(batch)) === false) {
        await reader.cancel();
        return { rows, complete: false };
      }
    }
    if (!named) events.onSchema(reader.schema?.fields.map((f) => ({ name: f.name, type: String(f.type) })) ?? []);
  } finally {
    // an abort closes the body; nothing else to release
  }
  return { rows, complete: true };
}

/** `querysolo estimate`: the gauge without running. */
export async function estimate(api: Api, sql: string): Promise<Estimate> {
  return api.post<Estimate>('/estimate', { sql });
}
