'use client';

import { useEffect } from 'react';

const EDGE = 8;

/**
 * The Fact popover works with CSS alone (hover and focus show it). This
 * island adds three refinements, once per page, by event delegation:
 *   - nudges a popover sideways so it never leaves the viewport,
 *   - flips it above the number when there is no room below,
 *   - Escape dismisses it without moving the pointer or focus (WCAG 1.4.13).
 * On narrow screens the popover is a fixed bottom sheet and needs none of this.
 */
export function FactPositioner() {
  useEffect(() => {
    const narrow = window.matchMedia('(max-width: 40rem)');

    const place = (fact: HTMLElement) => {
      const pop = fact.querySelector<HTMLElement>(':scope > .fact-pop');
      if (!pop) return;
      pop.style.setProperty('--fact-shift', '0px');
      pop.classList.remove('is-above');
      if (narrow.matches) return;
      const r = pop.getBoundingClientRect();
      let shift = 0;
      if (r.left < EDGE) shift = EDGE - r.left;
      else if (r.right > window.innerWidth - EDGE) shift = window.innerWidth - EDGE - r.right;
      if (shift) pop.style.setProperty('--fact-shift', `${Math.round(shift)}px`);
      const anchor = fact.getBoundingClientRect();
      if (r.bottom > window.innerHeight - EDGE && anchor.top > r.height + EDGE + 56) pop.classList.add('is-above');
    };

    // Entering a fact from outside it (pointer or keyboard).
    const onEnter = (e: Event) => {
      const fact = (e.target as Element | null)?.closest?.('.fact');
      if (!(fact instanceof HTMLElement)) return;
      const from = (e as PointerEvent | FocusEvent).relatedTarget as Node | null;
      if (from && fact.contains(from)) return;
      fact.removeAttribute('data-dismissed');
      // The card is display:none until :hover or :focus-within applies; measure on the next frame.
      requestAnimationFrame(() => place(fact));
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return;
      document.querySelectorAll('.fact:hover, .fact:focus-within').forEach((f) => f.setAttribute('data-dismissed', ''));
    };

    document.addEventListener('pointerover', onEnter);
    document.addEventListener('focusin', onEnter);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerover', onEnter);
      document.removeEventListener('focusin', onEnter);
      document.removeEventListener('keydown', onKey);
    };
  }, []);

  return null;
}
