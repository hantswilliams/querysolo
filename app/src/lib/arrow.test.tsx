// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Cells as the grid shows them: Arrow JS hands dates over as milliseconds, times as
// microseconds and decimals as four words; the grid shows dates, times and numbers.

import { Date_, DateUnit, Decimal, Int64, Time, TimeUnit, Timestamp, Utf8 } from 'apache-arrow';
import { describe, expect, it } from 'vitest';
import { cellConverter, decimalText } from './arrow';

describe('cellConverter', () => {
  it('dates and timestamps become ISO text', () => {
    expect(cellConverter(new Date_(DateUnit.DAY))(Date.UTC(2026, 0, 3))).toBe('2026-01-03');
    expect(cellConverter(new Timestamp(TimeUnit.MICROSECOND, null))(Date.UTC(2026, 0, 3, 10, 11, 12))).toBe('2026-01-03T10:11:12');
    expect(cellConverter(new Timestamp(TimeUnit.MILLISECOND, null))(Date.UTC(2026, 0, 3, 10, 11, 12, 250))).toBe('2026-01-03T10:11:12.250');
    expect(cellConverter(new Timestamp(TimeUnit.MICROSECOND, 'UTC'))(Date.UTC(2026, 0, 3, 10, 11, 12))).toBe('2026-01-03T10:11:12Z');
    expect(cellConverter(new Date_(DateUnit.DAY))(null)).toBeNull();
  });

  it('times become HH:MM:SS with the fraction only when there is one', () => {
    expect(cellConverter(new Time(TimeUnit.MICROSECOND, 64))(36_672_000_000n)).toBe('10:11:12');
    expect(cellConverter(new Time(TimeUnit.MICROSECOND, 64))(36_672_500_000n)).toBe('10:11:12.5');
    expect(cellConverter(new Time(TimeUnit.SECOND, 32))(61)).toBe('00:01:01');
  });

  it('decimals become their digits with the scale applied, sign included', () => {
    expect(decimalText([150, 0, 0, 0], 2)).toBe('1.50');
    expect(decimalText([2394798901, 3175723401, 4294966626, 4294967295], 3)).toBe('-12345678901234567890.123');
    expect(decimalText([5, 0, 0, 0], 0)).toBe('5');
    expect(decimalText([5, 0, 0, 0], 4)).toBe('0.0005');
    expect(cellConverter(new Decimal(2, 10, 128))(new Uint32Array([150, 0, 0, 0]))).toBe('1.50');
  });

  it('everything else is left to plain: BigInt within range is a number, strings stay', () => {
    expect(cellConverter(new Int64())(12345678901234567n)).toBe('12345678901234567');
    expect(cellConverter(new Int64())(42n)).toBe(42);
    expect(cellConverter(new Utf8())('x')).toBe('x');
  });
});
