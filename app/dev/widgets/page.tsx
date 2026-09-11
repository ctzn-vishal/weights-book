import type { Metadata } from 'next';
import type { ReactNode } from 'react';
import { PopulationSampler } from '@/components/widgets/PopulationSampler';
import { WeightBuilder } from '@/components/widgets/WeightBuilder';
import { HiddenEffectWeights } from '@/components/widgets/HiddenEffectWeights';
import { EstimandSwitcher } from '@/components/widgets/EstimandSwitcher';
import { ReplicateRanking } from '@/components/widgets/ReplicateRanking';
import { ClusterDesignWorksheet } from '@/components/widgets/ClusterDesignWorksheet';

export const metadata: Metadata = {
  title: 'Widget demo (development)',
  robots: { index: false, follow: false },
};

function Section({ name, usage, children }: { name: string; usage: string; children: ReactNode }) {
  return (
    <section className="mt-12">
      <h2 className="font-sans text-xl font-semibold text-ink">{name}</h2>
      <pre className="mt-1 overflow-x-auto rounded bg-sunken px-2 py-1 font-mono text-xs text-ink-2 [contain:inline-size]">{usage}</pre>
      {children}
    </section>
  );
}

export default function WidgetDemoPage() {
  return (
    <main className="mx-auto w-full min-w-0 max-w-3xl px-4 py-10">
      <h1 className="font-sans text-2xl font-semibold text-ink">Widget demo</h1>
      <p className="mt-2 text-ink-2">
        Development page, not part of the book. Widgets with data read fake fixtures from{' '}
        <code className="font-mono text-sm">app/dev/widgets/data</code> (key <code className="font-mono text-sm">devw</code>
        ); the synthetic widgets draw from <code className="font-mono text-sm">lib/synthpop.ts</code>.
      </p>

      <Section name="PopulationSampler (Chapter 0)" usage="<PopulationSampler />">
        <PopulationSampler />
      </Section>
      <Section name="EstimandSwitcher (Chapter 1)" usage={'<EstimandSwitcher id="devw.estimand_set" />'}>
        <EstimandSwitcher id="devw.estimand_set" />
      </Section>
      <Section name="WeightBuilder (Chapter 2)" usage="<WeightBuilder />">
        <WeightBuilder />
      </Section>
      <Section name="ReplicateRanking (Chapter 3 lab)" usage={'<ReplicateRanking id="devw.replicates" />'}>
        <ReplicateRanking id="devw.replicates" />
      </Section>
      <Section name="HiddenEffectWeights (Chapter 5)" usage={'<HiddenEffectWeights cellsId="devw.cells" />'}>
        <HiddenEffectWeights cellsId="devw.cells" />
      </Section>
      <Section name="HiddenEffectWeights without cells" usage="<HiddenEffectWeights />">
        <HiddenEffectWeights />
      </Section>
      <Section name="ClusterDesignWorksheet (Chapter 6)" usage="<ClusterDesignWorksheet />">
        <ClusterDesignWorksheet />
      </Section>
    </main>
  );
}
