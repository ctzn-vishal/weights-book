import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { BookShell } from '@/components/book/BookShell';
import type { TocEntry } from '@/lib/toc';
import Article from './article.mdx';

/** Not a TOC entry: a development page that renders every component against fixture data. */
const entry: TocEntry = {
  slug: 'dev/kitchen-sink',
  key: 'dev',
  number: 'K',
  title: 'Kitchen Sink',
  dek: 'Every component in the book, rendered against fixture data. Not part of the book.',
  credential: 'Fixture data · not survey estimates',
  status: 'draft',
};

export const metadata: Metadata = {
  title: 'Kitchen sink',
  description: entry.dek,
  robots: { index: false, follow: false },
};

/**
 * Development page, not part of the book. A 404 in Vercel production builds (VERCEL_ENV=production,
 * the deployment vishalsingh.org/weights serves) and wherever HIDE_DEV_ROUTES=true is set at build
 * time; local dev and preview deployments keep it.
 */
export default function KitchenSink() {
  if (process.env.HIDE_DEV_ROUTES === 'true' || process.env.VERCEL_ENV === 'production') notFound();
  return (
    <BookShell entry={entry} part={null} prev={null} next={null} kicker="Development · component kitchen sink" inToc={false}>
      <Article />
    </BookShell>
  );
}
