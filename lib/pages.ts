import generated from './generated/pages.json';

/**
 * Chapter directories that already have a page file, as found by
 * scripts/gen-registry.mjs at the start of every dev, build, and typecheck.
 * Every other TOC entry is served by the placeholder route (app/[slug]).
 */
const pages = new Set<string>((generated as { pages: string[] }).pages);

export function hasChapterPage(slug: string): boolean {
  return pages.has(slug);
}
