import type { ReactNode } from 'react';
import { getFact } from '@/lib/registry';
import { FactPopover, usePopId } from './Fact';

/**
 * One number set large, with a one-line label. The value is the fact's
 * `display`; the interval, when the fact has one, prints underneath (a
 * headline number in this book always carries its uncertainty). The number
 * keeps the Fact popover. Use sparingly: one or two per chapter.
 */
export function KeyNumber({ id, label }: { id: string; label: ReactNode }) {
  const fact = getFact(id);
  const popId = usePopId('keynum');
  return (
    <div className="keynum">
      <p className="keynum-value">
        <span className="fact" data-fact={id}>
          <span className="fact-num" tabIndex={0} aria-describedby={popId}>
            {fact.display}
          </span>
          <FactPopover fact={fact} id={popId} />
        </span>
      </p>
      <p className="keynum-label">{label}</p>
      {fact.ci_display ? <p className="keynum-ci">95% CI {fact.ci_display}</p> : null}
    </div>
  );
}
