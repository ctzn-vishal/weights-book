/**
 * The book manifest: every part, chapter, lab, and appendix in reading order.
 *
 * This file is the single source of truth for navigation, chapter headers,
 * page metadata, prev/next links, the cover's chapter cards, and the
 * placeholder routes (app/[slug]) for chapters whose directory has not been
 * exported yet. scripts/verify-book.mjs checks it against app/.
 *
 * Keep it dependency-free (types only): the verify script imports it under tsx.
 */

export type EntryStatus = 'draft' | 'review' | 'final';

export interface TocEntry {
  /** Route segment and app/ directory name, e.g. "ch01-estimands". */
  slug: string;
  /** Artifact namespace (manifest key), e.g. "ch1". */
  key: string;
  /** Display number: "0", "1", "Lab 3", "A". */
  number: string;
  title: string;
  /** One sentence under the title. */
  dek: string;
  /** The data behind the chapter, shown under the dek. */
  credential?: string;
  status: EntryStatus;
}

export interface TocPart {
  /** "Start here", "Part I · Describing populations", "Appendices". */
  title: string;
  entries: TocEntry[];
}

export interface BookManifest {
  title: string;
  subtitle: string;
  author: string;
  parts: TocPart[];
}

export const book: BookManifest = {
  title: 'Weights, Design, and Estimands',
  subtitle: 'A Field Guide for Applied Researchers',
  author: 'Vishal Singh',
  parts: [
    {
      title: 'Start here',
      entries: [
        {
          slug: 'ch00-start-here',
          key: 'ch0',
          number: '0',
          title: 'Target, Contribution, Uncertainty',
          dek: 'Every weighted number answers three questions: who it describes, how each observation counts, and what could have come out differently.',
          credential: 'Synthetic population · interactive',
          status: 'draft',
        },
      ],
    },
    {
      title: 'Part I · Describing populations',
      entries: [
        {
          slug: 'ch01-estimands',
          key: 'ch1',
          number: '1',
          title: 'What Are We Trying to Estimate?',
          dek: 'Six defensible answers to how much Americans work, and why they are different estimands rather than competing estimators.',
          credential: 'ATUS · CPS Voting · CPS Food Security · CPS ASEC',
          status: 'draft',
        },
        {
          slug: 'ch02-weights',
          key: 'ch2',
          number: '2',
          title: 'Where Survey Weights Come From',
          dek: 'How one phone-survey respondent comes to stand for thousands of adults: design weights, adjustment, raking, and trimming.',
          credential: 'BRFSS 2024 · ATUS · effective sample sizes',
          status: 'draft',
        },
        {
          slug: 'ch03-design',
          key: 'ch3',
          number: '3',
          title: 'Point Estimates and Design-Based Uncertainty',
          dek: 'Nearly half of adults have hypertension. How many know it, treat it, and control it, and how sure can we be?',
          credential: 'NHANES 2021–2023 · NHIS · BRFSS · Taylor linearization',
          status: 'draft',
        },
        {
          slug: 'ch03-lab-replicates',
          key: 'ch3lab',
          number: 'Lab 3',
          title: 'Lab: Which State Differences Are Real?',
          dek: 'A league table of state estimates looks more definitive than the data allow. Replicate weights show by how much.',
          credential: 'ACS 2024 · 80 SDR replicate weights',
          status: 'draft',
        },
      ],
    },
    {
      title: 'Part II · Regression and causal questions',
      entries: [
        {
          slug: 'ch04-regression',
          key: 'ch4',
          number: '4',
          title: 'What Are We Weighting For?',
          dek: 'Weighted and unweighted wage regressions agree here. That agreement is informative, and it is not the end of the story.',
          credential: 'ACS 2024 · OLS vs WLS · replicate SEs',
          status: 'draft',
        },
        {
          slug: 'ch05-hidden-weights',
          key: 'ch5',
          number: '5',
          title: 'Hidden Weights Under Heterogeneous Effects',
          dek: 'An adjusted regression averages heterogeneous contrasts with weights nobody chose. Here is how to see them.',
          credential: 'ACS 2024 · implicit regression weights',
          status: 'draft',
        },
        {
          slug: 'ch06-clustering',
          key: 'ch6',
          number: '6',
          title: 'Sampling Design, Assignment Design, and Clustering',
          dek: 'Millions of survey records, dozens of policy shocks: clustering as a question about sampling and assignment.',
          credential: 'ACS 2011–2019 · Medicaid expansion · few-cluster inference',
          status: 'draft',
        },
      ],
    },
    {
      title: 'Part III · Field guide',
      entries: [
        {
          slug: 'ch07-field-guide',
          key: 'ch7',
          number: '7',
          title: 'Field Guide: Six Surveys, Declared',
          dek: 'Design facts, declaration code, and known traps for six public surveys, generated from their design manifests.',
          credential: 'ACS · CPS ASEC · NHIS · NHANES · BRFSS · ATUS',
          status: 'draft',
        },
      ],
    },
    {
      title: 'Appendices',
      entries: [
        {
          slug: 'appendix-a-notation',
          key: 'appA',
          number: 'A',
          title: 'Notation and Crosswalk',
          dek: 'One notation for weights, and a dictionary between the survey, econometrics, and causal-inference literatures.',
          status: 'draft',
        },
        {
          slug: 'appendix-b-derivations',
          key: 'appB',
          number: 'B',
          title: 'Scoped Derivations',
          dek: 'Linearization, the Moulton factor, implicit regression weights, and four effective sample sizes, each with its conditions.',
          status: 'draft',
        },
        {
          slug: 'appendix-c-reproducibility',
          key: 'appC',
          number: 'C',
          title: 'Data, Code, and Reproducibility',
          dek: 'Releases, citations, validation layers, and how to rebuild every number.',
          status: 'draft',
        },
      ],
    },
  ],
};

// ------------------------------------------------------------------ helpers

/** Every entry, in reading order. */
export const allEntries: readonly TocEntry[] = book.parts.flatMap((p) => p.entries);

export type EntryKind = 'chapter' | 'lab' | 'appendix';

export function entryKind(entry: TocEntry): EntryKind {
  if (entry.key.startsWith('app')) return 'appendix';
  if (/^Lab\b/.test(entry.number)) return 'lab';
  return 'chapter';
}

/** "Chapter 1", "Lab 3", "Appendix A". */
export function entryLabel(entry: TocEntry): string {
  switch (entryKind(entry)) {
    case 'appendix':
      return `Appendix ${entry.number}`;
    case 'lab':
      return entry.number;
    default:
      return `Chapter ${entry.number}`;
  }
}

/** Splits "Part I · Describing populations" into its label and name. */
export function splitPartTitle(title: string): { label: string | null; name: string } {
  const m = /^(Part [IVXLC]+)\s*·\s*(.+)$/.exec(title);
  return m ? { label: m[1], name: m[2] } : { label: null, name: title };
}

/** The chapter header's kicker: "Part I · Chapter 1", "Start here · Chapter 0", "Appendix A". */
export function kickerFor(entry: TocEntry, part: TocPart | null): string {
  if (entryKind(entry) === 'appendix' || !part) return entryLabel(entry);
  const { label, name } = splitPartTitle(part.title);
  return `${label ?? name} · ${entryLabel(entry)}`;
}

export function entryHref(entry: TocEntry): string {
  return `/${entry.slug}`;
}

export interface EntryLocation {
  entry: TocEntry;
  part: TocPart;
  index: number;
  prev: TocEntry | null;
  next: TocEntry | null;
}

export function findEntry(slug: string): EntryLocation | null {
  const index = allEntries.findIndex((e) => e.slug === slug);
  if (index === -1) return null;
  const entry = allEntries[index];
  const part = book.parts.find((p) => p.entries.includes(entry))!;
  return {
    entry,
    part,
    index,
    prev: index > 0 ? allEntries[index - 1] : null,
    next: index < allEntries.length - 1 ? allEntries[index + 1] : null,
  };
}
