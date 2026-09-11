'use client';

import { useEffect, useRef, useState, type MouseEvent, type ReactNode } from 'react';
import { usePathname } from 'next/navigation';
import { CloseIcon, MenuIcon } from './icons';
import { OnThisPage } from './OnThisPage';

/**
 * Below lg the sidebar becomes this drawer: a native modal <dialog>, so focus
 * is trapped, Escape closes it, and the page behind is inert without extra
 * code. The contents list arrives as server-rendered children.
 */
export function MobileNav({ children, showSections = false }: { children: ReactNode; showSections?: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const pathname = usePathname();

  // A link to another page closes the drawer.
  useEffect(() => {
    ref.current?.close();
  }, [pathname]);

  const onClick = (e: MouseEvent<HTMLDialogElement>) => {
    const dialog = ref.current;
    if (!dialog) return;
    // Clicks on the backdrop land on the dialog itself, outside its box.
    const r = dialog.getBoundingClientRect();
    const outside = e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
    // Same-page links (the section list) don't change the pathname.
    const onLink = (e.target as HTMLElement).closest('a');
    if (outside || onLink) dialog.close();
  };

  return (
    <>
      <button
        type="button"
        className="bk-iconbtn bk-menu-btn"
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => {
          ref.current?.showModal();
          setOpen(true);
        }}
      >
        <MenuIcon />
        <span>Contents</span>
      </button>
      <dialog ref={ref} className="bk-drawer" aria-label="Contents" onClose={() => setOpen(false)} onClick={onClick}>
        <div className="bk-drawer-head">
          <span>Contents</span>
          <button type="button" className="bk-iconbtn" aria-label="Close contents" onClick={() => ref.current?.close()}>
            <CloseIcon />
          </button>
        </div>
        <div className="bk-drawer-body">
          {open && showSections ? <OnThisPage variant="drawer" /> : null}
          {children}
        </div>
      </dialog>
    </>
  );
}
