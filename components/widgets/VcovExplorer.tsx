import { getFigure } from '@/lib/registry';
import type { VcovMenuFigure } from '@/lib/types';
import { VcovExplorerClient } from './VcovExplorer.client';

/**
 * Lab 6: one coefficient, several `vcov` arguments. `id` names a figure of
 * type "vcov-menu" (CONTRACT section 9), for example "ch6lab.vcov_menu".
 */
export function VcovExplorer({ id }: { id: string }) {
  const data = getFigure<VcovMenuFigure>(id);
  if (data.type !== 'vcov-menu') {
    throw new Error(`VcovExplorer: figure "${id}" has type "${data.type}", expected "vcov-menu"`);
  }
  if (!data.options?.length) throw new Error(`VcovExplorer: figure "${id}" has no options`);
  return <VcovExplorerClient data={data} />;
}
