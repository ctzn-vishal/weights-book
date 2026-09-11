'use client';

/**
 * Shared building blocks for the book's widgets: frame, controls, stat tiles,
 * and two small SVG charts (dot rows and histogram). Colours come only from the
 * design tokens in app/globals.css; every meaningful distinction also has a
 * shape, a dash, or a label.
 *
 * Layout rule: chart containers and scrolling tables use `contain: inline-size`
 * and SVGs draw on a viewBox at 100% width, so no widget can widen its parent
 * (a flex or grid column) on a narrow screen. Before the first measurement
 * (server render, no JavaScript) a chart scales down instead of overflowing.
 */

import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from 'react';
import clsx from 'clsx';
import { scaleLinear } from 'd3-scale';
import type { Format } from '@/lib/types';
import { axisFormatter } from './format';

/** A contract format (tick precision follows the tick step) or a formatting function. */
export type TickFormat = Format | ((v: number) => string);

// ------------------------------------------------------------------ layout

/** Width of a container in CSS pixels; renders at `initial` on the server and first paint. */
export function useMeasuredWidth<T extends HTMLElement = HTMLDivElement>(initial = 600) {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(initial);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver((entries) => {
      const w = Math.floor(entries[0].contentRect.width);
      if (w > 0) setWidth(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

/** Class for a chart's measured container. */
export const chartBoxClass = 'w-full [contain:inline-size]';
/** Class for a horizontally scrolling table wrapper. */
export const scrollBoxClass = 'overflow-x-auto [contain:inline-size]';

/** An SVG that draws in measured pixels but scales to its container until measured. */
export function ChartSvg({
  width,
  height,
  label,
  children,
}: {
  width: number;
  height: number;
  label: string;
  children: ReactNode;
}) {
  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label={label} className="block h-auto overflow-visible">
      {children}
    </svg>
  );
}

export function WidgetFrame({
  title,
  subtitle,
  children,
  className,
}: {
  title: string;
  subtitle?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={`${id}-title`}
      className={clsx(
        'not-prose my-8 min-w-0 rounded-lg border border-rule bg-surface p-4 font-sans text-sm leading-relaxed text-ink sm:p-5',
        className,
      )}
    >
      <div className="mb-3">
        <div id={`${id}-title`} className="text-base font-semibold leading-snug text-ink">
          {title}
        </div>
        {subtitle ? <div className="mt-1 text-ink-2">{subtitle}</div> : null}
      </div>
      {children}
    </section>
  );
}

export const buttonClass =
  'inline-flex items-center rounded-md border border-[var(--border-strong)] bg-surface px-3 py-1.5 text-sm font-medium text-ink hover:bg-sunken focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent)] disabled:opacity-50';

export function SeedControl({
  seed,
  onNext,
  label = 'Draw a new sample',
  note,
}: {
  seed: number;
  onNext: () => void;
  label?: string;
  note?: ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <button type="button" onClick={onNext} className={buttonClass}>
        {label}
      </button>
      <span className="tabular-nums text-ink-2" aria-live="polite">
        Seed {seed}
      </span>
      {note ? <span className="text-xs text-muted">{note}</span> : null}
    </div>
  );
}

export function HeldFixed({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 border-t border-rule pt-2 text-xs leading-relaxed text-ink-2">
      <span className="font-semibold text-ink">What is held fixed. </span>
      {children}
    </p>
  );
}

export function Note({ children, tone = 'plain' }: { children: ReactNode; tone?: 'plain' | 'caveat' }) {
  return (
    <p
      className={clsx(
        'mt-3 text-xs leading-relaxed',
        tone === 'caveat' ? 'border-l-2 border-[var(--accent)] pl-2 text-ink' : 'text-ink-2',
      )}
    >
      {children}
    </p>
  );
}

// ------------------------------------------------------------------ controls

export interface SegmentOption<T extends string> {
  value: T;
  label: ReactNode;
}

/** A segmented control built from native radio inputs (arrow keys move within the group). */
export function Segmented<T extends string>({
  legend,
  options,
  value,
  onChange,
  hideLegend = false,
  className,
}: {
  legend: string;
  options: SegmentOption<T>[];
  value: T;
  onChange: (v: T) => void;
  hideLegend?: boolean;
  className?: string;
}) {
  const name = useId();
  return (
    <fieldset className={clsx('min-w-0', className)}>
      <legend className={clsx('mb-1 text-xs font-medium text-ink-2', hideLegend && 'sr-only')}>{legend}</legend>
      <div className="inline-flex max-w-full flex-wrap gap-0.5 rounded-md border border-[var(--border-strong)] bg-surface p-0.5">
        {options.map((o) => (
          <label key={o.value} className="relative cursor-pointer">
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="peer sr-only"
            />
            <span className="block rounded px-2.5 py-1 text-sm text-ink-2 hover:bg-sunken peer-checked:bg-[var(--text)] peer-checked:font-semibold peer-checked:text-[var(--surface)] peer-focus-visible:outline-2 peer-focus-visible:outline-offset-1 peer-focus-visible:outline-[var(--accent)]">
              {o.label}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

export function Slider({
  label,
  min,
  max,
  step,
  value,
  onChange,
  display,
  hint,
}: {
  label: string;
  min: number;
  max: number;
  step: number;
  value: number;
  onChange: (v: number) => void;
  display: string;
  hint?: ReactNode;
}) {
  const id = useId();
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-xs font-medium text-ink-2">
          {label}
        </label>
        <output htmlFor={id} className="text-sm font-semibold tabular-nums text-ink">
          {display}
        </output>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={display}
        onChange={(e) => onChange(Number(e.target.value))}
        className="mt-1 w-full cursor-pointer"
        style={{ accentColor: 'var(--accent)' }}
      />
      {hint ? <div className="text-xs text-muted">{hint}</div> : null}
    </div>
  );
}

export function Stat({
  label,
  value,
  sub,
  strong = false,
}: {
  label: ReactNode;
  value: ReactNode;
  sub?: ReactNode;
  strong?: boolean;
}) {
  return (
    <div className={clsx('min-w-0 rounded-md border border-rule px-3 py-2', strong ? 'bg-sunken' : 'bg-surface')}>
      <div className="text-xs text-ink-2">{label}</div>
      <div className="text-lg font-semibold tabular-nums leading-tight text-ink">{value}</div>
      {sub ? <div className="text-xs text-muted">{sub}</div> : null}
    </div>
  );
}

// ------------------------------------------------------------------ marks

export type Shape = 'circle' | 'diamond' | 'square' | 'triangle';

export function Mark({
  shape = 'circle',
  x,
  y,
  r = 5,
  color = 'var(--role-weighted)',
  hollow = false,
}: {
  shape?: Shape;
  x: number;
  y: number;
  r?: number;
  color?: string;
  hollow?: boolean;
}) {
  const common = {
    fill: hollow ? 'var(--surface)' : color,
    stroke: color,
    strokeWidth: 1.75,
  };
  if (shape === 'square') return <rect x={x - r * 0.85} y={y - r * 0.85} width={r * 1.7} height={r * 1.7} {...common} />;
  if (shape === 'diamond') {
    const s = r * 1.2;
    return <polygon points={`${x},${y - s} ${x + s},${y} ${x},${y + s} ${x - s},${y}`} {...common} />;
  }
  if (shape === 'triangle') {
    const s = r * 1.15;
    return <polygon points={`${x},${y - s} ${x + s},${y + s * 0.8} ${x - s},${y + s * 0.8}`} {...common} />;
  }
  return <circle cx={x} cy={y} r={r} {...common} />;
}

/** A small inline legend swatch that matches Mark. */
export function Swatch({ shape = 'circle', color, hollow }: { shape?: Shape; color: string; hollow?: boolean }) {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true" className="inline-block align-[-2px]">
      <Mark shape={shape} x={7} y={7} r={4.5} color={color} hollow={hollow} />
    </svg>
  );
}

// ------------------------------------------------------------------ dot rows

export interface DotRowDatum {
  key: string;
  label: string;
  value: number;
  lo?: number;
  hi?: number;
  /** Secondary interval (for example a naive MOE), drawn thin and dashed. */
  lo2?: number;
  hi2?: number;
  valueText?: string;
  shape?: Shape;
  color?: string;
  hollow?: boolean;
  strong?: boolean;
  muted?: boolean;
}

interface DotRowsProps {
  rows: DotRowDatum[];
  domain: [number, number];
  tickFormat: TickFormat;
  reference?: { value: number; label: string };
  ariaLabel: string;
  rowHeight?: number;
  /** When set (and the chart is wide enough), labels sit left of the track instead of above it. */
  labelWidth?: number;
  /** Width reserved on the right for value text in the labels-left layout. */
  valueWidth?: number;
}

/** A non-degenerate domain: nearly equal ends are spread apart so ticks stay distinct. */
function safeDomain([a, b]: [number, number]): [number, number] {
  if (b - a > 1e-9 * Math.max(1, Math.abs(a), Math.abs(b))) return [a, b];
  const pad = Math.max(Math.abs(a) * 0.1, 0.01);
  return [a - pad, b + pad];
}

function ReferenceLine({ x, y1, y2, label, width }: { x: number; y1: number; y2: number; label: string; width: number }) {
  return (
    <g>
      <line x1={x} x2={x} y1={y1} y2={y2} stroke="var(--role-truth)" strokeWidth={1.5} strokeDasharray="5 3" />
      <text
        x={x}
        y={y1 - 4}
        textAnchor={x > width * 0.7 ? 'end' : x < width * 0.3 ? 'start' : 'middle'}
        fontSize={11}
        fontWeight={600}
        fill="var(--role-truth)"
      >
        {label}
      </text>
    </g>
  );
}

/**
 * Rows of labelled dots on one shared horizontal axis, with an optional
 * reference line (for example the simulated population truth).
 */
export function DotRows({ rows, domain, tickFormat, reference, ariaLabel, rowHeight = 34, labelWidth, valueWidth = 0 }: DotRowsProps) {
  const [ref, width] = useMeasuredWidth(560);
  const left = labelWidth != null && width >= 480;
  if (left) {
    return (
      <DotRowsLeft {...{ rows, domain, tickFormat, reference, ariaLabel, valueWidth, width }} labelWidth={labelWidth} containerRef={ref} />
    );
  }
  const m = { l: 10, r: 18, t: reference ? 20 : 6, b: 26 };
  const h = m.t + rows.length * rowHeight + m.b;
  const x = scaleLinear().domain(safeDomain(domain)).range([m.l, Math.max(m.l + 60, width - m.r)]).nice();
  const ticks = x.ticks(width < 420 ? 4 : 6);
  const tf = axisFormatter(tickFormat, ticks);
  return (
    <div ref={ref} className={chartBoxClass}>
      <ChartSvg width={width} height={h} label={ariaLabel}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={m.t} y2={h - m.b} stroke="var(--chart-grid)" />
            <text x={x(t)} y={h - m.b + 16} textAnchor="middle" fontSize={11} fill="var(--chart-tick)">
              {tf(t)}
            </text>
          </g>
        ))}
        <line x1={m.l} x2={width - m.r} y1={h - m.b} y2={h - m.b} stroke="var(--chart-axis)" />
        {rows.map((r, i) => {
          const y0 = m.t + i * rowHeight;
          const yt = y0 + rowHeight - 10;
          const color = r.muted ? 'var(--role-muted)' : r.color ?? 'var(--role-weighted)';
          return (
            <g key={r.key} opacity={r.muted ? 0.75 : 1}>
              <text x={m.l} y={y0 + 12} fontSize={12} fill="var(--chart-annotation)" fontWeight={r.strong ? 700 : 400}>
                {r.label}
                {r.valueText ? (
                  <tspan fill="var(--chart-label)" fontWeight={r.strong ? 700 : 400}>
                    {'  '}
                    {r.valueText}
                  </tspan>
                ) : null}
              </text>
              {r.lo2 != null && r.hi2 != null ? (
                <line x1={x(r.lo2)} x2={x(r.hi2)} y1={yt + 7} y2={yt + 7} stroke={color} strokeWidth={1.25} strokeDasharray="3 2" />
              ) : null}
              {r.lo != null && r.hi != null ? (
                <line x1={x(r.lo)} x2={x(r.hi)} y1={yt} y2={yt} stroke={color} strokeWidth={2.25} strokeLinecap="round" />
              ) : null}
              <Mark shape={r.shape} x={x(r.value)} y={yt} r={r.strong ? 6.5 : 5} color={color} hollow={r.hollow} />
            </g>
          );
        })}
        {reference ? <ReferenceLine x={x(reference.value)} y1={m.t - 4} y2={h - m.b} label={reference.label} width={width} /> : null}
      </ChartSvg>
    </div>
  );
}

function DotRowsLeft({
  rows,
  domain,
  tickFormat,
  reference,
  ariaLabel,
  labelWidth,
  valueWidth = 0,
  width,
  containerRef,
}: DotRowsProps & { labelWidth: number; width: number; containerRef: RefObject<HTMLDivElement | null> }) {
  const rowH = 24;
  const m = { t: reference ? 20 : 6, b: 26, r: 12 };
  const h = m.t + rows.length * rowH + m.b;
  const x0 = labelWidth;
  const x1 = Math.max(x0 + 60, width - m.r - valueWidth);
  const x = scaleLinear().domain(safeDomain(domain)).range([x0, x1]).nice();
  const ticks = x.ticks(width < 640 ? 4 : 6);
  const tf = axisFormatter(tickFormat, ticks);
  return (
    <div ref={containerRef} className={chartBoxClass}>
      <ChartSvg width={width} height={h} label={ariaLabel}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={m.t} y2={h - m.b} stroke="var(--chart-grid)" />
            <text x={x(t)} y={h - m.b + 16} textAnchor="middle" fontSize={11} fill="var(--chart-tick)">
              {tf(t)}
            </text>
          </g>
        ))}
        <line x1={x0} x2={x1} y1={h - m.b} y2={h - m.b} stroke="var(--chart-axis)" />
        {rows.map((r, i) => {
          const yc = m.t + i * rowH + rowH / 2;
          const color = r.muted ? 'var(--role-muted)' : r.color ?? 'var(--role-weighted)';
          return (
            <g key={r.key}>
              <text x={x0 - 10} y={yc + 4} textAnchor="end" fontSize={12} fill="var(--chart-annotation)" fontWeight={r.strong ? 700 : 400}>
                {r.label}
              </text>
              {r.lo2 != null && r.hi2 != null ? (
                <line x1={x(r.lo2)} x2={x(r.hi2)} y1={yc + 6} y2={yc + 6} stroke={color} strokeWidth={1.25} strokeDasharray="3 2" />
              ) : null}
              {r.lo != null && r.hi != null ? (
                <line x1={x(r.lo)} x2={x(r.hi)} y1={yc} y2={yc} stroke={color} strokeWidth={2.25} strokeLinecap="round" />
              ) : null}
              <Mark shape={r.shape} x={x(r.value)} y={yc} r={r.strong ? 6 : 4.5} color={color} hollow={r.hollow} />
              {r.valueText && valueWidth > 0 ? (
                <text x={width - m.r} y={yc + 4} textAnchor="end" fontSize={11.5} fill="var(--chart-label)" className="tabular-nums">
                  {r.valueText}
                </text>
              ) : null}
            </g>
          );
        })}
        {reference ? <ReferenceLine x={x(reference.value)} y1={m.t - 4} y2={h - m.b} label={reference.label} width={width} /> : null}
      </ChartSvg>
    </div>
  );
}

// ------------------------------------------------------------------ histogram

export interface HistBin {
  x0: number;
  x1: number;
  count: number;
}

export function binValues(values: ArrayLike<number>, domain: [number, number], nBins: number): HistBin[] {
  const [lo, hi] = domain;
  const w = (hi - lo) / nBins;
  const bins: HistBin[] = Array.from({ length: nBins }, (_, i) => ({ x0: lo + i * w, x1: lo + (i + 1) * w, count: 0 }));
  for (let i = 0; i < values.length; i++) {
    const k = Math.min(nBins - 1, Math.max(0, Math.floor((values[i] - lo) / w)));
    bins[k].count++;
  }
  return bins;
}

export function Histogram({
  bins,
  tickFormat,
  markers = [],
  ariaLabel,
  height = 150,
  color = 'var(--role-weighted)',
  yMax,
  title,
}: {
  bins: HistBin[];
  tickFormat: TickFormat;
  markers?: { value: number; label: string; dash?: string; color?: string }[];
  ariaLabel: string;
  height?: number;
  color?: string;
  yMax?: number;
  title?: string;
}) {
  const [ref, width] = useMeasuredWidth(560);
  const m = { l: 10, r: 14, t: title ? 30 : 16, b: 24 };
  const x = scaleLinear()
    .domain([bins[0].x0, bins[bins.length - 1].x1])
    .range([m.l, Math.max(m.l + 60, width - m.r)]);
  const top = yMax ?? Math.max(1, ...bins.map((b) => b.count));
  const y = scaleLinear().domain([0, top]).range([height - m.b, m.t + 6]);
  const ticks = x.ticks(width < 420 ? 4 : 6);
  const tf = axisFormatter(tickFormat, ticks);
  return (
    <div ref={ref} className={chartBoxClass}>
      <ChartSvg width={width} height={height} label={ariaLabel}>
        {title ? (
          <text x={m.l} y={13} fontSize={12} fontWeight={600} fill="var(--chart-annotation)">
            {title}
          </text>
        ) : null}
        {bins.map((b, i) => (
          <rect
            key={i}
            x={x(b.x0) + 0.5}
            y={y(b.count)}
            width={Math.max(0, x(b.x1) - x(b.x0) - 1)}
            height={Math.max(0, y(0) - y(b.count))}
            fill={color}
            opacity={0.8}
          />
        ))}
        <line x1={m.l} x2={width - m.r} y1={y(0)} y2={y(0)} stroke="var(--chart-axis)" />
        {ticks.map((t, i) => (
          <text key={i} x={x(t)} y={height - m.b + 15} textAnchor="middle" fontSize={11} fill="var(--chart-tick)">
            {tf(t)}
          </text>
        ))}
        {markers.map((mk, i) => {
          const xm = x(mk.value);
          const anchor = xm > width * 0.72 ? 'end' : xm < width * 0.28 ? 'start' : 'middle';
          return (
            <g key={i}>
              <line
                x1={xm}
                x2={xm}
                y1={m.t - 2 + i * 12}
                y2={y(0)}
                stroke={mk.color ?? 'var(--role-truth)'}
                strokeWidth={1.5}
                strokeDasharray={mk.dash ?? '5 3'}
              />
              <text x={xm} y={m.t - 5 + i * 12} textAnchor={anchor} fontSize={11} fontWeight={600} fill={mk.color ?? 'var(--role-truth)'}>
                {mk.label}
              </text>
            </g>
          );
        })}
      </ChartSvg>
    </div>
  );
}
