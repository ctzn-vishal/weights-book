import { getFigure } from '@/lib/registry';
import type { ReplicatesFigure } from '@/lib/types';
import { ReplicateRankingClient } from './ReplicateRanking.client';

/**
 * Chapter 3 lab: point-estimate rankings versus ranking uncertainty. `id` names
 * a figure of type "replicates" (CONTRACT section 9). Units may carry an
 * optional `naive_se` (an SE that ignores the design) for comparison.
 */
export function ReplicateRanking({ id }: { id: string }) {
  const data = getFigure<ReplicatesFigure>(id);
  if (data.type !== 'replicates') {
    throw new Error(`ReplicateRanking: figure "${id}" has type "${data.type}", expected "replicates"`);
  }
  for (const u of data.units) {
    if (u.reps.length !== data.n_reps) {
      throw new Error(`ReplicateRanking: unit "${u.id}" in "${id}" has ${u.reps.length} replicates, expected ${data.n_reps}`);
    }
  }
  return <ReplicateRankingClient data={data} />;
}
