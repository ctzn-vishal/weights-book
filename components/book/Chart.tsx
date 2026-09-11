import { BarChart } from '@/components/charts/BarChart';
import { DotChart } from '@/components/charts/DotChart';
import { HistogramChart } from '@/components/charts/HistogramChart';
import { LineChart } from '@/components/charts/LineChart';
import { SlopeChart } from '@/components/charts/SlopeChart';
import { TableChart } from '@/components/charts/TableChart';
import { variantsFor, type FrameWidth } from '@/components/charts/common';
import { getFigure } from '@/lib/registry';

const WIDGET_FOR: Record<string, string> = {
  cells: 'HiddenEffectWeights cellsId',
  'estimand-set': 'EstimandSwitcher id',
  replicates: 'ReplicateRanking id',
  'vcov-menu': 'VcovExplorer id',
};

export interface ChartProps {
  /** Global figure id, "<key>.<figure file stem>". */
  id: string;
  /** Set by <Figure>: which width zone the chart is drawn for. */
  frameWidth?: FrameWidth;
  /** Set by <Figure>: the frame prints the note and source under the caption. */
  inFigure?: boolean;
}

/**
 * Renders a figure artifact by id as a server-side SVG (or HTML table) chart,
 * with its title and subtitle above, a "Show data" table below, and — when
 * not inside <Figure> — its note and source. Widget data (cells,
 * estimand-set, replicates) is rejected with the widget to use instead.
 */
export function Chart({ id, frameWidth = 'body', inFigure = false }: ChartProps) {
  const fig = getFigure(id);
  if (fig.type in WIDGET_FOR) {
    throw new Error(
      `<Chart id="${id}">: "${fig.type}" is widget data, not a chart. Render it with <${WIDGET_FOR[fig.type]}="${id}" /> (import from '@/components/widgets/...').`,
    );
  }
  const variants = variantsFor(frameWidth);
  let body;
  switch (fig.type) {
    case 'dot':
      body = <DotChart fig={fig} variants={variants} />;
      break;
    case 'bar':
      body = <BarChart fig={fig} variants={variants} />;
      break;
    case 'line':
      body = <LineChart fig={fig} variants={variants} />;
      break;
    case 'slope':
      body = <SlopeChart fig={fig} variants={variants} />;
      break;
    case 'table':
      body = <TableChart fig={fig} />;
      break;
    case 'histogram':
      body = <HistogramChart fig={fig} variants={variants} />;
      break;
    default:
      throw new Error(`<Chart id="${id}">: unknown figure type "${(fig as { type: string }).type}".`);
  }
  const foot = !inFigure && (fig.note || fig.source);
  return (
    <div className="ch" data-chart={id}>
      {fig.title || fig.subtitle ? (
        <div className="ch-head">
          {fig.title ? <p className="ch-title">{fig.title}</p> : null}
          {fig.subtitle ? <p className="ch-subtitle">{fig.subtitle}</p> : null}
        </div>
      ) : null}
      {body}
      {foot ? (
        <p className="ch-foot">
          {fig.note ? <span>Note: {fig.note}</span> : null}
          {fig.source ? <span>Source: {fig.source}</span> : null}
        </p>
      ) : null}
    </div>
  );
}
