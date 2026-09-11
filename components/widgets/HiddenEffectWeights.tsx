import { getFigure } from '@/lib/registry';
import type { CellsFigure } from '@/lib/types';
import { HiddenEffectWeightsClient } from './HiddenEffectWeights.client';

/**
 * Chapter 5: hidden effect weights. Part 1 (always) is the two-group
 * variance-weighting machine. Part 2 appears when `cellsId` names a figure of
 * type "cells" (CONTRACT section 9): real cells, their population shares, and
 * their implicit regression weights.
 */
export function HiddenEffectWeights({ cellsId }: { cellsId?: string }) {
  const cells = cellsId ? getFigure<CellsFigure>(cellsId) : undefined;
  if (cells && cells.type !== 'cells') {
    throw new Error(`HiddenEffectWeights: figure "${cellsId}" has type "${cells.type}", expected "cells"`);
  }
  return <HiddenEffectWeightsClient cells={cells} />;
}
