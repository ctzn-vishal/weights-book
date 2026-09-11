import type { ReactNode } from 'react';
import Link from 'next/link';
import { REPO_URL } from '@/lib/site';
import { book } from '@/lib/toc';
import { GitHubIcon } from './icons';
import { ThemeToggle } from './ThemeToggle';

/** On every page (root layout). Wording fixed by the draft brief. */
export function DraftBanner() {
  return (
    <div className="bk-draft" role="note">
      <strong>Draft:</strong> numbers and prose are under review
    </div>
  );
}

/**
 * The slim sticky bar: book title (home), theme toggle, source link. Pages
 * with a contents drawer pass its trigger as `menu` (shown below lg).
 */
export function TopBar({ menu }: { menu?: ReactNode }) {
  return (
    <header className="bk-topbar">
      <div className="bk-topbar-inner">
        {menu}
        <Link href="/" className="bk-brand">
          {book.title}
        </Link>
        <div className="bk-topbar-actions">
          <ThemeToggle />
          <a className="bk-iconbtn" href={REPO_URL} aria-label="Source on GitHub" title="Source on GitHub" rel="noopener noreferrer">
            <GitHubIcon />
          </a>
        </div>
      </div>
    </header>
  );
}

/** On every page (root layout): one-line data credit, pointing to Appendix C. */
export function SiteFooter() {
  return (
    <footer className="bk-footer">
      <div className="bk-footer-inner">
        <p>
          Data: IPUMS (USA, CPS, Time Use, Health Surveys), NHANES, and BRFSS. Citations and terms of use are in{' '}
          <Link href="/appendix-c-reproducibility">Appendix C</Link>.
        </p>
        <p>
          {book.title} · {book.author} · draft
        </p>
      </div>
    </footer>
  );
}
