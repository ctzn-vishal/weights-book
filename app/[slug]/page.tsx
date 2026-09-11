import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { BookShell } from '@/components/book/BookShell';
import { Callout } from '@/components/book/Callout';
import { chapterMetadata } from '@/lib/chapter-page';
import { hasChapterPage } from '@/lib/pages';
import { allEntries, findEntry } from '@/lib/toc';

/**
 * Placeholder for TOC entries whose directory has not been exported yet, so
 * the deployed draft never has a broken link. Only those slugs are generated
 * (dynamicParams = false: anything else is a 404). When the integrator adds
 * app/<slug>/page.tsx, the next registry run drops the slug from this list
 * and the static route serves it (static segments also win over [slug]).
 */
export const dynamicParams = false;

export function generateStaticParams() {
  return allEntries.filter((e) => !hasChapterPage(e.slug)).map((e) => ({ slug: e.slug }));
}

type Params = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Params): Promise<Metadata> {
  const { slug } = await params;
  const loc = findEntry(slug);
  return loc ? chapterMetadata(loc.entry) : {};
}

export default async function Placeholder({ params }: Params) {
  const { slug } = await params;
  const loc = findEntry(slug);
  if (!loc) notFound();
  return (
    <BookShell entry={loc.entry} part={loc.part} prev={loc.prev} next={loc.next}>
      <Callout kind="draft" title="This chapter is being drafted">
        <p>
          Its data, figures, and prose appear here once the draft is exported. The neighbouring chapters are linked
          below, and the full contents are in the sidebar.
        </p>
      </Callout>
    </BookShell>
  );
}
