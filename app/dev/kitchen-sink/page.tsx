import type { Metadata } from 'next';
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

export default function KitchenSink() {
  return (
    <BookShell entry={entry} part={null} prev={null} next={null} kicker="Development · component kitchen sink" inToc={false}>
      <Article />
    </BookShell>
  );
}
