# CONTRACT — *Weights, Design, and Estimands*, first draft

Every agent building this draft follows this file. When it conflicts with
`docs/PROPOSAL_weighting_booklet_v3_FINAL.md` (v3) or `docs/PLAN_v4_implementation.md`
(v4), this file wins for mechanics and v3 wins for concepts.

**Goal of this pass:** a complete, deployable first draft of every chapter, for the
author to read on a live URL (`vishalsingh.org/weights`). Every chapter present,
real numbers from real data, honest caveats, working figures, the core
interactives. Depth over polish; correctness over coverage. Nothing is final: the
site ships `noindex` with a draft banner.

---

## 1. Locations and ownership

| Path | What | Owner |
|---|---|---|
| `C:\github\weights-book\` | Next.js 16.3.4 + MDX front-end, git, deployed on Vercel with `basePath: '/weights'` | FE agent; W agent (widgets only); integrator |
| `C:\Users\Vishal Singh\Box\ipums\book\` | analysis and chapter drafts (this folder) | chapter agents, one folder each |
| `…\Box\ipums\{parquet,analysis,aggregate}\` | data and the existing pipeline | **read-only for everyone** |

Box forbids dotfiles, so no git lives in Box. **Vercel never sees Box**: every
number on the site reaches it as a small JSON artifact exported into the repo.
**Microdata never leaves Box** (IPUMS terms). **`Box\ipums\env.txt` holds the IPUMS
API key: never copy, print, or mirror it.**

| Agent | Writes | Must not touch |
|---|---|---|
| FE | repo: `app/` (layout, home, `not-found`, `dev/kitchen-sink/`), `components/book/**`, `components/charts/**`, `lib/**` (except `lib/synthpop*`), `scripts/**`, `mdx-components.tsx`, `next.config.ts` (keep basePath and plugins), `app/globals.css`, `docs/**` | `components/widgets/**`, `lib/synthpop*`, `app/ch*/**`, `app/appendix-*/**` |
| W | repo: `components/widgets/**`, `lib/synthpop.ts`, `lib/synthpop.test.ts`, `app/dev/widgets/**` | everything else; **no `package.json` changes** |
| chapter agents | Box: `book/chapters/<slug>/**` only | the repo (read-only; run `scripts/check-mdx.mjs`), all other Box paths |
| integrator (lead) | Box `book/export.py`, this file; repo `app/ch*/**`, `app/appendix-*/**`, `data/**`, commits | — |

Nobody else commits. Nobody else runs `npm install`; if you need a package, say so
in your report. Two builds must not share a `.next`: FE uses the default dir and
port 3000; W uses `NEXT_DIST_DIR=.next-widgets` and port 3001.

## 2. Pipeline

```
Box\ipums\book\chapters\<slug>\build.py   (reads Box parquet via duckdb / polars / svy)
        |  writes
        v
Box\ipums\book\chapters\<slug>\artifacts\{manifest,facts,ledger}.json + figures\*.json
Box\ipums\book\chapters\<slug>\article.mdx   (prose; cites artifacts by id)
        |  book/export.py  (integrator)
        v
C:\github\weights-book\app\<slug>\{article.mdx, page.tsx, data\...}  -> git -> Vercel
```

After the first export a chapter's MDX lives in the repo; artifacts are always
regenerated in Box and re-exported.

## 3. Chapters

| Slug | Key | Title | Owner |
|---|---|---|---|
| `ch00-start-here` | `ch0` | Target, Contribution, Uncertainty | C-ch0007 |
| `ch01-estimands` | `ch1` | What Are We Trying to Estimate? | C-ch01 |
| `ch02-weights` | `ch2` | Where Survey Weights Come From | C-ch02 |
| `ch03-design` | `ch3` | Point Estimates and Design-Based Uncertainty | C-ch03 |
| `ch03-lab-replicates` | `ch3lab` | Lab: Which State Differences Are Real? | C-ch03lab |
| `ch04-regression` | `ch4` | What Are We Weighting For? | C-ch0405 |
| `ch05-hidden-weights` | `ch5` | Hidden Weights Under Heterogeneous Effects | C-ch0405 |
| `ch06-clustering` | `ch6` | Sampling Design, Assignment Design, and Clustering | C-ch06 |
| `ch07-cluster-choice` | `ch7` | Whose Decision Was It? Clustering by the Source of Variation | integrator |
| `ch08-field-guide` | `ch8` | Field Guide: Six Surveys, Declared | C-ch0007 |
| `appendix-a-notation` | `appA` | Notation and Crosswalk | C-ch0007 |
| `appendix-b-derivations` | `appB` | Scoped Derivations | C-ch0007 |
| `appendix-c-reproducibility` | `appC` | Data, Code, and Reproducibility | C-ch0007 |

## 4. Chapter folder layout (Box)

```
book/chapters/<slug>/
  build.py          python build.py  -> regenerates artifacts/ deterministically
  verify.R          optional: R `survey` sentinel checks (section 6)
  artifacts/
    manifest.json   {key, slug, inputs:[{path, rows, note}], code:"build.py", validation:[...], generated_at}
    facts.json      {key, facts:{<fact_key>: Fact}}
    ledger.json     {key, ledgers:{<ledger_key>: Ledger}}
    figures/<figure_key>.json
  article.mdx       the chapter prose
  NOTES.md          open questions, caveats, validation results, new citations
```

Keys are lower_snake_case. A fact's global id is `<key>.<fact_key>`, for example
`ch1.atus_work_weighted`; a figure's is `<key>.<file name without .json>`.

## 5. Artifact schema

**Fact** — one number the prose states.

```json
"atus_work_weighted": {
  "value": 213.8,
  "display": "213.8",
  "unit": "minutes per day",
  "se": null, "ci_low": null, "ci_high": null, "ci_display": null, "df": null,
  "n": 8548,
  "weight": "WT06",
  "variance": "weights_only_understated",
  "estimand": "Mean minutes per day spent working, all 2023 person-days, civilian noninstitutional population 15+",
  "source": "IPUMS ATUS 2023 (analysis/atus/atus_respondent.parquet)",
  "benchmark": "BLS ATUS 2023 published 3.56 hours/day",
  "note": ""
}
```

- Required: `value`, `display`, `estimand`, `source`.
- `display` is **exactly** the string the reader sees. Percent facts include `%`
  ("32.3%"), dollar facts include `$`, counts use thousands separators ("8,548").
  Unit words stay in the prose. Python formats; the front-end prints.
- `ci_display` looks like "31.6%–32.9%" (en dash). Intervals are 95%; give `df`
  when the interval uses t.
- `variance` is one of `taylor`, `replicate_sdr(80)`, `replicate_sdr(160)`,
  `replicate_brr`, `weights_only_understated`, `cluster_robust(<level>)`,
  `wild_cluster_bootstrap(<level>)`, `none`, `simulation`.

**Ledger** — the Analysis Ledger (v3 §2.1), one per headline result.

```json
"atus_work": {
  "title": "How much do Americans work? (ATUS 2023)",
  "target_population": "...", "estimand": "...", "estimator": "...",
  "explicit_weights": "...", "implicit_weights": "...", "randomness": "...",
  "variance_estimator": "...", "assumptions": "...",
  "facts": ["ch1.atus_work_weighted"]
}
```

**Figure** — `figures/<figure_key>.json`. Common fields: `type` (required),
`title`, `subtitle`, `alt` (required: one sentence saying what the chart shows),
`format`, `source`, `note`. Values are raw numbers; proportions are stored as 0–1.

| `type` | Fields |
|---|---|
| `dot` | `rows:[{label, estimate, ci_low?, ci_high?, group?, role?, n?}]`, `x_label`, `reference?:{value,label}`, `domain?:[lo,hi]` (forest or dot plot) |
| `bar` | `rows:[{label, value, ci_low?, ci_high?, role?}]`, `x_label`, `domain?` (horizontal bars) |
| `line` | `series:[{name, role?, segments:[[{x,y,lo?,hi?},...],...]}]`, `x_label`, `y_label`, `annotations?:[{x,label}]`, `y_domain?`. **`segments` are break segments: a line is never drawn across a series break** |
| `slope` | `rows:[{label, left, right, role?}]`, `left_label`, `right_label` (for example unweighted → weighted) |
| `table` | `columns:[{key,label,format?,align?}]`, `rows:[{...}]`, `highlight_key?`. Numeric tables live here, never as hand-typed markdown |
| `histogram` | `bins:[{x0,x1,count}]`, `x_label`, `y_label`, `markers?:[{x,label}]` |
| `cells`, `estimand-set`, `replicates` | widget data (section 9) |

`format` is one of `pct0 pct1 pct2` (value is a proportion), `num0 num1 num2 num3`,
`int` (thousands separator), `usd0`, `min0 min1`, `ratio2` (renders "1.64×").
`role` is one of `weighted unweighted design naive truth benchmark treated control
highlight muted cat1`…`cat8`: colour by meaning, never by hue.

**Determinism.** Same inputs give byte-identical `facts.json`, `ledger.json`, and
`figures/*.json`: sorted keys, fixed rounding, seeded randomness, no timestamps
(only `manifest.json` may carry `generated_at`). Suppress any estimate with
unweighted n below 100 (floor 30, with the reason stated); flag CV above 0.30.

## 6. Data and estimation rules

- **Read `analysis/`** (the cleaned layer), not `parquet/`. UPPERCASE = raw IPUMS;
  lowercase = derived (`age_group`, `female`, `race_eth5`, `educ4`, `marst3`,
  `emp3`, `citizen_b`, `foreign_born`, outcome flags). Sentinel codes are already
  NULL. Read the dataset's `analysis/<coll>/metadata/<ds>.design.json` and
  `.dictionary.json` before touching it. Never guess a code.
- **The variance tier is a property of the extract, not a choice.** `nhis_core`
  is Taylor with the **(STRATA, PSU) composite key, built per year**; `acs` is
  SDR, 80 replicates, c = 4/80, df = 79; `cps_asec` is SDR, 160 replicates,
  c = 4/160, df = 159 (2005 and later); CPS supplements and ATUS are
  `weights_only_understated`. Weights-only sources may carry an estimand lesson;
  they must not carry an uncertainty lesson.
- **`svy` 0.28 pitfalls (verified on this machine):**
  - Replicate weights: the default call **silently ignores declared replicate
    weights and returns a Taylor SE with df = n − 1**. Always pass
    `method="replication", variance_center="estimate"` and assert the returned
    df is 79 or 159, not n − 1. (`scale=` and `df=` on `SdrWgts` take effect once
    `method="replication"` is passed; the default call ignores the whole replicate
    declaration. The error's direction is not fixed: it has both overstated and
    understated the replicate SE.)
  - `where=` takes `svy.col(...)` expressions, not strings. A `where=` condition on an
    8- or 16-bit integer column (IPUMS flags such as `ASTATFLG`) raises `ComputeError`;
    cast to `Int64` first.
  - Nulls in an outcome raise unless `drop_nulls=True`; decide and record it.
  - Singleton PSUs raise `SingletonError`. Choose a rule deliberately and report
    PSUs retained and lonely strata next to every domain SE.
  - On Windows set `PYTHONIOENCODING=utf-8` and `NO_COLOR=1`, or use `.to_polars()`.
- **R oracle.** R 4.6.1 with `survey` 4.5 and `arrow` is installed but not on PATH:
  `"C:\Program Files\R\R-4.6.1\bin\x64\Rscript.exe"`. Use `arrow::read_parquet`.
  Keep `options(survey.lonely.psu="fail")`. Validate two or three headline
  design-based numbers per chapter and record the comparison in
  `manifest.validation`.
- **Box is slow when cold.** Files hydrate on first read and get evicted. Reading
  a parquet footer (`DESCRIBE`, `parquet_metadata`) downloads the whole file: a
  3 GB ACS replicate part costs 60–80 s. Select only the columns you need, never
  scan the tree for schemas, and reuse a loaded frame.
- **DuckDB gotcha:** the lowercase `year` and `month` aliases come back as
  `year_1` and `month_1` under `SELECT *`. Select columns explicitly. ASEC parts
  are decade-ragged: use `union_by_name=true`.
- **Benchmarks are not truth** (v3 §7.8). Compare with published figures, label
  them "external benchmark", and record every comparison.
- Cite IPUMS using each DDI's `ipums_citation`; cite NHANES, BRFSS, and ANES per
  their producers.

## 7. Editorial rules

**Audience:** doctoral students and applied researchers in economics, marketing,
political science, sociology, and public health, with one econometrics sequence
and no survey-sampling training. **Register:** precise, plain, and quietly
confident. Short declarative sentences that carry real content. Define a term
the first time it appears. Prefer the concrete example to the abstract claim.

**Pedagogical contract (v3 §3), binding:**
1. Open with a real-data puzzle that produces two or more defensible-looking
   answers; then intuition or a picture, then the equation, then code, then back
   to the puzzle.
2. A "Predict first" callout comes before every key equation and interactive.
3. One estimand per section, stated. Headline results get a `<Ledger>`.
4. Failure first: show the defensible-looking wrong answer, then repair it.
5. Close every empirical chapter with `<Closing>`: **What we learned about the
   question**, **What the method changed**, and **What this analysis does not
   establish** (mandatory, and strictest in Chapters 4–6).

**Binding corrections (v3 §7). Never contradict these anywhere:**
1. Not "weights get the point estimate, the design gets the uncertainty." The
   weights help define the estimator; the sampling design *and the weight
   construction* determine repeated-sampling variance.
2. No "HT estimands." Correct inclusion weights give design-unbiased or
   consistent estimators for *specified finite-population quantities*.
3. Moulton is a **special-case regression analogue of the clustering component of
   a design effect**, not the design effect itself.
4. Replicate weights are the survey world's **pre-packaged repeated sampling**.
   BRR, Fay, jackknife, SDR, and bootstrap are distinct procedures; never call
   them "a bootstrap."
5. The "cluster at the coarser level" rule applies to nested hierarchies inside
   the full Abadie–Athey–Imbens–Wooldridge statement.
6. Not "there is no unweighted estimator": equal case weights do not imply equal
   weighting of heterogeneous conditional effects.
7. MRP is not defined by Bayesian software.
8. Benchmarks are not truth.
9. Causal restraint: the Chapter 4–5 contrasts are descriptive; Chapter 6's
   policy coefficient is inference conditional on the design unless a modern
   staggered estimator is used.
10. Coverage honesty: target populations reflect actual coverage (BRFSS 2024
    omits Tennessee; 2023 omits Kentucky and Pennsylvania; 2021 omits Florida).

**Numbers.** Every number that comes from data is a `<Fact id="..."/>`, a
`<KeyNumber>`, or lives in a `<Chart>`. Never type one. Allowed in prose: years,
counts that are definitions ("80 replicate weights", "two stages"), chapter and
figure numbers, and numbers inside math. `check-mdx` flags the rest.

**Avoid:** hype and filler ("crucial", "delve", "robust" as praise, "it is
important to note", "in today's world", "game-changer", "powerful"); stacked
rhetorical questions; exclamation marks; emoji; "Let us" or "let's"; sentences that
announce what the next sentence will say; ending a section by summarizing it;
causal verbs (causes, drives, leads to, because of) for descriptive contrasts.

**Length:** 2,000–3,500 words per chapter (appendices as needed). Headings are
`##` and `###`. The chapter title comes from the TOC, so there is **no `#` heading**.

## 8. MDX authoring

Files start with imports (widgets only), then prose. No frontmatter.

**Global components (no import needed):**

| Component | Use |
|---|---|
| `<Fact id="ch1.x" />` | inline number; add `ci` to append " (95% CI …)"; hover shows n, weight, variance, source |
| `<KeyNumber id="ch1.x" label="..." />` | a large number with a one-line label |
| `<Figure n="1.2" caption="...">...</Figure>` | numbered frame; **the caption states the finding**, not the subject |
| `<Chart id="ch1.weekend_share" />` | renders a figure artifact by id (usually inside `<Figure>`) |
| `<Ledger id="ch1.atus_work" />` | the Analysis Ledger table |
| `<Callout kind="predict" title="Predict first">...</Callout>` | kinds: `predict`, `note`, `warning`, `box` (classic replication or provenance), `definition`, `draft` |
| `<SideNote>...</SideNote>` | margin note |
| `<Cite id="solon2015" />` | "(Solon, Haider, and Wooldridge 2015)"; add `narrative` for "Solon, Haider, and Wooldridge (2015)"; several ids comma-separated |
| `<Details summary="Derivation">...</Details>` | collapsible block |
| `<Closing><Learned>...</Learned><Changed>...</Changed><NotEstablished>...</NotEstablished></Closing>` | the closing panels |

**Widgets (import explicitly):**
`import { WeightBuilder } from '@/components/widgets/WeightBuilder'` (section 9).

**Syntax rules (MDX 3 is stricter than Markdown):**
- Inline math is `$$...$$` **inside a line**; display math is a `$$` fence on its
  own lines. A single `$` is always currency. Notation macros: `\E \Var \Cov \plim
  \DEFF \DEFT \CV \SE \nKish \ndesign \nDDC \PATE \ATT \ATU`.
- Leave a blank line before and after any JSX block that contains markdown.
- `<` and `{` in prose are syntax. Write "less than", or escape them as `\<` and `\{`.
- Comments are `{/* ... */}`, never `<!-- -->`.
- Internal links are root-relative without the base path:
  `[Chapter 3](/ch03-design#domains)`.
- Code blocks are fenced with a language (`python`, `r`, `stata`).
- Numeric tables go in a `<Chart>` of type `table`. Markdown tables are for text only.

**Check before you report done:**

```
node C:/github/weights-book/scripts/check-mdx.mjs <article.mdx> --data <artifacts dir> [--data <other chapter's artifacts>]
```

Zero errors required. Every remaining warning is either fixed or explained in NOTES.md.

## 9. Widget API (W implements; chapters use)

| Widget | Props | Data |
|---|---|---|
| `PopulationSampler` | none | canonical synthetic population (`lib/synthpop.ts`) |
| `WeightBuilder` | none | synthetic |
| `HiddenEffectWeights` | `cellsId?` | `type:"cells"`: `{outcome_label, treatment_label, effect_format, cells:[{label, pop_share, treat_share, effect, effect_se?, n}], ols_coef?, wls_coef?}` |
| `EstimandSwitcher` | `id` | `type:"estimand-set"`: `{question, format, options:[{id, label, unit, weight, estimate, display, n, note?, ledger?}]}` |
| `ReplicateRanking` | `id` | `type:"replicates"`: `{measure_label, format, method:"SDR", n_reps:80, scale:0.05, top_k, units:[{id, label, estimate, reps:number[]}]}` |
| `ClusterDesignWorksheet` | none | rule-based, no data |
| `VcovExplorer` | `id` | `type:"vcov-menu"`: `{coef, coef_display, truth, n_obs, options:[{key, label, assumes, verdict, role, se, ratio, ci_low, ci_high, p, *_display, code:{r,python,stata}, arg:{r,python,stata}}]}` |
| `RejectionGrid` | `id` | a `type:"table"` figure with columns `design, estimator, code, reject, ratio, verdict` (sortable, filterable) |

Use only CSS custom properties from `app/globals.css` (`--role-*`, `--chart-*`,
`--text*`, `--surface*`, `--border*`, `--accent`). Charts never hard-code a colour.

## 10. Citation keys

Use these ids with `<Cite>`. If you need another, make a lower-case `authorYEAR`
key and give the full reference under "New citations" in NOTES.md.

`solon2015` `abadie2023` `abadie2020` `mackinnon2023` `cameron2015` `bertrand2004`
`moulton1990` `dickens1990` `dumouchel1983` `gelman2007` `little2004`
`gelmanlittle1997` `angrist1998` `aronow2016` `sloczynski2022`
`chattopadhyay2023` `bollen2016` `lundberg2021` `lumley2010` `heeringa2017`
`kish1965` `horvitz1952` `fay1995` `wooldridge1999` `wooldridge2001`
`wooldridge2007` `deaton1997` `valliant2018` `meng2018` `bradley2021`
`goodmanbacon2021` `callaway2021` `ipums_usa` `ipums_cps` `ipums_atus`
`ipums_nhis` `nhanes` `brfss2024` `anes_cdf` `nchs_db511` `census_acs_dm`
`census_spm` `bls_atus`

## 11. What to report back

A short report: artifacts produced (counts), headline numbers with their
validation (benchmark or R check), the check-mdx result, open problems, and every
place you departed from v3 or v4 and why. Do not paste artifact contents.
