import type { Format } from './types';

/**
 * The CONTRACT §5 format codes, implemented once so a chart's axis ticks, its
 * marks' tooltips, its "Show data" table, and a table figure agree to the digit.
 *
 * Facts are NOT formatted here: a fact's `display` string is formatted in
 * Python and printed verbatim. This module formats raw numbers inside figures.
 *
 *   pct0 pct1 pct2   value is a proportion (0.323 -> "32.3%")
 *   num0 … num3      fixed decimals with thousands separators
 *   int              rounded, thousands separators ("8,548")
 *   usd0             "$74,580"
 *   min0 min1        minutes: "213.8 min" (ticks print the number only)
 *   ratio2           "1.64×"
 *
 * Negative numbers use U+2212 MINUS SIGN, which sits at the height and width
 * of a figure; a hyphen looks homemade at tabular widths.
 */

export const FORMAT_CODES: readonly Format[] = [
  'pct0', 'pct1', 'pct2', 'num0', 'num1', 'num2', 'num3', 'int', 'usd0', 'min0', 'min1', 'ratio2',
];

const MINUS = '−';
const EM_DASH = '—';

const cache = new Map<number, Intl.NumberFormat>();
function nf(digits: number): Intl.NumberFormat {
  let f = cache.get(digits);
  if (!f) {
    f = new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
    cache.set(digits, f);
  }
  return f;
}

/** Fixed decimals, thousands separators, true minus; never prints "-0.0". */
function fixed(v: number, digits: number): string {
  const rounded = Number(v.toFixed(digits));
  const s = nf(digits).format(rounded === 0 ? 0 : rounded);
  return s.startsWith('-') ? MINUS + s.slice(1) : s;
}

function digitsOf(code: string): number {
  return Number(code.charAt(code.length - 1));
}

function dollars(v: number, digits: number): string {
  const s = fixed(Math.abs(v), digits);
  return `${v < 0 && s !== fixed(0, digits) ? MINUS : ''}$${s}`;
}

/** A sensible default when a figure declares no format. */
export function formatAuto(v: number): string {
  if (Number.isInteger(v)) return fixed(v, 0);
  const a = Math.abs(v);
  return fixed(v, a >= 100 ? 1 : a >= 1 ? 2 : 3);
}

/** Format one raw value by CONTRACT code. Null, undefined, and NaN print as an em dash. */
export function formatValue(v: number | null | undefined, fmt?: Format | null): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return EM_DASH;
  switch (fmt) {
    case 'pct0':
    case 'pct1':
    case 'pct2':
      return `${fixed(v * 100, digitsOf(fmt))}%`;
    case 'num0':
    case 'num1':
    case 'num2':
    case 'num3':
      return fixed(v, digitsOf(fmt));
    case 'int':
      return fixed(Math.round(v), 0);
    case 'usd0':
      return dollars(v, 0);
    case 'min0':
    case 'min1':
      return `${fixed(v, digitsOf(fmt))} min`;
    case 'ratio2':
      return `${fixed(v, 2)}×`;
    default:
      return formatAuto(v);
  }
}

/** "31.6%–32.9%" (en dash), matching the contract's ci_display style. */
export function formatInterval(
  lo: number | null | undefined,
  hi: number | null | undefined,
  fmt?: Format | null,
): string | null {
  if (lo === null || lo === undefined || hi === null || hi === undefined) return null;
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) return null;
  return `${formatValue(lo, fmt)}–${formatValue(hi, fmt)}`;
}

/**
 * Signed change between two values in the same format. Proportions change in
 * percentage points ("+4.2 pp"), never in percent.
 */
export function formatChange(d: number | null | undefined, fmt?: Format | null): string {
  if (d === null || d === undefined || !Number.isFinite(d)) return EM_DASH;
  const magnitude =
    fmt === 'pct0' || fmt === 'pct1' || fmt === 'pct2'
      ? `${fixed(Math.abs(d) * 100, digitsOf(fmt))} pp`
      : formatValue(Math.abs(d), fmt);
  const zero = magnitude === formatValue(0, fmt) || /^0(\.0+)? pp$/.test(magnitude);
  return `${zero ? '' : d > 0 ? '+' : MINUS}${magnitude}`;
}

/** Counts in tooltips and tables: "8,548". */
export function formatCount(n: number | null | undefined): string {
  return formatValue(n, 'int');
}

/** Decimals needed to print a tick step exactly (0.05 -> 2, 2.5 -> 1, 20 -> 0). */
function stepDecimals(step: number): number {
  if (!(step > 0) || !Number.isFinite(step)) return 0;
  const s = String(Number(step.toPrecision(10)));
  if (s.includes('e-')) return Math.min(6, Number(s.split('e-')[1]));
  const frac = s.split('.')[1];
  return Math.min(6, frac ? frac.length : 0);
}

/**
 * Axis tick formatter. Precision follows the tick STEP, not the format code:
 * a 0–50% axis with 10-point steps prints "10%", not "10.0%". Unit words
 * (minutes) stay in the axis label, so min ticks print the number alone.
 */
export function tickFormatter(
  fmt: Format | null | undefined,
  step: number,
  opts: { year?: boolean } = {},
): (v: number) => string {
  if (opts.year) return (v) => String(Math.round(v));
  switch (fmt) {
    case 'pct0':
    case 'pct1':
    case 'pct2': {
      const d = stepDecimals(step * 100);
      return (v) => `${fixed(v * 100, d)}%`;
    }
    case 'usd0': {
      const d = stepDecimals(step);
      return (v) => dollars(v, d);
    }
    case 'ratio2': {
      const d = stepDecimals(step);
      return (v) => `${fixed(v, d)}×`;
    }
    default: {
      const d = stepDecimals(step);
      return (v) => fixed(v, d);
    }
  }
}

/** True when every x looks like a calendar year (integers in 1800–2200). */
export function looksLikeYears(values: readonly number[]): boolean {
  return values.length > 0 && values.every((v) => Number.isInteger(v) && v >= 1800 && v <= 2200);
}
