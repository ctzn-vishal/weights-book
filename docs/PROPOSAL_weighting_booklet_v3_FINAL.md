# Proposal (v3, final): *Weights, Design, and Estimands — A Field Guide for Applied Researchers*

**Type:** Online booklet (stitched HTML/MDX chapters) for vishalsingh.org
**Seed article:** `weights_vs_design_distill_article.html` (revised into Ch. 3 per §6)
**Audience:** Doctoral students and applied researchers in economics, marketing, political science, sociology, public health. One econometrics/statistics sequence assumed; no survey-sampling training assumed.
**Execution:** Claude Code, with repo access + empirical data (Tigris parquet store, survey-prep pipeline).
**Status:** Final planning document. Supersedes v1 (scope) and v2 (conceptual architecture). v3 replaces the empirical spine: contemporary applications carry every chapter; the classic SHW-era replications become compact provenance boxes. Nothing conceptual from v2 is weakened.

---

## 1. Pitch and positioning

Applied researchers ask "should I use the weights?" — but that question is incomplete. A defensible answer requires separating three decisions: the population quantity being targeted, the way observations enter the estimator, and the sampling or assignment design that governs uncertainty. Training on these decisions is fragmented across disciplines: econometrics, survey statistics, epidemiology, and political science each teach parts of the same problem with different terminology and different defaults. Existing treatments typically emphasize one part — survey design (Lumley; Heeringa–West–Berglund), regression weighting (Solon–Haider–Wooldridge), causal estimands (Aronow–Samii; Słoczyński), clustering (Abadie–Athey–Imbens–Wooldridge; MacKinnon–Nielsen–Webb), or poststratification (Gelman). This booklet connects those decisions in one applied workflow — and does so through **contemporary empirical questions readers already care about**: housing affordability, mental distress, hypertension control, telework and earnings, and state health policy.

The differentiators, in priority order:

1. a recurring cross-disciplinary vocabulary (one framework, one notation, one crosswalk table);
2. contemporary headline applications in which a central technical correction has a *visible substantive payoff*;
3. the hidden-effect-weights interactive (population projection vs PATE, live);
4. a careful sampling-vs-assignment account of clustering;
5. release-specific survey field guides generated from pipeline metadata, with versioned replications and exact analysis contracts.

### 1.1 The empirical principle (new in v3, binding)

Every chapter is organized around:

> **A substantive question that produces two or more defensible-looking answers, with the chapter's technical concept explaining why they differ.**

And each chapter isolates *one* thing that visibly changes:

| Ch. | What visibly changes |
|---|---|
| 1 | The answer changes because the **target population or unit** changes |
| 2 | The point estimate changes because **representation weights** change |
| 3 | The conclusion changes because **design-based uncertainty** changes |
| 4 | The regression coefficient changes because **explicit weighting and specification** change |
| 5 | The interpretation changes because **implicit effect weights** change |
| 6 | The uncertainty changes because the number of **independent assignment units** is far smaller than the number of records |

No application is asked to demonstrate all three framework pillars at once.

---

## 2. Conceptual backbone: Target — Contribution — Uncertainty

The mnemonic hook remains:

> **"What is this number a weighted average of, and who chose the weights?"**

sitting on top of a formal three-part framework that gives every chapter a stable address:

**A. Target — who and what is the estimate about?** Target population; finite-population vs superpopulation; descriptive vs causal estimand; the specific quantity (mean, total, projection coefficient, PATE, ATT, …). Estimand / estimator / estimate are three objects; target / frame / sampled / respondent / analytic populations are five.

**B. Contribution — how does each unit, cell, or conditional effect enter the estimator?** Design/base weights; nonresponse and calibration adjustments; frequency weights; precision weights; equal case weights; *implicit* regression weights on heterogeneous conditional effects; (Ch. 3 adds) standardization weights that redefine the comparison population.

**C. Uncertainty — which hypothetical repetition makes the estimate vary?** Sampling; treatment assignment; response/nonresponse; model-based superpopulation variation; combinations. The variance is not another weighted average — it is a statement about a repetition mechanism, and identifying that mechanism is itself a modeling decision.

### 2.1 The Analysis Ledger (required for every empirical result)

Rendered by a reusable `<AnalysisLedger>` component that consumes the result-JSON artifact (§10.3), so it can never drift from the numbers:

| Field | Required statement |
|---|---|
| Target population | Who is the result intended to describe? |
| Estimand | What exact population quantity is being estimated? |
| Estimator | What sample rule produces the estimate? |
| Explicit weights | What does each supplied or constructed weight mean? |
| Implicit weights | Which groups or conditional effects get more leverage? |
| Source of randomness | Sampling, assignment, response, model? |
| Variance estimator | Taylor, replicate, cluster-robust, randomization-based, … |
| Assumptions | What must hold for the interpretation? |

### 2.2 Notation contract (frozen before drafting)

- $d_i = 1/\pi_i$ — base/design weight
- $g_i$ — nonresponse/calibration adjustment factor
- $w_i = d_i\,g_i$ — final survey weight as shipped
- $a_i$ — precision/analysis weight
- $f_i$ — frequency weight
- $w_i^{(r)}$ — replicate weight, replicate $r$
- $s_a$ — age-standardization weights (population-standard shares)
- $\omega_i$ — implicit regression/effect weight

`w` is never overloaded merely because software calls everything a "weight."

### 2.3 Required early box: *Four effective samples that are not the same thing*

Separated with distinct notation (Ch. 0 or Ch. 2):

1. $n_{\text{Kish}} = n/(1+\mathrm{CV}(w)^2)$ — weight-dispersion approximation, valid under restrictive conditions;
2. $n_{\text{design}}(\hat\theta) = n/\mathrm{DEFF}(\hat\theta)$ — estimator- and outcome-specific; a survey has no single universal effective size;
3. the regression effective sample — Aronow–Samii's $\omega_i$: a *composition* object, no scalar $n$ by default, possibly signed;
4. $n_{\text{DDC}}$ — Meng's MSE-equivalent size under selection, which prices bias, not just variance (deferred essay; forward-referenced).

---

## 3. Pedagogical contract (style rules for every chapter)

1. **Real-data puzzle → intuition/picture → equation → code → return to the puzzle.** *(Revised in v3: the contemporary puzzle opens the chapter and creates the demand for the method; the chapter closes by resolving it.)* "Predict first" prompts precede every equation and interactive.
2. **One estimand per section**, stated via the Analysis Ledger.
3. **Every number is reproducible** — prose numbers template-injected from result artifacts, never typed.
4. **Two-column dialect tables** wherever literatures name the same object differently (`<DialectTable>`; master version in Appendix A).
5. **Failure-first.** The opening puzzle's wrong answer is produced by defensible-looking code, then repaired.
6. **Real surveys for headline results.** Simulations confined to interactives and Monte Carlo validation.
7. **Qualified slogans** — the §7 corrections are binding on all prose and UI text.
8. **Two closing panels + one caveat line, every empirical chapter** *(new in v3)*:
   - **What we learned about the substantive question** (e.g., household and person exposure to rent burden differ; hypertension prevalence far exceeds control; telework access is highly stratified; the policy analysis has ~dozens of independent units, not millions).
   - **What the method changed** (the denominator; the represented population; the confidence interval; the regression target; the effective number of independent units).
   - **What this analysis does not establish** — mandatory, and most important for Ch. 4–6.

---

## 4. First edition structure

Eight chapters (0–7) + appendices; 2,500–4,000 words each. Classic replications appear as **boxes** (§4.1). Deferred material in §8.

### 4.1 Two-tier empirical structure (binding)

- **Headline application:** contemporary, substantively interesting, full prose + interactive + Ledger + figures; positioned as *the reason to learn the method*.
- **Classic replication box:** short, faithful to the source paper, expandable derivation or linked notebook; positioned as intellectual provenance and implementation validation. Never controls the chapter title or first screen. Full code lives in the replication archive.

### Ch. 0 — Start here: Target, Contribution, Uncertainty
Guided three-stage interaction on the canonical synthetic population (§9.1), one idea active at a time: (1) change who enters the sample → representation moves; (2) change how sampling occurs → uncertainty moves; (3) change effect heterogeneity and adjustment → the regression target moves. Reader routes at the end (descriptive → 1–3; regression/causal → 4–6; field guide → 7). Hosts or forward-references the "Four effective samples" box.

### Ch. 1 — What are we trying to estimate?
**Headline question: "How many Americans are housing-cost burdened?"** — 2024 ACS 1-year PUMS, housing + person files.

- **The puzzle (failure-first):** a person-level file with the household burden indicator attached to every person; `mean(housing_burden)` labeled "share of renter households that are burdened." Runs clean, looks plausible — but large households are counted repeatedly, so it is closer to a person-level quantity. Then the four-estimate table:

| Estimate | Unit | Weight | Interpretation |
|---|---|---|---|
| Unweighted housing records | Household | none | share of PUMS housing records |
| Household-weighted | Household | WGTP | share of renter households |
| Person-weighted | Person | PWGTP | share of people in burdened renter households |
| Child person-weighted | Child | PWGTP | share of children in burdened renter households |

These are different **estimands**, not competing estimators. Add severe burden (≥50%) and counts-vs-rates to complete the estimand family.
- **Core teaching:** estimand/estimator/estimate; unit of analysis; analytic universe and denominator choice; which weight corresponds to which unit; target/frame/sampled/respondent/analytic populations.
- **Substantive payoff:** show where the household-vs-person gap is largest — households with children, single-parent households, householder age, income groups, selected states. The insight: *housing affordability looks different measured as a problem of housing units vs a problem of people.*
- **Secondary box:** "What does it mean to say someone is poor?" — CPS ASEC official poverty vs SPM as an estimand-*definition* example; note the recent SPM threshold revisions as a live illustration of why releases and definitions must be versioned.
- **Classic box:** *"How an oversample produced a 26% unweighted poverty rate"* — reproduce the SHW PSID numbers (1968 wave, calendar-1967 family income; universe, poverty definition, weight variable, and SEO-oversample handling frozen in the chapter spec). Provenance + validation only; not an anchor, not in the launch field guides, not a primary pipeline.
- **Refs:** SHW (2015); Lundberg–Johnson–Stewart (2021); Census B25106 tables (validation target); ACS PUMS documentation.

### Ch. 2 — Where survey weights come from
**Headline question: "How does one phone-survey respondent become thousands of adults?"** — BRFSS, pinned release, outcome = frequent mental distress (14+ poor mental-health days) or uninsurance among adults under 65.

- **Core teaching:** real weights are $d_i \times g_i$: unequal selection probabilities; adults/phones per household; landline–cell dual-frame overlap; extreme-weight truncation; raking to demographic and phone-ownership margins. Gelman's "weights are not in general inverse probabilities of selection" is the pivot. The $f/a/w$ taxonomy. Diagnostics: CV(w), $n_{\text{Kish}}$, trimming bias–variance tradeoff.
- **Signature figure — the estimate waterfall:** raw sample estimate → design weighting → dual-frame adjustment → truncation → raking → final estimate, annotated with which demographic groups and phone types gained/lost representation. The waterfall explicitly distinguishes: stages exactly reconstructable from public variables; stages documented by the producer but not record-level reconstructable; and an illustrative raking reconstruction inside the widget. (No promise of record-level weight reconstruction.)
- **Coverage caveat as a lesson:** the 2024 BRFSS aggregate omits Tennessee. Either use a single large state, or define the target explicitly as "adults in participating jurisdictions," or pin a release with the desired coverage. Never silently label a 49-state aggregate "the U.S. adult population" — contemporary surveys have changing coverage, and *target population is not boilerplate*.
- **Optional box:** *"One survey, several legitimate weights"* — ANES 2024 (fresh cross-section + 2016–2020–2024 panel, pre/post waves, mode mixes, sample-specific weights) on a neutral outcome (trust in government): what goes wrong using a pre-election weight on post-election analysis, or treating the panel as a fresh cross-section.
- **Interactive:** `<WeightBuilder>` — raking/IPF on the synthetic population, live CV(w) and $n_{\text{Kish}}$; three-interpretation panel ($f_i/a_i/w_i$: same mean, three SEs).
- **Refs:** BRFSS 2024 weighting methodology (primary source); Gelman (2007) + discussion; Kish (1965); Valliant–Dever–Kreuter.

### Ch. 3 — Point estimation and design-based uncertainty
**Headline question: "Nearly half of adults have hypertension — but how many know it, treat it, and control it?"** — NHANES August 2021–August 2023 (post-pandemic redesigned sample).

- **The puzzle:** the hypertension cascade — prevalence (~48% of adults) → awareness → treatment → control (~21% of adults with hypertension, per the official data brief) — computed naively, then with the declared design. Where do the conclusions (not just the SEs) change?
- **Core teaching (the seed article, revised per §7, plus three v3 additions):**
  1. Correct inclusion weighting yields design-unbiased/consistent estimators *for specified finite-population quantities* (HT totals, Hájek means/ratios, weighted estimating equations); the exact claim depends on estimand and estimator.
  2. Strata, PSUs, DEFF, design df; df = #PSU − #strata is the common Taylor-linearization rule, not a universal law across replicate designs.
  3. **Domain estimation is unavoidable here** — awareness/treatment/control are estimated *among people with hypertension*: declare-then-subset vs incorrect row deletion; identical points, different variances.
  4. **Age standardization as a third weight family** ($s_a$): survey weights repair representation of the sampled population; standardization weights redefine the comparison population. Crude vs age-standardized prevalence, side by side.
  5. **DEFF is estimand-specific:** report DEFF separately for prevalence, awareness, treatment, control, and one subgroup — a dot plot that kills "the NHANES design effect" as a single number.
- **Design-changes-inference demonstration:** compare pre-pandemic vs 2021–2023 cascade estimates under (i) naive iid intervals, (ii) weight-only robust intervals, (iii) full strata/PSU intervals. The official analysis reports no significant change in awareness/treatment/control; the pedagogical question is whether a naive analyst would have claimed one.
- **Cross-survey interlude:** *"Weighting can repair representation; it cannot repair measurement."* Self-reported (BRFSS) vs measured (NHANES) hypertension/obesity — two representative surveys estimating different measurement constructs; weighting is not a universal cure for survey error.
- **Attached laboratory (not required reading): the ACS replicate-weight lab — "Which apparent state differences in rent burden are real?"** Continues the Ch. 1 application: state rent-burden estimates with WGTP; SDR variance with the 80 housing replicate weights; naive vs replicate intervals; point-estimate rankings vs ranking *uncertainty*; only comparisons supported by replicate-weight uncertainty highlighted. Interactive toggles: rank view / MOE view / frequency-in-top-group-across-replicates view. Substantive lesson: *a league table of point estimates looks far more definitive than the data justify.* Framing: replicate weights are *"the survey world's pre-packaged repeated sampling"* (BRR/Fay/jackknife/SDR/bootstrap are distinct procedures; conceptual bridge to bootstrap logic only). **Validation target:** reproduce an official PUMS documentation example and match a hand-implemented 80-replicate SDR formula against R `survey` to displayed rounding tolerance (not a published full-sample MOE — PUMS is a subsample of the full ACS). PUMA clustering appears only as an explicitly labeled incorrect shortcut.
- **Refs:** seed article; NCHS Data Brief 511 (hypertension); NHANES 2021–2023 analytic guidance; Lumley (2010); Heeringa–West–Berglund; Horvitz–Thompson (1952); Fay–Train (1995); Census ACS Design & Methodology ch. 12.

### Ch. 4 — What are we weighting for in regression?
*(SHW homage as chapter title.)*
**Headline question: "Do teleworkers earn more?"** — pooled 2024 monthly CPS, telework questions (added Oct 2022), with the appropriate ORG/earnings subsample for wages. Telework prevalence ≈ 23% of persons at work in 2024, ~40% among BA+ vs a few percent among less-than-HS — stratification that makes this the perfect setup for Ch. 5.

- **The estimand, stated up front:** an explicitly **descriptive adjusted wage contrast**, $\log(\text{earn}_i) = \alpha + \beta\,\text{telework}_i + X_i'\gamma + \varepsilon_i$ — *not* a causal telework effect. Selection into telework forecloses causal interpretation without stronger assumptions; the closing "does not establish" panel says so.
- **The empirical ladder:** (1) unweighted mean difference; (2) survey-weighted difference; (3) unweighted adjusted regression; (4) weighted adjusted regression; (5) logs vs levels; (6) occupation/industry adjustment; (7) influence diagnostics by occupation, state, education.
- **Core teaching (SHW §§III–IV rebuilt on this ladder):** the precision motive and the Dickens critique (kept primarily in the theory section and the `Dickens crossover` interactive on the synthetic population — the CPS application is not forced to reenact the grouped-data setting); endogenous vs exogenous sampling — when $w_i$ is required for consistency vs merely costly for precision; the DuMouchel–Duncan weighted-vs-unweighted contrast as a diagnostic that may signal *misspecification, endogenous sampling, leverage, or genuinely different estimands* — never an automatic verdict; Bollen et al. for the test landscape. The Moulton bridge stated correctly: **a special-case regression analogue of the clustering component of a design effect**, not an identity.
- **Weight choice within one survey:** general person weight for telework *prevalence*; ORG earnings weight for the *wage* regression — more useful than any generic pweight discussion.
- **Substantive output:** prevalence by education/occupation; raw gap; how much composition vs weighting moves it; which occupations/states drive divergence between specifications. Conclusion shape: *the observed telework wage gap is partly a difference in who can telework, and the adjusted gap depends on whether the target is the observed sample or the represented worker population.*
- **Classic box:** *Wolfers/Lee–Solon* — reproduce SHW Table 1 (WLS vs OLS, logs), the levels divergence, the drop-California diagnostic. A known case where logs, levels, weighting, and one influential state interact — evidence the implementation reproduces SHW, not the reason a 2026 reader cares.
- **Refs:** SHW (2015); Dickens (1990); DuMouchel–Duncan (1983); Wooldridge (1999, 2001); Bollen et al. (2016); Deaton (1997); Moulton (1990); BLS 2024 telework tables.

### Ch. 5 — Hidden weights under heterogeneous effects
**Headline question: "Whose telework wage gap?"** — *exactly the same CPS sample and model as Ch. 4*, so the reader learns no new dataset.

- **Core teaching:** the survey-weighted slope is design-consistent for the *population linear projection*, which under unmodeled heterogeneity is not the PATE; and equal case weights do not imply equal weighting of heterogeneous conditional effects (Angrist 1998; Aronow–Samii 2016; Słoczyński 2022). The provocation "there is no unweighted estimator" is kept but defined exactly that way. All theorems and visuals scoped to the binary-treatment setting in use.
- **The cell construction:** occupation × education (primary), occupation × age, industry × parent status. Per cell: telework prevalence, cell-specific adjusted contrast, population size, treatment-variance/overlap contribution.
- **The six-way comparison:** (1) unweighted OLS projection; (2) survey-weighted population projection; (3) population-weighted average of cell contrasts; (4) contrast among teleworkers (ATT-analogue); (5) among nonteleworkers (ATU-analogue); (6) the regression-effective sample composition — **showing signed weight / negative mass where relevant**, not just demographic shares.
- **The book's central empirical insight:** *a survey-weighted regression can represent the population correctly in the design sense while placing highly unequal implicit weight on heterogeneous conditional contrasts.* Occupations where nearly everyone or almost no one teleworks contribute little to the adjusted coefficient; overlap groups can dominate even when they are not the largest.
- **Interactives:** `<HiddenEffectWeights>` — the SHW plim machine (sliders $\pi, p, \sigma_0^2, \sigma_1^2, \beta_4$ → plim(OLS), plim(WLS), true PATE, knife-edge case) *plus* the live CPS effective-sample view; Słoczyński ATT/ATU decomposition (hettreatreg logic in Python, unit-tested against published examples). Interpret, don't adjudicate.
- **Refs:** SHW §V; Angrist (1998); Aronow–Samii (2016); Słoczyński (2022); Chattopadhyay–Zubizarreta (2023).

### Ch. 6 — Sampling design, assignment design, and clustering
**Headline question: "Millions of survey records, dozens of policy shocks."** — **Medicaid expansion and uninsurance among low-income nonelderly adults** (ACS or CPS person files + state-year expansion panel). *Frozen only after the audition (§5.2); backups ranked: (2) state minimum wages and lower-tail earnings via CPS ORG (reuses Ch. 4–5 pipeline; complicated by local minimums, tipped workers, continuous treatment); (3) paid family leave and maternal employment (intuitive, but few treated states — pedagogically useful fragility, heavier identification burden).*
- **Two-stage exposition (cleanest):** (1) construct state-year uninsured rates with correct survey weights and variance; (2) study how those rates move around expansion, with inference clustered at the state. This cleanly separates: uncertainty in each state-year survey estimate; uncertainty from policy variation across states; and person records vs ~50 policy units.
- **Core teaching:** AAIW (2023) — clustering is a sampling-design or assignment-design question, not "correlated errors" folklore; answers "why state but not gender?" and "why not in an experiment?". Survey PSU = sampling-design case; policy variation = assignment-design case. Guidance stated fully: *identify every sampling or assignment mechanism that induces common uncertainty; in a nested hierarchy the coarsest relevant level typically governs conventional clustering; non-nested mechanisms may require different or multiway treatment; the sampled-cluster fraction and the inferential target both matter.* Few-clusters medicine: wild cluster bootstrap, CRV3, design df.
- **Identification guardrail (mandatory):** do not present a conventional TWFE coefficient as established causal identification. Either use a modern staggered-adoption estimator, restrict to a transparent cohort/window, or state explicitly that identification is taken as given and the chapter's purpose is *inference conditional on the design*. The chapter must not open an unaddressed DiD-methodology front. The closing "does not establish" panel is strictest here.
- **Empirical SE ladder:** HC1 on person records / cluster-PSU / cluster-state / wild cluster bootstrap at state — with the choice derived from design, explicitly *not* from which SE is largest.
- **Interactive:** `<ClusterDesignWorksheet>` — an inference diagnostic (target, sampling mechanism, assignment mechanism, nesting, fixed effects, sampled-cluster fraction) that outputs *a recommendation plus its assumptions and at least one sensitivity alternative*; never a bare green checkmark.
- **Refs:** AAIW (2023 QJE; 2020 Econometrica); Cameron–Miller (2015); MacKinnon–Nielsen–Webb (2023); BDM (2004); the chosen staggered-DiD reference if used.

### Ch. 7 — Field guide (the payoff)
- (a) Print-ready SVG worksheets: "Descriptive statistic," "Causal effect," "Choosing SEs" — assumptions + alternatives, mirroring Ch. 6's worksheet philosophy.
- (b) **Four release-specific survey guides at launch**, generated and tested from survey-prep `design.json` manifests, each with pinned release, design summary, declaration snippets (`svy` / Stata `svyset` / R `survey`), replicate method, design df, known traps, and a "last verified" field. **Launch set: ACS 2024 1-year PUMS; NHANES Aug 2021–Aug 2023; CPS 2024 monthly/ORG + pinned ASEC; the pinned BRFSS release.** ANES 2024 is the first subsequent guide; PSID is deferred with its box.
- (c) Software patterns: groupby-for-exploration / declared-design-for-inference; `svy` ↔ R `survey` ↔ Stata rosetta; `pyfixest` weights + CRV patterns.
- (d) Referee/advisor checklist: ten pre-submission questions, each mapped to a Ledger field.

### Appendices
- **A.** Notation (§2.2) + master crosswalk table (superset of the seed article's table).
- **B.** Scoped derivations: Taylor linearization vs CRV1 (conditions for near-equivalence); Moulton as special case of the clustering DEFF component; SHW eq. (6)–(9); the four effective-sample definitions.
- **C.** Reproducibility: manifests, script index, package versions, tiers (§5.4); the outcome-audition disclosure table (§5.2).

---

## 5. Empirical program

### 5.1 Four data systems, used deeply (replaces the v2 anchor table)

| Anchor | Dataset (pinned release) | Chapters | Empirical question and role |
|---|---|---|---|
| 1 | **2024 ACS 1-year PUMS, housing + person files** | 1; Ch. 3 lab; 6 (if ACS chosen); 7 | "How many households, people, and children experience housing-cost burden?" Units, populations, WGTP vs PWGTP, replicate-weight state comparisons; insurance variables for the policy chapter. Pin 2024 — do not build against an anticipated 2025 release. |
| 2 | **BRFSS, pinned release + explicit target geography** | 2; 7 | "How does a phone-survey respondent become a population estimate?" Dual-frame design, truncation, raking, weight diagnostics; frequent mental distress or health access. |
| 3 | **NHANES Aug 2021–Aug 2023** | 3; 7 | "Who has hypertension, and who has it controlled?" Strata, PSUs, domains, design df, age standardization, estimand-specific DEFF. |
| 4 | **CPS 2024 monthly/ORG + pinned ASEC** | 4–5; 6 (backup/primary); 1 (poverty box); 7 | "Do teleworkers earn more, and whose contrast does the regression summarize?" Explicit weights and weight choice; OLS/WLS diagnostics; heterogeneous contrasts; regression-effective samples. |
| Supporting panel | **State Medicaid-expansion (or backup policy) panel** | 6 | "Why do millions of observations yield only dozens of policy shocks?" Sampling vs assignment uncertainty; clustering level; few-cluster methods. |

**Classic replications:** the 1968 PSID and Wolfers applications remain as compact classic-replication boxes and downloadable validation notebooks. They are not headline anchors, launch field guides, or primary pipelines.

This is *simpler* than v2's program: PSID and Wolfers pipelines are removed from the critical path, and each contemporary dataset does multiple jobs.

### 5.2 The empirical audition (new, required before chapter specs are frozen)

Outcomes are not chosen by intuition alone. One screening script per candidate outcome generates:

| Diagnostic | Purpose |
|---|---|
| Unweighted estimate | plausible wrong answer |
| Correctly weighted estimate | point-estimate effect of representation |
| Naive SE | common incorrect uncertainty |
| Full-design SE | design effect |
| CV(w), $n_{\text{Kish}}$ | weight concentration |
| Domain-correct vs row-deletion SE | subpopulation lesson |
| Largest demographic contribution shifts | who is reweighted |
| Official benchmark discrepancy | validation |
| One important subgroup pattern | substantive payoff |
| Required caveats | pedagogical burden |

An application is retained when at least one central technical correction has a **visible payoff** — it meaningfully changes the point estimate, the inference, the described population, or the substantive interpretation. Outcomes are *not* selected merely for the largest weighted–unweighted gap (cherry-picking); the substantive question must be independently worth answering. A disclosure table of audited candidates appears in Appendix C. The Ch. 6 policy application (Medicaid vs minimum wage vs PFL) is frozen only after a compact three-way audition.

### 5.3 `data_manifest.yml` (one per dataset, before any analysis code)

```
dataset:
release:
source:
access_type: public | registration | restricted | proprietary
redistribution:
raw_checksum:
analytic_sample_definition:
weight_variables:
design_variables:
benchmark_target:
coverage_notes:        # e.g., BRFSS 2024 excludes TN; ASEC SPM revisions
```

### 5.4 Reproducibility tiers (stated per result)

- **Tier 1 — publicly reproducible:** public acquisition + checksums + scripts (ACS, BRFSS, CPS, NHANES public files).
- **Tier 2 — reproducible after registration** (PSID box; some restricted supplements).
- **Tier 3 — reproducible only from released aggregates** (none in the first edition).

The Tigris store provides author-side reproducibility; the tiers are the reader's promise.

---

## 6. Disposition of the seed article

The seed article becomes Ch. 3's core teaching material with: the §7 corrections applied; the NHANES hypertension cascade replacing generic income/BMI examples; domain estimation and age standardization added; and the ACS lab attached. Its crosswalk table moves to Appendix A as the master version.

---

## 7. Required corrections to earlier formulations (binding on all prose and UI text)

1. **"Weights get the point estimate; the design gets the uncertainty"** — qualify: the weights help define the estimator; the sampling design *and the weight-construction procedure* determine repeated-sampling variance (final weights are themselves estimated; replication procedures that reproduce the weighting steps handle this).
2. **"HT estimands" — dropped.** Correct inclusion weights give design-unbiased/consistent estimators for *specified finite-population quantities*; the claim depends on estimand and estimator.
3. **"DEFF ≡ Moulton" → Moulton is a special-case regression analogue of the clustering component of a design effect.**
4. **Replicate weights = "pre-packaged repeated sampling,"** not a bootstrap; BRR/Fay/jackknife/SDR/bootstrap are distinct.
5. **Clustering level:** the "coarser level" mnemonic applies to nested hierarchies inside the full AAIW statement (Ch. 6 core).
6. **"There is no unweighted estimator" → equal case weights do not imply equal weighting of heterogeneous conditional effects.**
7. **MRP is not defined by Bayesian software** (multilevel model + cell prediction + poststratification + uncertainty propagation; frequentist mixed models qualify). Recorded for the deferred essay.
8. **Benchmarks are not truth** — label toggles "external benchmark" / "high-precision benchmark" / "simulated population truth"; benchmark surveys have their own sampling and measurement error.
9. **Causal restraint:** Ch. 4–5's telework contrast is descriptive; Ch. 6's policy coefficient is inference-conditional-on-design unless a modern staggered estimator is used. The "does not establish" panel enforces this.
10. **Coverage honesty:** target populations reflect actual coverage (BRFSS/TN; ASEC/SPM revisions); never silently labeled national.

---

## 8. Deferred to standalone advanced essays (*"When weighting is not enough"*)

- **MRP and poststratification** — MRP replaces fixed explicit weights with model-dependent implicit weights; validated against an *external benchmark* or scored against simulated truth on the synthetic population.
- **The big-data paradox (Meng)** — $n_{\text{DDC}}$ vs precision-based effective sizes; Bradley et al. (2021) as demonstration.
- **ANES 2024 full guide** (the Ch. 2 box graduates first).
- **DHS / international cluster designs** — pending access and redistribution review.
- **NielsenIQ panel-vs-census contrast** — only if publishable at nonconfidential aggregate level.
- **Propensity-score/balancing weights** — out of scope except one margin note (the same cut SHW made).

---

## 9. Interactive architecture

### 9.1 One canonical synthetic population
Seeded, versioned, reused across all interactives: individuals nested in neighborhoods; realistic age × education × income structure; one oversampled group; cluster-level outcome variation; heterogeneous treatment effects; known margins. Powers SRS/stratified/clustered draws, raking, sampling distributions, explicit-vs-implicit weights, assignment at individual vs neighborhood level, trimming — and supplies "simulated population truth" wherever a widget scores estimators. Makes the booklet cumulative rather than a demo collection.

### 9.2 First-edition components (six)
1. `<AnalysisLedger>` — consumes result JSON.
2. `<PopulationSampler>` — staged Ch. 0 hero + Ch. 3 sampling-distribution views.
3. `<WeightBuilder>` — Ch. 2 raking/trimming/diagnostics + the estimate-waterfall view.
4. `<DesignUncertaintyExplorer>` — Ch. 3 DEFF/df/domain views on real survey metadata; hosts the ACS-lab ranking-uncertainty toggles.
5. `<HiddenEffectWeights>` — Ch. 5 signature widget (SHW plims + signed $\omega_i$ on live CPS cells).
6. `<ClusterDesignWorksheet>` — Ch. 6 diagnostic instrument.

Demoted: replicate-weight heatmap (static figure in the lab initially); Dickens crossover (instance of a generic parameterized chart); MRP/Meng widgets (deferred with their essays); `<DialectTable>` is styling.

### 9.3 Implementation constraints (part of definition of done)
Deterministic seeded randomness; keyboard controls; reduced-motion mode; non-color encoding of meaningful distinctions; descriptive alt text; static canonical state (SVG fallback for no-JS/social cards); a "what is held fixed?" note; a "predict first" prompt; URL-serializable parameters where useful.

---

## 10. Build plan for Claude Code

### Phase 0 — Editorial and statistical contract (nothing stubbed)
Freeze: title/subtitle; chapter list (§4); terminology and notation (§2.2); scope exclusions (§8); Ledger schema; canonical synthetic population (generator + seed + version); the four `data_manifest.yml` files; result-artifact schema (§10.3); citation/source policy; accessibility requirements (§9.3). **Run the empirical auditions (§5.2)** for the Ch. 1–5 outcomes and the three Ch. 6 policy candidates; Vishal signs off on the audition results before any chapter spec is written. Output: `CONTRACT.md` + audition tables at the booklet root.

### Phase 1 — One complete vertical slice
**Chapter 1 (ACS housing burden)** end to end: raw data → analytic file → validated estimates → result JSON → prose with injected numbers → the four-estimand interactive with static fallback → mobile layout → citations → automated tests → the PSID classic box. (Ch. 1 replaces Ch. 3 as the slice: simpler design machinery, richest estimand lesson, and it exercises the two-tier headline/box structure immediately.) Do not generalize shared component architecture until this slice reveals what is genuinely reusable.

### Phase 2 — Core spine
Chapters 3, 4, 5 under the Phase 1 contracts (Ch. 4–5 share one CPS pipeline by construction).

### Phase 3 — Weight construction, lab, and field guide
Chapter 2 (BRFSS); the ACS replicate-weight laboratory; the four release-specific guides (Ch. 7) generated from design manifests.

### Phase 4 — Clustering
Chapter 6 last among the core: it depends on stable sampling-design language and on the frozen policy audition, and it is the chapter most at risk of automated implementation flattening design arguments into a rule engine. The worksheet's outputs are reviewed against AAIW claim-by-claim; the identification guardrail (§4, Ch. 6) is checked explicitly.

### Phase 5 — Advanced essays
Sequenced by reader feedback on the core.

### Per-chapter workflow: curated source packets
CC never "re-fetches and reads the literature" unsupervised. Each chapter gets a human-approved `chapter_spec.md`: learning objectives; **allowed claims** (with §7 baked in); equations; conditions and caveats; required citations; the frozen empirical target (universe, outcome definitions, weights, releases — e.g., PSID box: 1968 wave / calendar-1967 income / SEO handling); interactive behavior; the two closing panels + caveat line; **common misstatements to avoid**. Vishal reviews each spec before drafting (explicit confirmation at each fork).

**Per-chapter definition of done:** manifests present; audition passed; analysis runs clean from raw inputs; all prose numbers injected from artifacts; sentinel validations pass (§10.2); interactives meet §9.3; closing panels present; internal links, Ledger fields, and estimand statements audited; citations resolve.

---

## 11. Validation contract

### 11.1 Pin all defaults
Weight normalization; missing-value rules; subpopulation handling vs row deletion; lonely-PSU options; FPCs; degrees of freedom; variance type; confidence level — every choice stored *in the result artifact*, never implicit.

### 11.2 Sentinel validation
Per chapter: two or three key estimates validated against an independent package (R `survey` for design-based results; `fixest`/published tables for regressions); one result validated against producer documentation or official tables where available (ACS B25106 for Ch. 1; NCHS Data Brief 511 for Ch. 3; BLS telework tables for Ch. 4); Monte Carlo checks for each interactive's mathematical claims (seeded, on the synthetic population); unit tests for every displayed formula. All prose numbers are generated; not every number needs three implementations.

### 11.3 Result-artifact schema (single source of truth for Ledger, tables, prose, figures)

```
estimate:
standard_error:
degrees_of_freedom:
confidence_interval:
estimand_id:
estimator_id:
weight_specification:
variance_specification:
analytic_n:
weighted_population_total:
data_release:
data_checksum:
code_version:
```

---

## 12. Title and remaining decisions

**Title (recommended):** **Weights, Design, and Estimands** — *A Field Guide for Applied Researchers*, with **"What Are We Weighting For?"** as the Ch. 4 title.

Decisions closing Phase 0:

1. **Confirm title** (blocks URLs, metadata, branding).
2. **Sign off the auditions** (§5.2): Ch. 1–5 outcome choices and the Ch. 6 policy pick (prior ranking: Medicaid expansion > minimum wage > PFL).
3. **Pin releases:** ACS 2024 1-year PUMS; NHANES Aug 2021–Aug 2023; CPS 2024 monthly/ORG + which ASEC; which BRFSS release and target geography (single large state vs participating-jurisdictions framing).
4. **Ch. 6 dataset:** ACS vs CPS for the insurance outcome (decide with the audition; ACS wins on precision, CPS on pipeline reuse).
5. **Publication cadence:** ship Phase 1–2 chapters as linked articles immediately vs hold for the full edition. (Lean: ship incrementally; the essay structure already assumes it.)
6. **Confirm scope exclusions** (§8), including PSID's demotion to a box and the propensity-score margin-note-only rule.

---

## 13. Core reference list

- Solon, Haider & Wooldridge (2015), "What Are We Weighting For?" *JHR* 50(2).
- Abadie, Athey, Imbens & Wooldridge (2023), *QJE* 138(1); (2020), *Econometrica*.
- MacKinnon, Nielsen & Webb (2023), *J. Econometrics*; Cameron & Miller (2015), *JHR*; Bertrand, Duflo & Mullainathan (2004), *QJE*.
- Moulton (1990); Dickens (1990); DuMouchel & Duncan (1983).
- Gelman (2007), *Stat. Sci.* + discussion; Little (2004); Gelman & Little (1997).
- Angrist (1998); Aronow & Samii (2016), *AJPS*; Słoczyński (2022), *REStat*; Chattopadhyay & Zubizarreta (2023).
- Bollen, Biemer, Karr, Tueller & Berzofsky (2016), *Annu. Rev. Stat. Appl.*; Lundberg, Johnson & Stewart (2021), *ASR*.
- Lumley (2010); Heeringa, West & Berglund; Kish (1965); Horvitz & Thompson (1952); Fay & Train (1995); Wooldridge (1999, 2001, 2007).
- **Producer/primary sources (pinned per release):** Census ACS Design & Methodology ch. 12 + PUMS documentation + B25106 tables; CDC BRFSS 2024 weighting methodology + data documentation; NCHS NHANES 2021–2023 analytic guidance + Data Brief 511; BLS 2024 telework tables; Census CPS ASEC documentation + SPM revision working paper.
- *(Deferred essays:)* Meng (2018), *Ann. Appl. Stat.*; Bradley et al. (2021), *Nature*.
