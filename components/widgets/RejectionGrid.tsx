import { getFigure } from '@/lib/registry';
import type { TableFigure } from '@/lib/types';
import { RejectionGridClient, type RejectionRow } from './RejectionGrid.client';

/**
 * Chapter 7: the simulation results as a sortable, filterable grid. `id` names a
 * figure of type "table" whose rows carry design, estimator, code, reject,
 * ratio, and verdict (built by ch07-cluster-choice/build.py).
 */
export function RejectionGrid({ id }: { id: string }) {
  const fig = getFigure<TableFigure>(id);
  if (fig.type !== 'table') throw new Error(`RejectionGrid: figure "${id}" has type "${fig.type}", expected "table"`);
  const rows = fig.rows as unknown as RejectionRow[];
  for (const k of ['design', 'estimator', 'code', 'reject', 'ratio', 'verdict'] as const) {
    if (!rows.every((r) => r[k] !== undefined)) throw new Error(`RejectionGrid: figure "${id}" rows need a "${k}" field`);
  }
  return <RejectionGridClient rows={rows} title={fig.title ?? 'The menu, scored'} subtitle={fig.subtitle} note={fig.note} source={fig.source} alt={fig.alt} />;
}
