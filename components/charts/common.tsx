import type { ReactNode } from 'react';
import { scaleLinear, type ScaleLinear } from 'd3-scale';
import type { Role } from '@/lib/types';

/**
 * Shared machinery for the server-rendered SVG charts.
 *
 * Responsiveness: a static SVG scales its text with its viewBox, so one
 * drawing cannot be legible at 340px and at 900px. Each chart therefore
 * draws two or three variants at nominal widths (sm 380, md 640, lg 900 for
 * wide figures) and CSS container queries on .ch-plot show the one that
 * fits (globals.css). Text stays within about ±15% of its design size.
 * Hidden variants are display:none, so screen readers meet one image.
 *
 * Colour: marks get colour only through roles (--role-*) or categorical
 * slots (--cat-*), always as CSS variables, so both themes follow.
 */

export type Variant = 'lg' | 'md' | 'sm';
export type FrameWidth = 'body' | 'wide' | 'full';

export const VARIANT_WIDTH: Record<Variant, number> = { lg: 900, md: 640, sm: 380 };
export const TICKS: Record<Variant, number> = { lg: 8, md: 6, sm: 4 };

export function variantsFor(frame: FrameWidth = 'body'): Variant[] {
  return frame === 'body' ? ['md', 'sm'] : ['lg', 'md', 'sm'];
}

export const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v);

/** One decimal keeps the SVG small without visible error. */
export const r1 = (v: number) => Math.round(v * 10) / 10;

// ------------------------------------------------------------------ colour

const ROLE_VAR: Record<Role, string> = {
  weighted: 'var(--role-weighted)',
  unweighted: 'var(--role-unweighted)',
  design: 'var(--role-design)',
  naive: 'var(--role-naive)',
  truth: 'var(--role-truth)',
  benchmark: 'var(--role-benchmark)',
  treated: 'var(--role-treated)',
  control: 'var(--role-control)',
  highlight: 'var(--role-highlight)',
  muted: 'var(--role-muted)',
  cat1: 'var(--cat-1)',
  cat2: 'var(--cat-2)',
  cat3: 'var(--cat-3)',
  cat4: 'var(--cat-4)',
  cat5: 'var(--cat-5)',
  cat6: 'var(--cat-6)',
  cat7: 'var(--cat-7)',
  cat8: 'var(--cat-8)',
};

/** The neutral mark for a figure that names no role. */
export const DEFAULT_MARK = 'var(--chart-mark)';

export function roleColor(role?: Role | null, fallback = DEFAULT_MARK): string {
  return (role && ROLE_VAR[role]) || fallback;
}

/** A line series: its role, else its categorical slot in order (never cycled; past 8 folds into grey). */
export function seriesColor(role: Role | null | undefined, index: number, count: number): string {
  if (role && ROLE_VAR[role]) return ROLE_VAR[role];
  if (count === 1) return DEFAULT_MARK;
  return `var(--cat-${Math.min(index + 1, 8)})`;
}

/** Roles with a meaning a legend can name. cat*, highlight, and muted identify nothing on their own. */
const ROLE_LABEL: Partial<Record<Role, string>> = {
  weighted: 'Weighted',
  unweighted: 'Unweighted',
  design: 'Design-based',
  naive: 'Naive',
  truth: 'Truth',
  benchmark: 'External benchmark',
  treated: 'Treated',
  control: 'Control',
};

export interface LegendItem {
  label: string;
  color: string;
  shape: 'dot' | 'line' | 'bar';
}

/** Legend entries for the distinct meaningful roles among the marks, in order of appearance. */
export function roleLegend(roles: (Role | null | undefined)[], shape: LegendItem['shape']): LegendItem[] {
  const seen = new Set<Role>();
  const out: LegendItem[] = [];
  for (const role of roles) {
    if (!role || seen.has(role) || !ROLE_LABEL[role]) continue;
    seen.add(role);
    out.push({ label: ROLE_LABEL[role]!, color: ROLE_VAR[role], shape });
  }
  return out;
}

/** A legend is shown only for two or more entries; one series is named by the title. */
export function Legend({ items }: { items: LegendItem[] }) {
  if (items.length < 2) return null;
  return (
    <ul className="ch-legend">
      {items.map((it) => (
        <li key={it.label}>
          <svg width="18" height="10" viewBox="0 0 18 10" aria-hidden="true">
            {it.shape === 'line' ? (
              <line x1="1" y1="5" x2="17" y2="5" style={{ stroke: it.color }} strokeWidth="2" strokeLinecap="round" />
            ) : it.shape === 'bar' ? (
              <rect x="4" y="0" width="10" height="10" rx="2" style={{ fill: it.color }} />
            ) : (
              <circle cx="9" cy="5" r="4" style={{ fill: it.color }} />
            )}
          </svg>
          {it.label}
        </li>
      ))}
    </ul>
  );
}

// ------------------------------------------------------------------ frame pieces

export interface PlotRender {
  height: number;
  body: ReactNode;
}

/** One <svg> per variant; CSS shows the one that fits the container. */
export function ChartPlot({
  variants,
  alt,
  render,
}: {
  variants: Variant[];
  alt: string;
  render: (variant: Variant, width: number) => PlotRender;
}) {
  return (
    <div className="ch-plot" data-lg={variants.includes('lg') ? '' : undefined}>
      {variants.map((v) => {
        const W = VARIANT_WIDTH[v];
        const { height, body } = render(v, W);
        return (
          <svg key={v} className={`v-${v}`} viewBox={`0 0 ${W} ${Math.ceil(height)}`} role="img" aria-label={alt}>
            {body}
          </svg>
        );
      })}
    </div>
  );
}

export interface DataColumn {
  label: string;
  num?: boolean;
}

/** The collapsed "Show data" table every chart carries: its values without hovering. */
export function DataTable({ label, columns, rows }: { label: string; columns: DataColumn[]; rows: ReactNode[][] }) {
  return (
    <details className="ch-data">
      <summary>Show data</summary>
      <div className="ch-data-scroll" tabIndex={0} role="region" aria-label={label}>
        <table className="ch-table">
          <thead>
            <tr>
              {columns.map((c, i) => (
                <th key={i} scope="col" className={c.num ? 'num' : undefined}>
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                {row.map((cell, j) => (
                  <td key={j} className={columns[j]?.num ? 'num' : undefined}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

// ------------------------------------------------------------------ text

/**
 * Width of a run of text in the chart sans (Inter), estimated per character
 * class. Leans wide, so a label is truncated rather than clipped.
 */
export function textWidth(text: string, fontSize = 12): number {
  let w = 0;
  for (const ch of text) {
    if (/[A-Z]/.test(ch)) w += 0.68;
    else if (/[0-9$%]/.test(ch)) w += 0.62;
    else if (/[ilj'.,:;|!·]/.test(ch)) w += 0.3;
    else if (/[mwMW]/.test(ch)) w += 0.86;
    else if (ch === ' ') w += 0.28;
    else w += 0.56;
  }
  return w * fontSize;
}

export function truncate(text: string, maxWidth: number, fontSize = 12): string {
  if (textWidth(text, fontSize) <= maxWidth) return text;
  let s = text;
  while (s.length > 1 && textWidth(`${s}…`, fontSize) > maxWidth) s = s.slice(0, -1);
  return `${s.trimEnd()}…`;
}

/** Anchor for text centred at x that must stay inside [0, W]. */
export function edgeAnchor(x: number, text: string, W: number, fontSize = 11): 'start' | 'middle' | 'end' {
  const half = textWidth(text, fontSize) / 2;
  if (x - half < 0) return 'start';
  if (x + half > W) return 'end';
  return 'middle';
}

/**
 * Push 1-D label positions apart to at least `minGap`, moving each as little
 * as possible and keeping order; results come back in input order.
 * (Two-pass sweep, from ctzn-viz registry/ctzn-viz/lib/layout.ts.)
 */
export function spreadLabels(positions: readonly number[], minGap: number, bounds?: readonly [number, number]): number[] {
  const order = positions.map((value, index) => ({ value, index })).sort((a, b) => a.value - b.value);
  const placed = order.map((o) => o.value);
  for (let i = 1; i < placed.length; i++) {
    if (placed[i] - placed[i - 1] < minGap) placed[i] = placed[i - 1] + minGap;
  }
  if (bounds) {
    const [lo, hi] = bounds;
    if (placed.length && placed[placed.length - 1] > hi) placed[placed.length - 1] = hi;
    for (let i = placed.length - 2; i >= 0; i--) {
      if (placed[i + 1] - placed[i] < minGap) placed[i] = placed[i + 1] - minGap;
    }
    if (placed.length && placed[0] < lo) {
      const shift = lo - placed[0];
      for (let i = 0; i < placed.length; i++) placed[i] += shift;
    }
  }
  const out = new Array<number>(positions.length);
  order.forEach((o, i) => {
    out[o.index] = placed[i];
  });
  return out;
}

// ------------------------------------------------------------------ scales and axes

/** Extent of the values, optionally through zero, niced; a fixed domain from the figure wins. */
export function niceDomain(
  values: number[],
  opts: { includeZero?: boolean; fixed?: [number, number] | null; count?: number } = {},
): [number, number] {
  if (opts.fixed && isNum(opts.fixed[0]) && isNum(opts.fixed[1])) return [opts.fixed[0], opts.fixed[1]];
  let lo = values.length ? Math.min(...values) : 0;
  let hi = values.length ? Math.max(...values) : 1;
  if (opts.includeZero) {
    lo = Math.min(lo, 0);
    hi = Math.max(hi, 0);
  }
  if (lo === hi) {
    const d = Math.abs(lo) * 0.1 || 1;
    lo -= d;
    hi += d;
  }
  return scaleLinear().domain([lo, hi]).nice(opts.count ?? 6).domain() as [number, number];
}

export function tickStep(ticks: number[]): number {
  return ticks.length > 1 ? Math.abs(ticks[1] - ticks[0]) : 1;
}

/** Vertical gridlines at x ticks. */
export function VGrid({ x, ticks, top, bottom }: { x: ScaleLinear<number, number>; ticks: number[]; top: number; bottom: number }) {
  return (
    <g aria-hidden="true">
      {ticks.map((t, i) => (
        <line key={i} className="ch-grid" x1={r1(x(t))} x2={r1(x(t))} y1={r1(top)} y2={r1(bottom)} />
      ))}
    </g>
  );
}

/** Horizontal gridlines at y ticks. */
export function HGrid({ y, ticks, left, right }: { y: ScaleLinear<number, number>; ticks: number[]; left: number; right: number }) {
  return (
    <g aria-hidden="true">
      {ticks.map((t, i) => (
        <line key={i} className="ch-grid" x1={r1(left)} x2={r1(right)} y1={r1(y(t))} y2={r1(y(t))} />
      ))}
    </g>
  );
}

/** Tick labels under a horizontal axis; labels at the edges anchor inward. */
export function XTicks({
  x,
  ticks,
  y,
  format,
  W,
}: {
  x: ScaleLinear<number, number>;
  ticks: number[];
  y: number;
  format: (v: number) => string;
  W: number;
}) {
  return (
    <g aria-hidden="true">
      {ticks.map((t, i) => {
        const label = format(t);
        return (
          <text key={i} className="ch-t-tick" x={r1(x(t))} y={r1(y)} textAnchor={edgeAnchor(x(t), label, W)}>
            {label}
          </text>
        );
      })}
    </g>
  );
}

/** Tick labels left of a vertical axis. */
export function YTicks({
  y,
  ticks,
  x,
  format,
}: {
  y: ScaleLinear<number, number>;
  ticks: number[];
  x: number;
  format: (v: number) => string;
}) {
  return (
    <g aria-hidden="true">
      {ticks.map((t, i) => (
        <text key={i} className="ch-t-tick" x={r1(x)} y={r1(y(t))} dy="0.35em" textAnchor="end">
          {format(t)}
        </text>
      ))}
    </g>
  );
}

// ------------------------------------------------------------------ row charts (dot, bar)

export type RowItem<T> = { kind: 'group'; label: string } | { kind: 'row'; row: T; index: number };

/** Rows with a `group` get a section header each time the group changes. */
export function groupItems<T extends { group?: string | null }>(rows: T[]): RowItem<T>[] {
  const out: RowItem<T>[] = [];
  let last: string | null = null;
  rows.forEach((row, index) => {
    const g = row.group ?? null;
    if (g && g !== last) out.push({ kind: 'group', label: g });
    last = g;
    out.push({ kind: 'row', row, index });
  });
  return out;
}

export interface RowPos {
  y0: number;
  h: number;
  /** vertical centre of the mark */
  cy: number;
  /** vertical centre of the label */
  labelY: number;
}

export interface RowGeom {
  stacked: boolean;
  plotLeft: number;
  plotRight: number;
  /** labels end here (right-aligned) in side mode; start at 0 in stacked mode */
  labelX: number;
  labelMax: number;
  top: number;
  plotBottom: number;
  tickY: number;
  axisLabelY: number;
  height: number;
  positions: RowPos[];
}

/**
 * Geometry for one-row-per-estimate charts. md/lg put labels in a left
 * gutter; sm stacks each label above its mark so long labels survive a
 * phone-width column.
 */
export function rowGeometry<T>(
  items: RowItem<T>[],
  variant: Variant,
  W: number,
  opts: { labels: string[]; top: number; rightPad: number; xLabel: boolean },
): RowGeom {
  const stacked = variant === 'sm';
  let labelMax: number;
  let labelX: number;
  let plotLeft: number;
  if (stacked) {
    labelMax = W - 8;
    labelX = 0;
    plotLeft = 8;
  } else {
    const widest = Math.max(40, ...opts.labels.map((l) => textWidth(l, 12)));
    labelMax = Math.min(widest, W * 0.36);
    labelX = labelMax + 2;
    plotLeft = labelX + 16;
  }
  const plotRight = W - opts.rightPad;
  const positions: RowPos[] = [];
  let y = opts.top;
  items.forEach((it, i) => {
    if (it.kind === 'group') {
      const h = i === 0 ? 22 : 32;
      positions.push({ y0: y, h, cy: y + h - 9, labelY: y + h - 9 });
      y += h;
    } else if (stacked) {
      positions.push({ y0: y, h: 40, labelY: y + 12, cy: y + 29 });
      y += 40;
    } else {
      positions.push({ y0: y, h: 26, labelY: y + 13, cy: y + 13 });
      y += 26;
    }
  });
  const plotBottom = y + 4;
  const tickY = plotBottom + 15;
  const axisLabelY = tickY + 19;
  return {
    stacked,
    plotLeft,
    plotRight,
    labelX,
    labelMax,
    top: opts.top,
    plotBottom,
    tickY,
    axisLabelY,
    height: (opts.xLabel ? axisLabelY : tickY) + 8,
    positions,
  };
}
