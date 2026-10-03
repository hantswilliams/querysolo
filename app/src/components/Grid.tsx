// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The result grid (app brief A4): rows as they arrive, virtualised so a hundred thousand
// of them cost what a screenful does. Columns come from the first batch's schema.

import { useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Column, Row } from '../lib/arrow';

const ROW = 30;

/** A cell's text. Binary (a GeoParquet geometry's WKB, a blob) is its size and the first
 *  bytes in hex, not the byte-by-index object JSON would make of a Uint8Array. */
export const cell = (v: unknown, type: string): string => {
  if (v === null || v === undefined) return '∅';
  if (typeof v === 'string' && type.startsWith('Decimal') && /^-?\d+(\.\d+)?$/.test(v)) return decimalText(v);
  if (typeof v === 'number') return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 6 });
  if (v instanceof Uint8Array) {
    const head = Array.from(v.subarray(0, 8), (b) => b.toString(16).padStart(2, '0')).join('');
    return `${v.length.toLocaleString()} ${v.length === 1 ? 'byte' : 'bytes'} · ${head}${v.length > 8 ? '…' : ''}`;
  }
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
};

const numeric = (type: string) => /^(Int|Uint|Float|Decimal)/.test(type);

/** Columns sized to what they hold, like a spreadsheet, rather than an equal share of the
 *  width: the longest of the header and the first rows' cells, in characters of the mono
 *  face, between a floor and a cap, so a two-column result keeps its number beside its
 *  header instead of at the far right. The last column takes what is left. */
export const SAMPLE = 200;
const CHAR = 7.8; // 13px monospace
const PAD = 28; // 12px padding each side, the 1px border, and a little slack: a ten-character date was one pixel short and showed an ellipsis
export function columnWidths(columns: Column[], rows: Row[]): number[] {
  return columns.map((c, i) => {
    let longest = c.name.length;
    for (const row of rows.slice(0, SAMPLE)) longest = Math.max(longest, cell(row[i], c.type).length);
    return Math.min(480, Math.max(96, Math.ceil(longest * CHAR) + PAD));
  });
}
export const template = (widths: number[]): string => widths.map((w, i) => (i === widths.length - 1 ? `minmax(${w}px, 1fr)` : `${w}px`)).join(' ');
const decimalText = (v: string) => { const [i, f] = v.split('.'); const sign = i.startsWith('-') ? '-' : ''; const whole = Number(sign ? i.slice(1) : i).toLocaleString(); return f === undefined ? `${sign}${whole}` : `${sign}${whole}.${f}`; };

export function Grid({ columns, rows }: { columns: Column[]; rows: Row[] }) {
  const scroller = useRef<HTMLDivElement>(null);
  const virtual = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scroller.current,
    estimateSize: () => ROW,
    overscan: 12,
  });
  if (columns.length === 0) return null;
  const items = virtual.getVirtualItems();
  const widths = template(columnWidths(columns, rows));
  return (
    <div className="grid" ref={scroller} data-testid="grid" data-rows={rows.length}>
      <div className="grid-head" style={{ gridTemplateColumns: widths }}>
        {columns.map((c) => (
          <div key={c.name} className={numeric(c.type) ? 'num' : ''} title={c.type}>{c.name}</div>
        ))}
      </div>
      <div className="grid-body" style={{ height: virtual.getTotalSize() }}>
        {items.map((item) => {
          const row = rows[item.index];
          return (
            <div
              key={item.key}
              className="grid-row"
              data-index={item.index}
              style={{ transform: `translateY(${item.start}px)`, gridTemplateColumns: widths }}
            >
              {row.map((v, i) => (
                <div key={i} className={numeric(columns[i].type) ? 'num' : ''}>{cell(v, columns[i].type)}</div>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}
