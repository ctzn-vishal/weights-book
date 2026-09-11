'use client';

import { useEffect, useState } from 'react';

interface Heading {
  id: string;
  text: string;
  level: 2 | 3;
}

/** Offset below the viewport top at which a heading counts as "current". */
const ACTIVE_LINE = 120;

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
 * The article DOM is the external source here: headings are read in an
 * animation frame after mount, and the active one follows scroll.
 */
export function OnThisPage({ variant = 'rail' }: { variant?: 'rail' | 'nested' | 'drawer' }) {
  const [items, setItems] = useState<Heading[]>([]);
  const [active, setActive] = useState('');

  useEffect(() => {
    const tags = variant === 'nested' ? ['h2'] : ['h2', 'h3'];
    const selector = tags.map((t) => `[data-article-body] > ${t}[id]`).join(', ');
    let nodes: HTMLElement[] = [];
    let frame = 0;

    const update = () => {
      frame = 0;
      let current = '';
      for (const n of nodes) {
        if (n.getBoundingClientRect().top <= ACTIVE_LINE) current = n.id;
        else break;
      }
      setActive(current);
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(update);
    };

    const init = requestAnimationFrame(() => {
      nodes = Array.from(document.querySelectorAll<HTMLElement>(selector)).filter((n) => n.textContent?.trim());
      setItems(nodes.map((n) => ({ id: n.id, text: n.textContent!.trim(), level: n.tagName === 'H3' ? 3 : 2 })));
      update();
    });
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll);
    return () => {
      cancelAnimationFrame(init);
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener('scroll', onScroll);
      window.removeEventListener('resize', onScroll);
    };
  }, [variant]);

  if (items.length < 2) return null;

  return (
    <nav className={variant === 'nested' ? 'bk-otp is-nested' : 'bk-otp'} aria-label="On this page">
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
