'use client';

import { useEffect, useRef, useState } from 'react';

interface Heading {
  id: string;
  text: string;
  level: 2 | 3;
}

/** Offset below the viewport top at which a heading counts as "current". */
const ACTIVE_LINE = 120;

/**
 * Scroll the nearest scrolling ancestor (the sidebar, the rail, or the drawer)
 * so that `el` is comfortably in view. Only that container moves: unlike
 * scrollIntoView, the window is never scrolled, so revealing a contents entry
 * cannot yank the reader away from the paragraph they are on.
 */
export function revealInScrollParent(el: HTMLElement, position: 'nearest' | 'center' = 'nearest') {
  let box: HTMLElement | null = el.parentElement;
  while (box && !/(auto|scroll)/.test(getComputedStyle(box).overflowY)) box = box.parentElement;
  if (!box || box.clientHeight === 0 || box.scrollHeight <= box.clientHeight) return;
  const b = box.getBoundingClientRect();
  const r = el.getBoundingClientRect();
  const pad = 24;
  if (position === 'center') {
    box.scrollTop += r.top - b.top - (b.height - r.height) / 2;
  } else if (r.top < b.top + pad) {
    box.scrollTop -= b.top + pad - r.top;
  } else if (r.bottom > b.bottom - pad) {
    box.scrollTop += r.bottom - (b.bottom - pad);
  }
}

/**
 * Mounted inside the contents list: on arrival, scrolls the list so the
 * current chapter is visible (centred, so its neighbours show too). Renders
 * nothing.
 */
export function RevealCurrent() {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const nav = ref.current?.closest('nav');
    const current = nav?.querySelector<HTMLElement>('a[aria-current="page"]');
    if (current) revealInScrollParent(current, 'center');
  }, []);
  return <span ref={ref} hidden />;
}

/**
 * "On this page", built from the article's own h2/h3 (ids from rehype-slug).
 * Only headings that are direct children of the article body count, so
 * headings inside figures, callouts, or panels stay out. Renders nothing for
 * fewer than two headings.
 *
 *   rail    h2 + h3, the sticky right rail on wide screens
 *   nested  h2 only, under the current chapter in the sidebar
 *   drawer  h2 + h3, at the top of the mobile contents drawer
 *
 * The article DOM is the external source here: headings are read once after
 * mount. The current heading is the last one above the active line; it can
 * only change when a heading crosses that line, so an IntersectionObserver
 * whose root is the viewport inset by the line does the tracking, with a
 * throttled scroll listener as the fallback for the end of the page (where the
 * last heading may never reach the line) and for browsers without observers.
 */
export function OnThisPage({ variant = 'rail' }: { variant?: 'rail' | 'nested' | 'drawer' }) {
  const [items, setItems] = useState<Heading[]>([]);
  const [active, setActive] = useState('');
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const tags = variant === 'nested' ? ['h2'] : ['h2', 'h3'];
    const selector = tags.map((t) => `[data-article-body] > ${t}[id]`).join(', ');
    let teardown: (() => void) | undefined;

    // The read is deferred one tick (a timer, not an animation frame, so it also runs in a
    // background tab): the article is committed by then, and the state update happens in a callback.
    const timer = setTimeout(() => {
      const nodes = Array.from(document.querySelectorAll<HTMLElement>(selector)).filter((n) => n.textContent?.trim());
      setItems(nodes.map((n) => ({ id: n.id, text: n.textContent!.trim(), level: n.tagName === 'H3' ? 3 : 2 })));
      if (nodes.length < 2) return;

      let frame = 0;
      const update = () => {
        frame = 0;
        let current = '';
        for (const n of nodes) {
          if (n.getBoundingClientRect().top <= ACTIVE_LINE) current = n.id;
          else break;
        }
        // At the foot of the page the last section counts even if its heading sits below the line.
        const root = document.documentElement;
        if (window.innerHeight + window.scrollY >= root.scrollHeight - 2) current = nodes[nodes.length - 1].id;
        setActive(current);
      };
      const schedule = () => {
        if (!frame) frame = requestAnimationFrame(update);
      };
      update();

      const observer =
        typeof IntersectionObserver === 'function'
          ? new IntersectionObserver(schedule, { rootMargin: `-${ACTIVE_LINE}px 0px 0px 0px`, threshold: [0, 1] })
          : null;
      if (observer) for (const n of nodes) observer.observe(n);
      window.addEventListener('scroll', schedule, { passive: true });
      window.addEventListener('resize', schedule);
      teardown = () => {
        observer?.disconnect();
        if (frame) cancelAnimationFrame(frame);
        window.removeEventListener('scroll', schedule);
        window.removeEventListener('resize', schedule);
      };
    }, 0);

    return () => {
      clearTimeout(timer);
      teardown?.();
    };
  }, [variant]);

  // A long list scrolls inside its rail: keep the current entry in view as it moves.
  useEffect(() => {
    if (!active) return;
    const link = navRef.current?.querySelector<HTMLElement>('a[aria-current="location"]');
    if (link) revealInScrollParent(link);
  }, [active]);

  if (items.length < 2) return null;

  return (
    <nav ref={navRef} className={variant === 'nested' ? 'bk-otp is-nested' : 'bk-otp'} aria-label="On this page">
      {variant === 'nested' ? null : <p className="bk-otp-title">On this page</p>}
      <ol>
        {items.map((h) => (
          <li key={h.id} className={`lvl-${h.level}`}>
            <a
              href={`#${h.id}`}
              className={h.id === active ? 'is-active' : undefined}
              aria-current={h.id === active ? 'location' : undefined}
            >
              {h.text}
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
}
