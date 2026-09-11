import { scaleLinear } from 'd3-scale';
import { formatChange, formatValue } from '@/lib/format';
import type { SlopeFigure } from '@/lib/types';
import {
  ChartPlot, DataTable, Legend, edgeAnchor, isNum, r1, roleColor, roleLegend, spreadLabels, textWidth, truncate,
  type Variant,
} from './common';

/**
 * Two columns, one line per row, read by slope (for example unweighted ->
 * weighted). Values label both ends directly, so there is no y axis; end
 * labels are pushed apart where rows converge.
 */
export function SlopeChart({ fig, variants }: { fig: SlopeFigure; variants: Variant[] }) {
  const fmt = fig.format;
  const rows = fig.rows;
  const vals = rows.flatMap((row) => [row.left, row.right]).filter(isNum);
  let lo = vals.length ? Math.min(...vals) : 0;
  let hi = vals.length ? Math.max(...vals) : 1;
  if (lo === hi) {
    lo -= 1;
    hi += 1;
  }
  const pad = (hi - lo) * 0.04;

  const tip = (label: string, left: number, right: number) =>
    `${label}: ${fig.left_label} ${formatValue(left, fmt)}, ${fig.right_label} ${formatValue(right, fmt)} (change ${formatChange(right - left, fmt)})`;

  const render = (variant: Variant, W: number) => {
    const sm = variant === 'sm';
    const leftText = rows.map((row) => (sm ? formatValue(row.left, fmt) : `${row.label}  ${formatValue(row.left, fmt)}`));
    const rightText = rows.map((row) => `${formatValue(row.right, fmt)}  ${row.label}`);
    const sideMax = W * (sm ? 0.46 : 0.34);
    const lw = Math.min(Math.max(30, ...leftText.map((t) => textWidth(t, 12))), sm ? W * 0.2 : sideMax);
    const rw = Math.min(Math.max(30, ...rightText.map((t) => textWidth(t, 12))), sideMax);
    const xL = lw + 14;
    const xR = W - rw - 14;
    const top = 34;
    const plotH = Math.min(640, Math.max(sm ? 180 : 220, rows.length * 24));
    const bottom = top + plotH;
    const y = scaleLinear().domain([lo - pad, hi + pad]).range([bottom, top]);
    const leftY = spreadLabels(rows.map((row) => y(row.left)), 15, [top, bottom]);
    const rightY = spreadLabels(rows.map((row) => y(row.right)), 15, [top, bottom]);
    return {
      height: bottom + 14,
      body: (
        <>
          <text className="ch-t-head" x={r1(xL)} y={16} textAnchor={edgeAnchor(xL, fig.left_label.toUpperCase(), W)}>
            {fig.left_label}
          </text>
          <text className="ch-t-head" x={r1(xR)} y={16} textAnchor={edgeAnchor(xR, fig.right_label.toUpperCase(), W)}>
            {fig.right_label}
          </text>
          <line className="ch-axis" x1={r1(xL)} x2={r1(xL)} y1={top - 8} y2={bottom} />
          <line className="ch-axis" x1={r1(xR)} x2={r1(xR)} y1={top - 8} y2={bottom} />
          {rows.map((row, i) => {
            const color = roleColor(row.role);
            const strong = row.role === 'highlight';
            return (
              <g key={i} className="ch-row">
                <title>{tip(row.label, row.left, row.right)}</title>
                <line
                  x1={r1(xL)}
                  y1={r1(y(row.left))}
                  x2={r1(xR)}
                  y2={r1(y(row.right))}
                  style={{ stroke: color }}
                  strokeWidth={strong ? 2.5 : 2}
                  strokeLinecap="round"
                />
                <circle cx={r1(xL)} cy={r1(y(row.left))} r={4.5} style={{ fill: color, stroke: 'var(--chart-surface)' }} strokeWidth={2} />
                <circle cx={r1(xR)} cy={r1(y(row.right))} r={4.5} style={{ fill: color, stroke: 'var(--chart-surface)' }} strokeWidth={2} />
                <text
                  className={strong ? 'ch-t-label ch-t-strong' : 'ch-t-label'}
                  x={r1(xL - 10)}
                  y={r1(leftY[i])}
                  dy="0.35em"
                  textAnchor="end"
                >
                  {truncate(leftText[i], lw, 12)}
                </text>
                <text className={strong ? 'ch-t-label ch-t-strong' : 'ch-t-label'} x={r1(xR + 10)} y={r1(rightY[i])} dy="0.35em">
                  {truncate(rightText[i], rw, 12)}
                </text>
              </g>
            );
          })}
        </>
      ),
    };
  };

  return (
    <>
      <Legend items={roleLegend(rows.map((row) => row.role), 'line')} />
      <ChartPlot variants={variants} alt={fig.alt} render={render} />
      <DataTable
        label={`Data: ${fig.title ?? fig.alt}`}
        columns={[{ label: 'Row' }, { label: fig.left_label, num: true }, { label: fig.right_label, num: true }, { label: 'Change', num: true }]}
        rows={rows.map((row) => [
          row.label,
          formatValue(row.left, fmt),
          formatValue(row.right, fmt),
          formatChange(row.right - row.left, fmt),
        ])}
      />
    </>
  );
}
