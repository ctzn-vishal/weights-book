import { getFigure } from '@/lib/registry';
import type { EstimandSetFigure } from '@/lib/types';
import { EstimandSwitcherClient } from './EstimandSwitcher.client';

/**
 * Chapter 1: one indicator, several estimands. `id` names a figure of type
 * "estimand-set" (CONTRACT section 9), for example "ch1.burden_estimands".
 */
export function EstimandSwitcher({ id }: { id: string }) {
  const data = getFigure<EstimandSetFigure>(id);
  if (data.type !== 'estimand-set') {
    throw new Error(`EstimandSwitcher: figure "${id}" has type "${data.type}", expected "estimand-set"`);
  }
  if (!data.options?.length) throw new Error(`EstimandSwitcher: figure "${id}" has no options`);
  return <EstimandSwitcherClient data={data} />;
}
