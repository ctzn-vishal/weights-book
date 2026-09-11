import { scaleLinear } from 'd3-scale';
import { formatCount, formatInterval, formatValue, tickFormatter } from '@/lib/format';
import type { DotFigure, DotRow } from '@/lib/types';
import {
  ChartPlot, DataTable, Legend, TICKS, VGrid, XTicks, edgeAnchor, groupItems, isNum, niceDomain, r1,
  roleColor, roleLegend, rowGeometry, tickStep, truncate, type DataColumn, type Variant,
} from './common';

/**
 * Dot plot / forest plot: one row per estimate, a dot with an optional 95%
 * interval whisker, an optional reference rule, optional group sections.
 * Row order is the figure's; a row without an interval is a bare dot
 * ("not reported"), never a zero-width whisker.
 */
export function DotChart({ fig, variants }: { fig: DotFigure; variants: Variant[] }) {
  const fmt = fig.format;
  const rows = fig.rows;
  const values: number[] = [];
  for (const row of rows) for (const v of [row.estimate, row.ci_low, row.ci_high]) if (isNum(v)) values.push(v);
  if (fig.reference && isNum(fig.reference.value)) values.push(fig.reference.value);
  const domain = niceDomain(values, { fixed: fig.domain ?? null });
  const items = groupItems(rows);

  const tip = (row: DotRow) => {
    let s = `${row.label}: ${isNum(row.estimate) ? formatValue(row.estimate, fmt) : 'suppressed'}`;
    const ci = formatInterval(row.ci_low, row.ci_high, fmt);
    if (ci) s += ` (95% CI ${ci})`;
    if (isNum(row.n)) s += `, n = ${formatCount(row.n)}`;
    return s;
  };

  const render = (variant: Variant, W: number) => {
    const g = rowGeometry(items, variant, W, {
      labels: rows.map((row) => row.label),
      top: fig.reference ? 26 : 6,
      rightPad: 16,
      xLabel: Boolean(fig.x_label),
    });
    const x = scaleLinear().domain(domain).range([g.plotLeft, g.plotRight]);
    const clampX = (v: number) => Math.max(g.plotLeft, Math.min(g.plotRight, x(v)));
    const ticks = x.ticks(TICKS[variant]);
    const tf = tickFormatter(fmt, tickStep(ticks));
    const showZero = !fig.reference && domain[0] < 0 && domain[1] > 0;
    const ref = fig.reference;
    return {
      height: g.height,
      body: (
        <>
          <VGrid x={x} ticks={ticks} top={g.top} bottom={g.plotBottom} />
          <line className="ch-axis" x1={g.plotLeft} x2={g.plotRight} y1={r1(g.plotBottom)} y2={r1(g.plotBottom)} />
          {showZero ? <line className="ch-zero" x1={r1(x(0))} x2={r1(x(0))} y1={g.top} y2={r1(g.plotBottom)} /> : null}
          {ref ? (
            <g aria-hidden="true">
              <line className="ch-ref" x1={r1(clampX(ref.value))} x2={r1(clampX(ref.value))} y1={g.top - 6} y2={r1(g.plotBottom)} />
              <text className="ch-t-annot" x={r1(clampX(ref.value))} y={g.top - 11} textAnchor={edgeAnchor(clampX(ref.value), ref.label, W)}>
                {ref.label}
              </text>
            </g>
          ) : null}
          {items.map((it, i) => {
            const p = g.positions[i];
            if (it.kind === 'group') {
              return (
                <text key={`g${i}`} className={g.stacked ? 'ch-t-group ch-halo' : 'ch-t-group'} x={0} y={r1(p.labelY)} dy="0.35em">
                  {truncate(it.label.toUpperCase(), W - 8, 11.5)}
                </text>
              );
            }
            const row = it.row;
            const color = roleColor(row.role);
            const interval = isNum(row.ci_low) && isNum(row.ci_high);
            return (
              <g key={`r${i}`} className="ch-row">
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
                {interval ? (
                  <line
                    x1={r1(clampX(row.ci_low as number))}
                    x2={r1(clampX(row.ci_high as number))}
                    y1={r1(p.cy)}
                    y2={r1(p.cy)}
                    style={{ stroke: color }}
                    strokeWidth={2}
                    strokeLinecap="round"
                  />
                ) : null}
                {isNum(row.estimate) ? (
                  <circle
                    cx={r1(clampX(row.estimate))}
                    cy={r1(p.cy)}
                    r={4.5}
                    style={{ fill: color, stroke: 'var(--chart-surface)' }}
                    strokeWidth={2}
                  />
                ) : (
                  <text className="ch-t-tick" x={g.plotLeft} y={r1(p.cy)} dy="0.35em">
                    suppressed
                  </text>
                )}
              </g>
            );
          })}
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

  const hasGroup = rows.some((row) => row.group);
  const hasCI = rows.some((row) => isNum(row.ci_low) && isNum(row.ci_high));
  const hasN = rows.some((row) => isNum(row.n));
  const columns: DataColumn[] = [
    ...(hasGroup ? [{ label: 'Group' }] : []),
    { label: 'Estimate for' },
    { label: 'Estimate', num: true },
    ...(hasCI ? [{ label: '95% CI', num: true }] : []),
    ...(hasN ? [{ label: 'n', num: true }] : []),
  ];
  const data = rows.map((row) => [
    ...(hasGroup ? [row.group ?? ''] : []),
    row.label,
    isNum(row.estimate) ? formatValue(row.estimate, fmt) : 'suppressed',
    ...(hasCI ? [formatInterval(row.ci_low, row.ci_high, fmt) ?? '—'] : []),
    ...(hasN ? [isNum(row.n) ? formatCount(row.n) : '—'] : []),
  ]);

  return (
    <>
      <Legend items={roleLegend(rows.map((row) => row.role), 'dot')} />
      <ChartPlot variants={variants} alt={fig.alt} render={render} />
      <DataTable label={`Data: ${fig.title ?? fig.alt}`} columns={columns} rows={data} />
    </>
  );
}
