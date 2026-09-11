import { scaleLinear } from 'd3-scale';
import { formatCount, formatValue, tickFormatter } from '@/lib/format';
import type { HistogramFigure } from '@/lib/types';
import {
  ChartPlot, DataTable, HGrid, TICKS, XTicks, YTicks, edgeAnchor, niceDomain, r1, textWidth, tickStep,
  type Variant,
} from './common';

/** A column with rounded top corners and a square base. */
function columnPath(x: number, w: number, yTop: number, base: number): string {
  const rad = Math.min(3, w / 2, base - yTop);
  return [
    `M${r1(x)},${r1(base)}`,
    `V${r1(yTop + rad)}`,
    `Q${r1(x)},${r1(yTop)} ${r1(x + rad)},${r1(yTop)}`,
    `H${r1(x + w - rad)}`,
    `Q${r1(x + w)},${r1(yTop)} ${r1(x + w)},${r1(yTop + rad)}`,
    `V${r1(base)}`,
    'Z',
  ].join('');
}

/**
 * Counts in bins, with optional labelled markers (a mean, a trimming cap).
 * The figure's `format` applies to the x values; counts print as integers.
 */
export function HistogramChart({ fig, variants }: { fig: HistogramFigure; variants: Variant[] }) {
  const fmt = fig.format;
  const bins = fig.bins;
  const markers = fig.markers ?? [];
  const lo = Math.min(...bins.map((b) => b.x0), ...markers.map((m) => m.x));
  const hi = Math.max(...bins.map((b) => b.x1), ...markers.map((m) => m.x));
  const yDomain = niceDomain([0, ...bins.map((b) => b.count)], { includeZero: true });
  const binLabel = (x0: number, x1: number) => `${formatValue(x0, fmt)}–${formatValue(x1, fmt)}`;

  const render = (variant: Variant, W: number) => {
    const sm = variant === 'sm';
    const yTicks = scaleLinear().domain(yDomain).ticks(sm ? 4 : 5);
    const ytf = tickFormatter('int', tickStep(yTicks));
    const left = Math.max(24, ...yTicks.map((t) => textWidth(ytf(t), 11))) + 10;
    const right = W - 12;
    const x = scaleLinear().domain([lo, hi]).range([left, right]);
    // marker labels stack in rows above the plot
    const rowEnds: number[] = [];
    const markerRows = markers.map((m) => {
      const w = textWidth(m.label, 11);
      const px = x(m.x);
      const anchor = edgeAnchor(px, m.label, W);
      const start = anchor === 'start' ? px : anchor === 'end' ? px - w : px - w / 2;
      let row = rowEnds.findIndex((end) => start > end + 8);
      if (row === -1) {
        row = rowEnds.length;
        rowEnds.push(0);
      }
      rowEnds[row] = start + w;
      return row;
    });
    const headTop = fig.y_label ? 24 : 8;
    const top = headTop + rowEnds.length * 14 + (rowEnds.length ? 8 : 4);
    const plotH = Math.round(W * (sm ? 0.55 : variant === 'lg' ? 0.3 : 0.36));
    const base = top + plotH;
    const y = scaleLinear().domain(yDomain).range([base, top]);
    const xTicks = x.ticks(TICKS[variant]);
    const xtf = tickFormatter(fmt, tickStep(xTicks));
    const gap = bins.length > 40 ? 1 : 2;
    const tickY = base + 16;
    return {
      height: (fig.x_label ? tickY + 19 : tickY) + 8,
      body: (
        <>
          {fig.y_label ? (
            <text className="ch-t-axis" x={0} y={12}>
              {fig.y_label}
            </text>
          ) : null}
          <HGrid y={y} ticks={yTicks} left={left} right={right} />
          {bins.map((b, i) => {
            const bx = x(b.x0) + gap / 2;
            const bw = Math.max(1, x(b.x1) - x(b.x0) - gap);
            return (
              <g key={i} className="ch-row">
                <title>{`${binLabel(b.x0, b.x1)}: ${formatCount(b.count)}`}</title>
                <rect className="ch-rowbg" x={r1(x(b.x0))} y={top} width={r1(Math.max(1, x(b.x1) - x(b.x0)))} height={plotH} />
                {b.count > 0 ? <path d={columnPath(bx, bw, y(b.count), base)} style={{ fill: 'var(--chart-fill)' }} /> : null}
              </g>
            );
          })}
          <line className="ch-axis" x1={left} x2={right} y1={r1(base)} y2={r1(base)} />
          {markers.map((m, i) => (
            <g key={`m${i}`} aria-hidden="true">
              <line className="ch-ref" x1={r1(x(m.x))} x2={r1(x(m.x))} y1={r1(top - 3)} y2={r1(base)} />
              <text className="ch-t-annot" x={r1(x(m.x))} y={r1(headTop + 10 + markerRows[i] * 14)} textAnchor={edgeAnchor(x(m.x), m.label, W)}>
                {m.label}
              </text>
            </g>
          ))}
          <YTicks y={y} ticks={yTicks} x={left - 8} format={ytf} />
          <XTicks x={x} ticks={xTicks} y={tickY} format={xtf} W={W} />
          {fig.x_label ? (
            <text className="ch-t-axis" x={r1((left + right) / 2)} y={r1(tickY + 19)} textAnchor="middle">
              {fig.x_label}
            </text>
          ) : null}
        </>
      ),
    };
  };

  return (
    <>
      <ChartPlot variants={variants} alt={fig.alt} render={render} />
      <DataTable
        label={`Data: ${fig.title ?? fig.alt}`}
        columns={[{ label: fig.x_label ?? 'Bin' }, { label: fig.y_label ?? 'Count', num: true }]}
        rows={[
          ...bins.map((b) => [binLabel(b.x0, b.x1), formatCount(b.count)]),
          ...markers.map((m) => [`Marker: ${m.label}`, formatValue(m.x, fmt)]),
        ]}
      />
    </>
  );
}
