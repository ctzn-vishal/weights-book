import type { MDXComponents } from 'mdx/types';
import { Callout } from '@/components/book/Callout';
import { Chart } from '@/components/book/Chart';
import { Cite } from '@/components/book/Cite';
import { Changed, Closing, Learned, NotEstablished } from '@/components/book/Closing';
import { Details } from '@/components/book/Details';
import { Fact } from '@/components/book/Fact';
import { Figure } from '@/components/book/Figure';
import { KeyNumber } from '@/components/book/KeyNumber';
import { Ledger } from '@/components/book/Ledger';
import { MdxH2, MdxH3, MdxImage, MdxLink, MdxPre, MdxTable } from '@/components/book/MdxElements';
import { SideNote } from '@/components/book/SideNote';

/**
 * Global MDX components (docs/CONTRACT.md §8): usable in every chapter
 * without an import. Widgets are the exception and are imported explicitly.
 * Keep this list in step with GLOBAL_COMPONENTS in scripts/lib/book-contract.mjs
 * (scripts/verify-book.mjs checks it).
 */
const components: MDXComponents = {
  Fact,
  KeyNumber,
  Figure,
  Chart,
  Ledger,
  Callout,
  SideNote,
  Cite,
  Details,
  Closing,
  Learned,
  Changed,
  NotEstablished,
  a: MdxLink,
  h2: MdxH2,
  h3: MdxH3,
  img: MdxImage,
  table: MdxTable,
  pre: MdxPre,
};

export function useMDXComponents(): MDXComponents {
  return components;
}
