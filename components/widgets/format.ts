import { format as d3format, precisionFixed } from 'd3-format';
import type { Format } from '@/lib/types';

/** Number formatting for widgets, keyed by the contract's `format` names (CONTRACT section 5). */
const F: Record<Exclude<Format, 'ratio2' | 'int'>, (v: number) => string> = {
  pct0: d3format('.0%'),
  pct1: d3format('.1%'),
  pct2: d3format('.2%'),
  num0: d3format(',.0f'),
  num1: d3format(',.1f'),
  num2: d3format(',.2f'),
  num3: d3format(',.3f'),
  usd0: d3format('$,.0f'),
  min0: d3format(',.0f'),
  min1: d3format(',.1f'),
};
const ratio = d3format('.2f');
const int = d3format(',d');

export function fmt(v: number | null | undefined, format: Format = 'num2'): string {
  if (v == null || !Number.isFinite(v)) return '–';
  if (format === 'ratio2') return `${ratio(v)}×`;
  if (format === 'int') return int(Math.round(v));
  return F[format](v);
}

/** A difference between two proportions in percentage points, signed: "+1.2 pts" (no sign on zero). */
export function pts(diff: number, digits = 1): string {
  if (!Number.isFinite(diff)) return '–';
  const v = Number((diff * 100).toFixed(digits));
  if (v === 0) return `${(0).toFixed(digits)} pts`;
  return `${d3format(`+.${digits}f`)(v)} pts`;
}

/**
 * Axis tick labels: a contract format with precision taken from the tick step
 * ("44%", not "44.0%"), or a caller's own function.
 */
export function axisFormatter(f: Format | ((v: number) => string), ticks: number[]): (v: number) => string {
  if (typeof f === 'function') return f;
  const step = ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 0;
  if (isPct(f)) {
    const d = step > 0 ? precisionFixed(step * 100) : 0;
    return (v) => `${d3format(`.${d}f`)(v * 100)}%`;
  }
  if (f === 'usd0') return (v) => fmt(v, 'usd0');
  const d = step > 0 ? precisionFixed(step) : 0;
  const base = d3format(`,.${d}f`);
  return f === 'ratio2' ? (v) => `${base(v)}×` : base;
}

/** A signed number: "+0.052". */
export function signed(v: number, digits = 3): string {
  if (!Number.isFinite(v)) return '–';
  return d3format(`+.${digits}f`)(v);
}

/** Percentage digits for a proportion format, used for derived values (for example MOE). */
export function isPct(format: Format | undefined): boolean {
  return format === 'pct0' || format === 'pct1' || format === 'pct2';
}

/** One more decimal than `format`, for standard errors and margins of error. */
export function finer(format: Format = 'num2'): Format {
  const up: Partial<Record<Format, Format>> = { pct0: 'pct1', pct1: 'pct2', num0: 'num1', num1: 'num2', num2: 'num3', min0: 'min1', int: 'num1' };
  return up[format] ?? format;
}
