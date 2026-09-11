import { scaleLinear } from 'd3-scale';
import { area, line } from 'd3-shape';
import { formatInterval, formatValue, looksLikeYears, tickFormatter } from '@/lib/format';
import type { LineFigure, LinePoint } from '@/lib/types';
import {
  ChartPlot, DataTable, HGrid, Legend, TICKS, XTicks, YTicks, edgeAnchor, isNum, niceDomain, r1,
  seriesColor, spreadLabels, textWidth, tickStep, truncate, type Variant,
} from './common';

interface Annot {
  x: number;
  label: string;
}

/** Greedy rows for labels above the plot, so neighbouring annotations never overprint. */
function stackLabels(items: { px: number; label: string }[], W: number): number[] {
  const rowEnds: number[] = [];
  return items.map(({ px, label }) => {
    const w = textWidth(label, 11);
    const anchor = edgeAnchor(px, label, W);
    const start = anchor === 'start' ? px : anchor === 'end' ? px - w : px - w / 2;
    let row = rowEnds.findIndex((end) => start > end + 8);
    if (row === -1) {
      row = rowEnds.length;
      rowEnds.push(0);
    }
    rowEnds[row] = start + w;
    return row;
  });
}

/**
 * Series over x (usually years) with optional 95% bands. Each break segment
 * is drawn on its own: a line is never drawn across a series break (a
 * redesign, a method change). Annotations are labelled vertical rules. Two to
 * four series also get direct labels at their right ends, beside the legend.
 */
export function LineChart({ fig, variants }: { fig: LineFigure; variants: Variant[] }) {
  const fmt = fig.format;
  const series = fig.series;
  const n = series.length;
  const colors = series.map((s, i) => seriesColor(s.role, i, n));
  const annots: Annot[] = (fig.annotations ?? []).filter((a) => isNum(a.x));

  const xs: number[] = [];
  const ys: number[] = [];
  for (const s of series) {
    for (const seg of s.segments) {
      for (const p of seg) {
        if (isNum(p.x)) xs.push(p.x);
        for (const v of [p.y, p.lo, p.hi]) if (isNum(v)) ys.push(v);
      }
    }
  }
  for (const a of annots) xs.push(a.x);
  const years = looksLikeYears(xs);
  const xDomain: [number, number] = xs.length ? [Math.min(...xs), Math.max(...xs)] : [0, 1];
  if (xDomain[0] === xDomain[1]) {
    xDomain[0] -= 1;
    xDomain[1] += 1;
  }
  const yDomain = niceDomain(ys, { fixed: fig.y_domain ?? null });
  const xLabelOf = (v: number) => (years ? String(v) : formatValue(v, null));

  const pointCount = series.map((s) => s.segments.reduce((k, seg) => k + seg.length, 0));
  const lastPoint = series.map((s): LinePoint | null => {
    for (let j = s.segments.length - 1; j >= 0; j--) {
      const seg = s.segments[j];
      for (let k = seg.length - 1; k >= 0; k--) if (isNum(seg[k].y)) return seg[k];
    }
    return null;
  });
  const directLabels = n >= 2 && n <= 4;

  const render = (variant: Variant, W: number) => {
    const sm = variant === 'sm';
    const direct = directLabels && !sm;
    const labelW = direct ? Math.min(Math.max(...series.map((s) => textWidth(s.name, 12))), W * 0.22) + 24 : 0;
    const yTicks = scaleLinear().domain(yDomain).ticks(sm ? 4 : 5);
    const ytf = tickFormatter(fmt, tickStep(yTicks));
    const left = Math.max(24, ...yTicks.map((t) => textWidth(ytf(t), 11))) + 10;
    const right = W - (direct ? labelW : 14);
    const provisional = scaleLinear().domain(xDomain).range([left, right]);
    const annotRows = stackLabels(annots.map((a) => ({ px: provisional(a.x), label: a.label })), W);
    const nRows = annots.length ? Math.max(...annotRows) + 1 : 0;
    const headTop = fig.y_label ? 24 : 8;
    const top = headTop + nRows * 14 + (nRows ? 8 : 4);
    const plotH = Math.round(W * (sm ? 0.6 : variant === 'lg' ? 0.34 : 0.42));
    const bottom = top + plotH;
    const x = provisional;
    const y = scaleLinear().domain(yDomain).range([bottom, top]);
    let xTicks = x.ticks(TICKS[variant]);
    if (years) xTicks = xTicks.filter((t) => Number.isInteger(t));
    const xtf = tickFormatter(null, tickStep(xTicks), { year: years });
    const tickY = bottom + 16;
    const height = (fig.x_label ? tickY + 19 : tickY) + 8;

    const band = area<LinePoint>()
      .defined((p) => isNum(p.lo) && isNum(p.hi))
      .x((p) => x(p.x))
      .y0((p) => y(p.lo as number))
      .y1((p) => y(p.hi as number))
      .digits(1);
    const path = line<LinePoint>()
      .defined((p) => isNum(p.y))
      .x((p) => x(p.x))
      .y((p) => y(p.y as number))
      .digits(1);

    const ends = lastPoint.map((p) => (p ? y(p.y as number) : bottom));
    const labelYs = direct ? spreadLabels(ends, 15, [top, bottom]) : [];

    return {
      height,
      body: (
        <>
          {fig.y_label ? (
            <text className="ch-t-axis" x={0} y={12}>
              {fig.y_label}
            </text>
          ) : null}
          <HGrid y={y} ticks={yTicks} left={left} right={right} />
          <line className="ch-axis" x1={left} x2={r1(right)} y1={r1(bottom)} y2={r1(bottom)} />
          {annots.map((a, i) => (
            <g key={`a${i}`} aria-hidden="true">
              <line className="ch-annot-rule" x1={r1(x(a.x))} x2={r1(x(a.x))} y1={r1(top - 3)} y2={r1(bottom)} />
              <text
                className="ch-t-annot"
                x={r1(x(a.x))}
                y={r1(headTop + 10 + annotRows[i] * 14)}
                textAnchor={edgeAnchor(x(a.x), a.label, W)}
              >
                {a.label}
              </text>
            </g>
          ))}
          {series.map((s, i) => (
            <g key={`b${i}`} aria-hidden="true">
              {s.segments.map((seg, j) => {
                const d = band(seg);
                return d ? <path key={j} d={d} style={{ fill: colors[i] }} fillOpacity={0.14} /> : null;
              })}
            </g>
          ))}
          {series.map((s, i) => (
            <g key={`l${i}`}>
              {s.segments.map((seg, j) => {
                const d = seg.length > 1 ? path(seg) : null;
                return d ? (
                  <path key={j} d={d} fill="none" style={{ stroke: colors[i] }} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
                ) : null;
              })}
              {s.segments.map((seg, j) =>
                seg.map((p, k) =>
                  isNum(p.y) && (pointCount[i] <= 30 || seg.length === 1) ? (
                    <circle
                      key={`${j}-${k}`}
                      cx={r1(x(p.x))}
                      cy={r1(y(p.y))}
                      r={seg.length === 1 ? 3.5 : 3}
                      style={{ fill: colors[i], stroke: 'var(--chart-surface)' }}
                      strokeWidth={1.5}
                    />
                  ) : null,
                ),
              )}
            </g>
          ))}
          {series.map((s, i) => (
            <g key={`h${i}`}>
              {s.segments.map((seg, j) =>
                seg.map((p, k) => {
                  if (!isNum(p.y)) return null;
                  const ci = formatInterval(p.lo, p.hi, fmt);
                  return (
                    <circle key={`${j}-${k}`} className="ch-hit" cx={r1(x(p.x))} cy={r1(y(p.y))} r={9}>
                      <title>{`${s.name}, ${xLabelOf(p.x)}: ${formatValue(p.y, fmt)}${ci ? ` (95% CI ${ci})` : ''}`}</title>
                    </circle>
                  );
                }),
              )}
            </g>
          ))}
          {direct
            ? series.map((s, i) => {
                const p = lastPoint[i];
                if (!p) return null;
                const px = x(p.x);
                const py = y(p.y as number);
                const ly = labelYs[i];
                return (
                  <g key={`d${i}`} aria-hidden="true">
                    {Math.abs(ly - py) > 1.5 || right - px > 2 ? (
                      <polyline className="ch-leader" points={`${r1(px + 5)},${r1(py)} ${r1(right + 4)},${r1(ly)} ${r1(right + 8)},${r1(ly)}`} />
                    ) : null}
                    <text className="ch-t-label" x={r1(right + 11)} y={r1(ly)} dy="0.35em">
                      {truncate(s.name, labelW - 14, 12)}
                    </text>
                  </g>
                );
              })
            : null}
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

  const hasCI = series.some((s) => s.segments.some((seg) => seg.some((p) => isNum(p.lo) && isNum(p.hi))));
  const data = series.flatMap((s) =>
    s.segments.flatMap((seg) =>
      seg.map((p) => [
        s.name,
        xLabelOf(p.x),
        isNum(p.y) ? formatValue(p.y, fmt) : '—',
        ...(hasCI ? [formatInterval(p.lo, p.hi, fmt) ?? '—'] : []),
      ]),
    ),
  );

  return (
    <>
      <Legend items={series.map((s, i) => ({ label: s.name, color: colors[i], shape: 'line' as const }))} />
      <ChartPlot variants={variants} alt={fig.alt} render={render} />
      <DataTable
        label={`Data: ${fig.title ?? fig.alt}`}
        columns={[
          { label: 'Series' },
          { label: fig.x_label ?? 'x', num: true },
          { label: fig.y_label ?? 'Value', num: true },
          ...(hasCI ? [{ label: '95% CI', num: true }] : []),
        ]}
        rows={data}
      />
    </>
  );
}
