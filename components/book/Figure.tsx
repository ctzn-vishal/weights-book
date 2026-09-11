import { Children, cloneElement, isValidElement, type ReactNode } from 'react';
import type { FrameWidth } from '@/components/charts/common';
import { getFigure } from '@/lib/registry';
import { Chart, type ChartProps } from './Chart';

export type FigureWidth = FrameWidth;

export interface FigureProps {
  /** "1.2": prints as "Figure 1.2." and anchors the figure at #fig-1-2. */
  n: string | number;
  /** The finding the figure shows, not its subject. */
  caption: ReactNode;
  /** body (the reading column), wide (into the sidenote margin), full (the whole content area). */
  width?: FigureWidth;
  /** Source line; defaults to the chart artifact's `source`. */
  source?: string;
  children?: ReactNode;
}

const WIDTHS: FigureWidth[] = ['body', 'wide', 'full'];

/**
 * Numbered figure frame. A <Chart> child is drawn for the frame's width, and
 * its artifact's note and source move under the caption, so a figure reads:
 * chart title, the chart, "Show data", then "Figure n." and the finding.
 */
export function Figure({ n, caption, width = 'body', source, children }: FigureProps) {
  if (!WIDTHS.includes(width)) {
    throw new Error(`<Figure n="${n}" width="${width}">: width must be one of ${WIDTHS.join(', ')}.`);
  }
  const meta: { note?: string; source?: string } = {};
  const content = Children.map(children, (child) => {
    if (isValidElement<ChartProps>(child) && child.type === Chart) {
      const fig = getFigure(child.props.id);
      meta.note = fig.note;
      meta.source = fig.source;
      return cloneElement(child, { frameWidth: width, inFigure: true });
    }
    return child;
  });
  const shownSource = source ?? meta.source;
  const anchor = `fig-${String(n).replace(/[^A-Za-z0-9]+/g, '-')}`;
  return (
    <figure className={`bk-figure fig-${width}`} id={anchor}>
      {content}
      <figcaption className="bk-figcaption">
        <span className="bk-fignum">Figure {n}.</span>
        {caption}
        {meta.note ? <span className="bk-figmeta">Note: {meta.note}</span> : null}
        {shownSource ? <span className="bk-figmeta">Source: {shownSource}</span> : null}
      </figcaption>
    </figure>
  );
}
