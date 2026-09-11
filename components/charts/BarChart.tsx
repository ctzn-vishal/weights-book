import { scaleLinear } from 'd3-scale';
import { formatInterval, formatValue, tickFormatter } from '@/lib/format';
import type { BarFigure, BarRow } from '@/lib/types';
import {
  ChartPlot, DataTable, Legend, TICKS, VGrid, XTicks, isNum, niceDomain, r1, roleColor, roleLegend,
  rowGeometry, textWidth, tickStep, truncate, type RowItem, type Variant,
} from './common';

/** A horizontal bar from x0 to x1 with a 4px rounded data end and a square baseline. */
function barPath(x0: number, x1: number, y: number, h: number): string {
  const len = Math.abs(x1 - x0);
  const rad = Math.min(4, len, h / 2);
  const dir = x1 >= x0 ? 1 : -1;
  const xe = x1 - dir * rad;
  return [
    `M${r1(x0)},${r1(y)}`,
    `H${r1(xe)}`,
    `Q${r1(x1)},${r1(y)} ${r1(x1)},${r1(y + rad)}`,
    `V${r1(y + h - rad)}`,
    `Q${r1(x1)},${r1(y + h)} ${r1(xe)},${r1(y + h)}`,
    `H${r1(x0)}`,
    'Z',
  ].join('');
}

/**
 * Horizontal bars from a zero baseline (length encodes value, so the axis
 * always includes zero, even when the figure fixes a domain). Optional 95%
 * interval whiskers; values are labelled at the bar tips when there are few
 * enough bars to read them.
 */
export function BarChart({ fig, variants }: { fig: BarFigure; variants: Variant[] }) {
  const fmt = fig.format;
  const rows = fig.rows;
  const values: number[] = [];
  for (const row of rows) for (const v of [row.value, row.ci_low, row.ci_high]) if (isNum(v)) values.push(v);
  const fixed = fig.domain ? ([Math.min(0, fig.domain[0]), Math.max(0, fig.domain[1])] as [number, number]) : null;
  const domain = niceDomain(values, { includeZero: true, fixed });
  const items: RowItem<BarRow>[] = rows.map((row, index) => ({ kind: 'row', row, index }));
  const showValues = rows.length <= 16;
  const valueText = rows.map((row) => (isNum(row.value) ? formatValue(row.value, fmt) : ''));
  const valuePad = showValues ? Math.max(0, ...valueText.map((s) => textWidth(s, 11.5))) + 14 : 16;

  const tip = (row: BarRow) => {
    let s = `${row.label}: ${isNum(row.value) ? formatValue(row.value, fmt) : 'suppressed'}`;
    const ci = formatInterval(row.ci_low, row.ci_high, fmt);
    if (ci) s += ` (95% CI ${ci})`;
    return s;
  };

  const render = (variant: Variant, W: number) => {
    const g = rowGeometry(items, variant, W, {
      labels: rows.map((row) => row.label),
      top: 6,
      rightPad: valuePad,
      xLabel: Boolean(fig.x_label),
    });
    const x = scaleLinear().domain(domain).range([g.plotLeft, g.plotRight]);
    const clampX = (v: number) => Math.max(g.plotLeft, Math.min(g.plotRight, x(v)));
    const ticks = x.ticks(TICKS[variant]);
    const tf = tickFormatter(fmt, tickStep(ticks));
    const x0 = x(0);
    const barH = g.stacked ? 14 : 16;
    return {
      height: g.height,
      body: (
        <>
          <VGrid x={x} ticks={ticks} top={g.top} bottom={g.plotBottom} />
          {items.map((it, i) => {
            if (it.kind !== 'row') return null;
            const row = it.row;
            const p = g.positions[i];
            const color = roleColor(row.role);
            const hasCI = isNum(row.ci_low) && isNum(row.ci_high);
            const v = isNum(row.value) ? row.value : null;
            const tipEnd = Math.max(v !== null ? clampX(v) : x0, hasCI ? clampX(row.ci_high as number) : -Infinity);
            const tipStart = Math.min(v !== null ? clampX(v) : x0, hasCI ? clampX(row.ci_low as number) : Infinity);
            // A negative bar's value sits left of its tip when there is room,
            // otherwise right of the whisker, never in the label gutter.
            const leftRoom = tipStart - g.plotLeft;
            const negative = v !== null && v < 0 && leftRoom >= textWidth(valueText[it.index], 11.5) + 10;
            return (
              <g key={i} className="ch-row">
                <title>{tip(row)}</title>
                <rect className="ch-rowbg" x={0} y={r1(p.y0)} width={W} height={p.h} />
                <text
                  className={`ch-t-label${row.role === 'highlight' ? ' ch-t-strong' : ''}${g.stacked ? ' ch-halo' : ''}`}
                  x={g.stacked ? 0 : r1(g.labelX)}
                  y={r1(p.labelY)}
                  dy="0.35em"
                  textAnchor={g.stacked ? 'start' : 'end'}
                >
                  {truncate(row.label, g.labelMax, 12)}
                </text>
                {v !== null ? <path d={barPath(x0, clampX(v), p.cy - barH / 2, barH)} style={{ fill: color }} /> : null}
                {hasCI ? (
                  <g style={{ stroke: 'var(--chart-annotation)' }} strokeWidth={1.25} opacity={0.75}>
                    <line x1={r1(clampX(row.ci_low as number))} x2={r1(clampX(row.ci_high as number))} y1={r1(p.cy)} y2={r1(p.cy)} />
                    <line x1={r1(clampX(row.ci_low as number))} x2={r1(clampX(row.ci_low as number))} y1={r1(p.cy - 4)} y2={r1(p.cy + 4)} />
                    <line x1={r1(clampX(row.ci_high as number))} x2={r1(clampX(row.ci_high as number))} y1={r1(p.cy - 4)} y2={r1(p.cy + 4)} />
                  </g>
                ) : null}
                {showValues && v !== null ? (
                  <text
                    className="ch-t-value"
                    x={r1(negative ? tipStart - 6 : tipEnd + 6)}
                    y={r1(p.cy)}
                    dy="0.35em"
                    textAnchor={negative ? 'end' : 'start'}
                  >
                    {valueText[it.index]}
                  </text>
                ) : null}
                {v === null ? (
                  <text className="ch-t-tick" x={r1(x0 + 4)} y={r1(p.cy)} dy="0.35em">
                    suppressed
                  </text>
                ) : null}
              </g>
            );
          })}
          <line className="ch-zero" x1={r1(x0)} x2={r1(x0)} y1={g.top} y2={r1(g.plotBottom)} />
          <XTicks x={x} ticks={ticks} y={g.tickY} format={tf} W={W} />
          {fig.x_label ? (
            <text className="ch-t-axis" x={r1((g.plotLeft + g.plotRight) / 2)} y={r1(g.axisLabelY)} textAnchor="middle">
              {fig.x_label}
            </text>
          ) : null}
        </>
      ),
    };
  };

  const hasCI = rows.some((row) => isNum(row.ci_low) && isNum(row.ci_high));
  return (
    <>
      <Legend items={roleLegend(rows.map((row) => row.role), 'bar')} />
      <ChartPlot variants={variants} alt={fig.alt} render={render} />
      <DataTable
        label={`Data: ${fig.title ?? fig.alt}`}
        columns={[{ label: 'Category' }, { label: 'Value', num: true }, ...(hasCI ? [{ label: '95% CI', num: true }] : [])]}
        rows={rows.map((row, i) => [
          row.label,
          valueText[i] || 'suppressed',
          ...(hasCI ? [formatInterval(row.ci_low, row.ci_high, fmt) ?? '—'] : []),
        ])}
      />
    </>
  );
}
