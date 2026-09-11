'use client';

/**
 * Chapter 6: an inference diagnostic, not a checkbox. The reader describes the
 * target, the sampling mechanism, and the assignment mechanism; the worksheet
 * returns a clustering level and variance estimator with its assumptions, a
 * sensitivity alternative, and a few-cluster check, each with a one-line reason.
 *
 * Logic follows Abadie, Athey, Imbens, and Wooldridge (2023): clustering is
 * justified by clustered sampling (clusters drawn from a larger population of
 * clusters) or clustered assignment (treatment assigned to whole clusters), not
 * by within-cluster correlation of outcomes alone; with a large sampled fraction
 * of clusters and treatment that varies within clusters, the conventional
 * cluster variance is conservative. Few-cluster advice follows MacKinnon,
 * Nielsen, and Webb (2023) and Cameron and Miller (2015).
 */

import { useId, useState, type ReactNode } from 'react';
import { HeldFixed, Note, Segmented, WidgetFrame, buttonClass } from './ui';
import { fmt } from './format';

type Target = 'observed' | 'population';
type Sampling = 'all' | 'sample_clusters' | 'within_every';
type Assignment = 'individual' | 'cluster' | 'mixed';
type Nesting = 'nested' | 'crossed' | 'none';
type YesNo = 'yes' | 'no';

interface Inputs {
  target: Target;
  sampling: Sampling;
  assignment: Assignment;
  nesting: Nesting;
  fe: YesNo;
  G: number;
  q: number;
}

interface Item {
  text: ReactNode;
  why: ReactNode;
}

interface Result {
  clusters: boolean;
  level: Item;
  estimator: Item;
  assumptions: Item[];
  sensitivity: Item[];
  fewClusters: Item;
  notes: Item[];
}

const PRESETS: { label: string; inputs: Inputs }[] = [
  {
    label: 'State policy, survey records',
    inputs: { target: 'observed', sampling: 'within_every', assignment: 'cluster', nesting: 'nested', fe: 'yes', G: 51, q: 1 },
  },
  {
    label: 'Individual randomization in sampled villages',
    inputs: { target: 'population', sampling: 'sample_clusters', assignment: 'individual', nesting: 'none', fe: 'no', G: 40, q: 0.05 },
  },
  {
    label: 'Firm-level program, all firms observed',
    inputs: { target: 'observed', sampling: 'all', assignment: 'mixed', nesting: 'none', fe: 'no', G: 120, q: 1 },
  },
];

function fewClusterAdvice(G: number, what: string): Item {
  if (G < 10) {
    return {
      text: `Fewer than 10 ${what}: cluster-robust SEs, and even the wild cluster bootstrap, are unreliable. Use randomization inference over the cluster-level assignments, and state the limitation plainly.`,
      why: 'With a handful of clusters the variance estimate rests on a handful of cluster-level residuals.',
    };
  }
  if (G < 50) {
    return {
      text: `Fewer than about 50 ${what}: use the wild cluster restricted bootstrap (WCR) or CRV3 (the cluster jackknife) with t(G − 1) critical values, not CR1 with normal critical values.`,
      why: 'CR1 over-rejects with few clusters; with few treated clusters even the bootstrap can fail (MacKinnon, Nielsen, and Webb 2023).',
    };
  }
  return {
    text: `${fmt(G, 'int')} ${what}: CR1 with t(G − 1) critical values is usually adequate. Still compare with the wild cluster bootstrap.`,
    why: 'The effective number of clusters is smaller than G when cluster sizes are very unequal or only a few clusters are treated.',
  };
}

export function recommend(x: Inputs): Result {
  const q = x.sampling === 'sample_clusters' ? x.q : 1;
  const superpop = x.target === 'population' && x.sampling === 'all';
  const clusteredSampling = (x.sampling === 'sample_clusters' && x.target === 'population') || superpop;
  const G = Math.max(0, Math.round(x.G));
  const assumptions: Item[] = [
    {
      text: 'The descriptions of sampling and assignment above are accurate.',
      why: 'The clustering level follows from how the data came to be, not from which standard error is largest.',
    },
  ];
  const sensitivity: Item[] = [];
  const notes: Item[] = [];
  let level: Item;
  let estimator: Item;
  let clusters = true;

  if (x.assignment === 'cluster') {
    level = {
      text: 'Cluster at the level where treatment is assigned.',
      why: `Every unit in a cluster shares one assignment, so there are ${fmt(G, 'int')} independent assignment units, not one per record.`,
    };
    estimator =
      G >= 50
        ? { text: 'Cluster-robust (CR1, Liang–Zeger) variance with t(G − 1) critical values.', why: 'The design has enough assignment clusters for the cluster-robust approximation.' }
        : G >= 10
          ? { text: 'Wild cluster restricted bootstrap (WCR) at the assignment level, or CRV3 with t(G − 1).', why: 'CR1 is unreliable with this few clusters; these corrections are designed for it.' }
          : { text: 'Randomization inference over cluster-level assignments; cluster-robust results only as a secondary check.', why: 'Below about 10 clusters no cluster-robust approximation is dependable.' };
    assumptions.push({
      text: 'Clusters do not affect one another (no spillovers across clusters).',
      why: 'Cluster-level inference treats clusters as independent units.',
    });
    if (x.nesting === 'nested') {
      assumptions.push({
        text: 'Sampling units (for example survey PSUs) sit inside the assignment clusters.',
        why: 'In a nested hierarchy, clustering at the coarser, assignment level also covers the sampling clustering.',
      });
    }
    if (x.fe === 'yes') {
      assumptions.push({
        text: 'Treatment changes within clusters (for example over time in a panel).',
        why: 'Cluster fixed effects absorb anything constant within a cluster, including a treatment that never switches on; they do not remove the need to cluster at the assignment level.',
      });
    }
    if (q >= 1 && x.target === 'observed') {
      notes.push({
        text: 'All clusters are observed and they are the target, so the uncertainty is about assignment, not sampling.',
        why: 'The cluster-robust variance is then conservative when effects vary across clusters, as the Neyman variance is in an experiment.',
      });
    }
    sensitivity.push({
      text: 'Heteroskedasticity-robust (EHW) SEs, shown only to measure how much clustering matters.',
      why: 'They ignore the clustered assignment and understate the uncertainty; they are not the result.',
    });
    if (G < 50) {
      sensitivity.push({ text: 'CR1, CRV3, and WCR p-values side by side.', why: 'Disagreement among them is itself a few-cluster warning.' });
    }
  } else if (x.assignment === 'individual') {
    if (clusteredSampling) {
      level = {
        text: 'Cluster at the sampling-cluster level (for example the survey PSU).',
        why: superpop
          ? 'Treating the observed clusters as draws from a larger population makes the choice of clusters a source of common variation.'
          : 'Clusters were drawn at random from a larger population of clusters, so which clusters entered the sample moves the estimate.',
      };
      estimator =
        q <= 0.2
          ? { text: 'Cluster-robust (CR1) at the sampling-cluster level, or the design-based variance the survey supplies (Taylor with strata and PSUs, or replicate weights).', why: 'With a small sampled fraction of clusters, the conventional cluster variance approximates the sampling variance.' }
          : { text: 'Cluster-robust at the sampling-cluster level, read as conservative; a finite-population correction, or AAIW’s causal cluster variance (CCV) or two-stage cluster bootstrap (TSCB), can tighten it.', why: `A sampled fraction of ${fmt(q, 'pct0')} is large; the conventional cluster variance then overstates the sampling component (Abadie et al. 2023).` };
      sensitivity.push({ text: 'EHW SEs as a lower bound.', why: 'The gap between EHW and cluster-robust SEs shows how much the clustered sampling matters here.' });
      if (superpop) {
        assumptions.push({
          text: 'The observed clusters are treated as a random draw from a larger, hypothetical population of clusters.',
          why: 'This model-based view is the conventional justification for cluster-robust SEs; if the observed clusters are the population of interest, choose “the observed units” and the answer changes.',
        });
      }
    } else {
      clusters = false;
      level = {
        text: 'No clustering adjustment.',
        why:
          x.sampling === 'within_every'
            ? 'Individuals were sampled within every cluster and treatment varies by individual: neither mechanism is clustered, and correlated outcomes within clusters alone do not call for clustering.'
            : x.sampling === 'all'
              ? 'Every cluster is observed and treatment varies by individual: neither the sampling nor the assignment is clustered.'
              : 'The target is the observed units, so which clusters were sampled is not a source of uncertainty for it, and assignment is individual.',
      };
      estimator = { text: 'Heteroskedasticity-robust (EHW) variance: HC1, or HC2 in small samples.', why: 'The uncertainty comes from individual-level assignment and sampling, which the robust variance captures.' };
      if (x.sampling === 'within_every') {
        assumptions.push({
          text: 'If the data are a stratified survey, the clusters act as strata.',
          why: 'A design-based variance that declares the strata is also valid and slightly smaller than EHW.',
        });
      }
      sensitivity.push({
        text: 'Cluster-robust SEs at the cluster level, read as an upper bound.',
        why: 'If the conclusion survives them, the clustering choice is not decisive; if not, report both and explain why EHW is the design-based answer.',
      });
    }
    if (x.fe === 'yes') {
      notes.push({
        text: 'Cluster fixed effects remove cluster-level shifts in the outcome.',
        why: 'They do not settle the clustering question, which depends on how units were sampled and assigned.',
      });
    }
  } else {
    level = {
      text: 'Cluster at the cluster level.',
      why: 'Treatment varies within clusters, but its rate differs between clusters, so assignment is partly clustered.',
    };
    if (clusteredSampling && q <= 0.2) {
      estimator = { text: 'Cluster-robust (CR1) at the cluster level.', why: 'With a small sampled fraction of clusters, the conventional cluster variance is approximately right.' };
    } else {
      estimator = {
        text: 'Cluster-robust (CR1) at the cluster level as a conservative bound; AAIW’s causal cluster variance (CCV) or two-stage cluster bootstrap (TSCB) where available.',
        why: 'When most or all clusters are observed and assignment is only partly clustered, the conventional cluster variance can be far too large, and EHW too small (Abadie et al. 2023).',
      };
    }
    sensitivity.push({
      text: 'EHW as a lower bound and CR1 as an upper bound.',
      why: 'If both lead to the same conclusion, the choice between them is not decisive.',
    });
    if (x.fe === 'yes') {
      assumptions.push({
        text: 'With cluster fixed effects, the effect is identified from within-cluster variation in treatment.',
        why: 'Clustering then matters through variation in effects across clusters; when effects are similar across clusters, EHW and CR1 will be close.',
      });
    }
  }

  if (x.nesting === 'crossed') {
    notes.push({
      text: 'Sampling clusters cut across the assignment clusters.',
      why: 'The hierarchy is not nested, so no single level covers both: consider two-way clustering, or argue that one source of common variation is negligible.',
    });
    sensitivity.push({ text: 'Two-way cluster-robust SEs on the sampling and assignment dimensions.', why: 'Non-nested mechanisms can each induce common variation.' });
  }
  if (clusters) {
    assumptions.push({ text: 'Many clusters, not many records, drive the large-sample approximation.', why: 'Cluster-robust inference is asymptotic in the number of clusters.' });
  }

  const fewClusters = clusters
    ? fewClusterAdvice(G, x.assignment === 'cluster' ? 'assignment clusters' : 'clusters')
    : {
        text: 'Not binding for the recommended estimator.',
        why: `No clustering adjustment is recommended; G = ${fmt(G, 'int')} matters only for the cluster-robust sensitivity check.`,
      };

  notes.push({
    text: 'This worksheet addresses inference conditional on the design.',
    why: 'It does not establish that the coefficient is causal; identification is a separate argument (Chapter 6).',
  });

  return { clusters, level, estimator, assumptions, sensitivity, fewClusters, notes };
}

function Radio<T extends string>(props: { legend: string; value: T; onChange: (v: T) => void; options: { value: T; label: string }[] }) {
  const name = useId();
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1 text-xs font-semibold text-ink">{props.legend}</legend>
      <div className="space-y-0.5">
        {props.options.map((o) => (
          <label key={o.value} className="flex cursor-pointer items-start gap-2 text-sm">
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={props.value === o.value}
              onChange={() => props.onChange(o.value)}
              className="mt-1"
              style={{ accentColor: 'var(--accent)' }}
            />
            <span>{o.label}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Out({ heading, items }: { heading: string; items: Item[] }) {
  return (
    <div>
      <div className="text-xs font-semibold uppercase tracking-wide text-ink-2">{heading}</div>
      <ul className="mt-1 space-y-1.5">
        {items.map((it, i) => (
          <li key={i} className="leading-snug">
            <span className="text-ink">{it.text}</span>
            <span className="block text-xs text-ink-2">
              <span className="font-semibold">Why: </span>
              {it.why}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ClusterDesignWorksheet() {
  const [x, setX] = useState<Inputs>(PRESETS[0].inputs);
  const set = <K extends keyof Inputs>(k: K) => (v: Inputs[K]) => setX((p) => ({ ...p, [k]: v }));
  const gId = useId();
  const qId = useId();
  const r = recommend(x);
  const qActive = x.sampling === 'sample_clusters';

  return (
    <WidgetFrame
      title="Where does the common uncertainty come from?"
      subtitle="Describe the target, how units were sampled, and how treatment was assigned. The worksheet derives a clustering level from the design, with its assumptions and alternatives."
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-xs font-medium text-ink-2">Start from an example:</span>
        {PRESETS.map((p) => (
          <button key={p.label} type="button" className={buttonClass} onClick={() => setX(p.inputs)}>
            {p.label}
          </button>
        ))}
      </div>

      <div className="mt-4 grid gap-x-6 gap-y-4 md:grid-cols-2">
        <Radio<Target>
          legend="1. Inferential target"
          value={x.target}
          onChange={set('target')}
          options={[
            { value: 'observed', label: 'The observed units (the clusters in the data are the population of interest)' },
            { value: 'population', label: 'A larger population of clusters than the one observed' },
          ]}
        />
        <Radio<Sampling>
          legend="2. Sampling mechanism"
          value={x.sampling}
          onChange={set('sampling')}
          options={[
            { value: 'all', label: 'All clusters and all their units are observed' },
            { value: 'sample_clusters', label: 'A random sample of clusters was drawn' },
            { value: 'within_every', label: 'Individuals were sampled within every cluster' },
          ]}
        />
        <Radio<Assignment>
          legend="3. Assignment mechanism"
          value={x.assignment}
          onChange={set('assignment')}
          options={[
            { value: 'individual', label: 'Treatment varies at the individual level' },
            { value: 'cluster', label: 'Treatment is assigned to whole clusters' },
            { value: 'mixed', label: 'Treatment varies within and between clusters' },
          ]}
        />
        <Radio<Nesting>
          legend="4. Are sampling units nested inside assignment clusters?"
          value={x.nesting}
          onChange={set('nesting')}
          options={[
            { value: 'nested', label: 'Yes (for example survey PSUs within states)' },
            { value: 'crossed', label: 'No, they cut across each other' },
            { value: 'none', label: 'There are no separate sampling clusters' },
          ]}
        />
        <Segmented<YesNo>
          legend="5. Cluster fixed effects included?"
          value={x.fe}
          onChange={set('fe')}
          options={[
            { value: 'no', label: 'No' },
            { value: 'yes', label: 'Yes' },
          ]}
        />
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label htmlFor={gId} className="block text-xs font-semibold text-ink">
              6. Number of clusters, G
            </label>
            <input
              id={gId}
              type="number"
              min={2}
              max={100000}
              value={x.G}
              onChange={(e) => set('G')(Math.max(2, Math.round(Number(e.target.value) || 2)))}
              className="mt-1 w-full rounded-md border border-[var(--border-strong)] bg-surface px-2 py-1 tabular-nums text-ink focus-visible:outline-2 focus-visible:outline-[var(--accent)]"
            />
          </div>
          <div>
            <label htmlFor={qId} className="block text-xs font-semibold text-ink">
              7. Sampled fraction of clusters
            </label>
            <input
              id={qId}
              type="number"
              min={0.001}
              max={1}
              step={0.01}
              disabled={!qActive}
              value={qActive ? x.q : 1}
              onChange={(e) => set('q')(Math.min(1, Math.max(0.001, Number(e.target.value) || 0.001)))}
              aria-describedby={`${qId}-hint`}
              className="mt-1 w-full rounded-md border border-[var(--border-strong)] bg-surface px-2 py-1 tabular-nums text-ink focus-visible:outline-2 focus-visible:outline-[var(--accent)] disabled:opacity-60"
            />
            <span id={`${qId}-hint`} className="text-xs text-muted">
              {qActive ? 'Between 0 and 1.' : 'All clusters observed: 1.'}
            </span>
          </div>
        </div>
      </div>

      <div className="mt-5 space-y-4 rounded-md border border-[var(--border-strong)] bg-sunken p-4" aria-live="polite">
        <div className="grid gap-4 md:grid-cols-2">
          <Out heading="Recommended clustering level" items={[r.level]} />
          <Out heading="Variance estimator" items={[r.estimator]} />
        </div>
        <Out heading="What this rests on" items={r.assumptions} />
        <Out heading="Also report (sensitivity)" items={r.sensitivity} />
        <Out heading="Few-cluster check" items={[r.fewClusters]} />
        <Out heading="Notes" items={r.notes} />
      </div>
      <Note>
        Rules follow Abadie, Athey, Imbens, and Wooldridge (2023): cluster when sampling or assignment is clustered, at the
        level of that mechanism; in a nested hierarchy the coarser relevant level typically governs. The output is a
        starting point for an argument, not a verdict.
      </Note>
      <HeldFixed>
        The estimand (an average treatment effect from a regression) and the data. Only the description of the design
        changes, and with it the source of uncertainty the standard error must reflect.
      </HeldFixed>
    </WidgetFrame>
  );
}
