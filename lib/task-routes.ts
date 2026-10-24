export type TaskGroup = 'Define the quantity' | 'Declare the survey' | 'Estimate and report' | 'Check identification';

export interface TaskRoute {
  id: string;
  question: string;
  description: string;
  group: TaskGroup;
  slug: string;
  heading: string;
  related?: { label: string; slug: string; heading: string };
}

export const taskRoutes: readonly TaskRoute[] = [
  {
    id: 'turnout-denominator',
    question: 'Why did my turnout denominator change?',
    description: 'Separate the Census convention from a respondents-only rate.',
    group: 'Define the quantity',
    slug: 'ch01-estimands',
    heading: 'what-was-turnout-in-2020',
    related: { label: 'What missing answers allow', slug: 'ch09-identification', heading: 'missing-answers-turnout-as-a-set' },
  },
  {
    id: 'weight-unit',
    question: 'Which weight goes with the unit I am counting?',
    description: 'Choose whether a rate describes households, people, children or days.',
    group: 'Define the quantity',
    slug: 'ch01-estimands',
    heading: 'which-weight-goes-with-which-unit',
  },
  {
    id: 'choose-survey',
    question: 'Where is the guide for my survey?',
    description: 'Compare the designs before opening one of six release-specific guides.',
    group: 'Declare the survey',
    slug: 'ch08-field-guide',
    heading: 'six-surveys-at-a-glance',
  },
  {
    id: 'acs-declaration',
    question: 'Which weights declare the ACS design?',
    description: 'Find the ACS person or household weight and its replicate weights.',
    group: 'Declare the survey',
    slug: 'ch08-field-guide',
    heading: 'acs-2024-1-year',
    related: { label: 'What replicate weights change', slug: 'ch03-lab-replicates', heading: 'replicate-weights-repeated-sampling-pre-packaged' },
  },
  {
    id: 'nhanes-measurement',
    question: 'Which weight for a NHANES examination?',
    description: 'Start with the NHANES release guide and the measurement-specific weight.',
    group: 'Declare the survey',
    slug: 'ch08-field-guide',
    heading: 'nhanes-august-2021august-2023',
  },
  {
    id: 'brfss-declaration',
    question: 'How should I declare BRFSS strata and PSUs?',
    description: 'Check the survey design and the rule for single-PSU strata.',
    group: 'Declare the survey',
    slug: 'ch08-field-guide',
    heading: 'brfss-2024',
  },
  {
    id: 'subgroup-se',
    question: 'Can I trust the standard error for a small subgroup?',
    description: 'Estimate a domain without deleting other sampled records first.',
    group: 'Estimate and report',
    slug: 'ch03-design',
    heading: 'domains-subset-the-design-not-the-data',
  },
  {
    id: 'group-difference',
    question: 'How do I estimate a difference between groups?',
    description: 'Account for both groups being measured within the same survey.',
    group: 'Estimate and report',
    slug: 'ch03-design',
    heading: 'two-groups-in-one-sample',
  },
  {
    id: 'weighted-regression',
    question: 'Why do weighted and unweighted coefficients differ?',
    description: 'Identify the population projection and the observations entering it.',
    group: 'Estimate and report',
    slug: 'ch04-regression',
    heading: 'what-are-we-weighting-for',
    related: { label: 'Implicit regression weights', slug: 'ch05-hidden-weights', heading: 'which-cells-the-regression-listens-to' },
  },
  {
    id: 'cluster-level',
    question: 'Should I cluster by state or by county?',
    description: 'Trace the sampling and assignment units before choosing a variance rule.',
    group: 'Estimate and report',
    slug: 'ch06-clustering',
    heading: 'clustering-is-a-question-about-the-design',
  },
  {
    id: 'few-clusters',
    question: 'Are there enough treated clusters?',
    description: 'Inspect the limits of the policy comparison and its uncertainty checks.',
    group: 'Estimate and report',
    slug: 'ch06-clustering',
    heading: 'the-standard-error-ladder',
  },
  {
    id: 'nonresponse-assumption',
    question: 'What can unanswered turnout questions establish?',
    description: 'See the range the file supports before imposing a response assumption.',
    group: 'Check identification',
    slug: 'ch09-identification',
    heading: 'missing-answers-turnout-as-a-set',
  },
  {
    id: 'no-overlap',
    question: 'What if my comparison has no overlap?',
    description: 'Understand why an empty cell cannot supply an observed contrast.',
    group: 'Check identification',
    slug: 'ch09-identification',
    heading: 'no-support-an-empty-cell-is-an-unidentified-contrast',
  },
];

export const taskHref = ({ slug, heading }: Pick<TaskRoute, 'slug' | 'heading'>): string => `/${slug}#${heading}`;

export function findTask(id: string): TaskRoute {
  const task = taskRoutes.find((item) => item.id === id);
  if (!task) throw new Error(`Unknown task route "${id}"`);
  return task;
}
