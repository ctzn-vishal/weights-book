# Identification: ideas for a strong section

## Can these data identify the quantity? A fourth question for the book, with replication labs on public data

- **Book:** *Weights, Design, and Estimands — A Field Guide for Applied Researchers*
- **Date:** September 17, 2026
- **Basis:** Current manuscript at Git HEAD `db6bbfe`; [the development memo](BOOK_IMPROVEMENT_IDEAS.md) of September 14, 2026; the author's stated direction: a collection of interrelated ideas on empirical research and robust analysis with field data, descriptive and causal.
- **Stage:** Brainstorm. Candidate data sources were checked at the source-page level today where marked "verified"; no file was downloaded, no result computed, no license read in full.
- **Recommendation:** Add identification as the book's fourth question, "Can these data identify the quantity?", taught through a single missing-data model that covers description and effects, and through replication labs that each make the same four moves. Choose the first labs so they run on surveys already in the pipeline.

The development memo asks for one causal replication. This memo asks what a whole identification section would be, now that the book is becoming a set of interrelated ideas rather than a weights primer. The two are compatible: the memo's Trip.com lab is one lab in the structure below.

**Jump to:** [where it sits](#2-where-identification-sits-in-the-book) · [structure](#3-structural-options) · [spine](#4-the-spine-four-chapters) · [lab template](#5-the-lab-template-replicate-ledger-remove-redefine) · [cases](#6-case-candidates) · [links between ideas](#7-the-interrelated-ideas-graph) · [schema](#8-ledger-and-artifact-extensions) · [components](#9-components-few-and-shared) · [robustness](#10-robust-to-what) · [first build](#12-a-bounded-first-build) · [sources](#13-sources-checked-today).

---

## If you only read one section

The book already asks who a number describes (Target), how each record counts (Contribution), and what could have come out differently (Uncertainty). Identification is the question between the first and the second: given what is missing from the data and why, does the distribution of what was observed determine the target at all, and under which assumption? The book answers that question today in scattered places: the two turnout conventions in Chapter 1, the calibration margins in Chapter 2, the measured-versus-reported interlude in Chapter 3, the unsupported cells in the weight builder, the "what the design assumes" callout in Chapter 6. A strong identification section collects those into one model, adds the causal half, and gives every identifying assumption in the book a numerical "without it".

The distinctive niche is identification **with survey data**. Almost every causal-inference text uses experimental or administrative files with no design weights and no replicate variance. Almost every survey text stops at description. This book already has both halves in one pipeline. A lab that runs a regression discontinuity with `PERWT` and successive difference replication, or a synthetic control on Current Population Survey (CPS) cells whose sampling noise is visible, is something readers cannot get elsewhere.

| Priority | Idea | Why it earns space | Main dependency |
|---|---|---|---|
| First | One spine chapter: identification as a missing-data problem, for description and for effects | Turns the book's scattered caveats into one model; makes weights and identifying assumptions the same kind of object | Existing turnout, calibration, and measurement material; one new component |
| First | A fixed lab template: replicate, ledger, remove the assumption, redefine the sample | Makes every case comparable and keeps labs from becoming a methods catalogue | Ledger schema extension (section 8) |
| First | Mariel boatlift on CPS via IPUMS | Sample definition as identification; one treated unit; survey coverage change inside a famous causal dispute; already-licensed data | IPUMS CPS extract; Peri–Yasenov replication package (verified) |
| First | Medicare at 65 in NHIS and ACS | Regression discontinuity with survey weights and replicate variance; discrete running variable; "what else changes at 65" | NHIS and ACS already in the pipeline |
| First | Sensitivity on existing results: Manski bounds on turnout, HonestDiD on Medicaid, Oster on the WFH contrast | Gives the book's own numbers a "without the assumption" value before any new dataset arrives | Existing artifacts plus small verified calculations |
| Next | One randomized study with noncompliance or attrition (Trip.com or the Michigan social-pressure experiment) | Offer versus receipt; attrition bounds; assignment as both identification and repetition | Package audit (memo §4.1); ISPS archive audit |
| Next | Angrist–Evans on IPUMS 1980, extended to ACS 2024 | Instrumental variables with the book's own data; a first stage that has weakened over forty years | IPUMS USA extract |
| Later | NSW, deworming or Progresa, Proposition 99, China shock, Hillstrom email test, author-original cases | Each adds one identification family or one audience | Separate auditions |

**Do not build the whole section at once.** Section 12 gives a bounded first build.

---

## 1. What "strong" should mean here

Five tests. A draft of the section passes if:

1. For any result in the book, a reader can say which feature of the observed data equals the target and under what named assumption, and whether that assumption was made true by design or adopted by argument.
2. Every identifying assumption the book states has a numerical companion: the identified set without it, or the value of a sensitivity parameter at which the conclusion changes. A caveat in a callout is not enough.
3. The same machinery serves descriptive and causal targets. Nonresponse and confounding are treated as two reasons a cell is missing, with different remedies and the same logic.
4. Every lab reproduces a published number from public data before it extends anything, and records what it could not reproduce.
5. Robustness is organized by what a change changes: the target, the assumption, the estimator, or the repetition. The memo's four-way classification becomes the section's reporting rule.

A section that adds estimators without passing these tests would lengthen the book without changing what readers can do.

---

## 2. Where identification sits in the book

### The definition, in the book's own terms

Chapter 1 defines the target: population, outcome, unit, time, comparison. Identification asks whether the observed data determine that target. Formally, the target is identified if it is a function of the distribution of the observed data under the stated assumptions. It is partially identified if the assumptions restrict it to a set. It is unidentified if the data are silent.

This is the second step of the memo's practical sequence, and it should be named as the book's fourth question:

> **Target.** What quantity? **Identification.** Can these data determine it, and under what assumption? **Contribution.** How does each record enter the estimator? **Uncertainty.** What could have come out differently?

The three-word mnemonic can stay for the weights material. Identification is not a fourth weight family and should never appear in a table beside design, calibration, and regression weights. It is the question of whether a weight, or anything else, can do the job.

### One model: reasons a cell is missing

Think of the full data matrix for the target population: every person, every outcome, every treatment version. A cell can be unobserved for five reasons. The book already handles four of them.

| Why the cell is missing | Assumption that fills it | What makes the assumption credible | What you have without it | Where the book already touches it |
|---|---|---|---|---|
| Not in the frame | The frame covers the target, or the excluded part is like the covered part on the outcome | Frame construction; coverage studies | Bounds from the excluded share and the outcome's range | Ch 1 turnout denominators; Ch 2 BRFSS frames |
| Not sampled | Sampling was by a known design | The design itself | Nothing to fill: design weights are exact | Ch 2 design weights |
| Did not respond | Missing at random given the weighting variables | Response modeling; calibration to known margins | Manski bounds; sensitivity to an assumed rate among nonrespondents | Ch 1 two turnout conventions; Ch 2 raking |
| Not measured, or mismeasured | The report equals the quantity, or the error is known | Validation against records or measurement | Bounds from validation rates; misclassification correction | Ch 3 measured versus reported hypertension; Ch 4 top-coded wages |
| Not assigned to that treatment version | Assignment independent of potential outcomes, unconditionally or given covariates, or a comparison group whose trend stands in | Randomization; a documented mechanism; an argued comparison | Bounds; breakdown values for the assumption | Ch 6 parallel trends; Ch 5 overlap; Ch 7 "whose decision was it?" |

The table is the section's organizing device. A survey weight is a missingness assumption written as a number: calibration to age-by-sex margins asserts that within a margin cell the respondents stand for the nonrespondents. A propensity weight is a different missingness assumption written the same way. Randomization is the case where the assumption is true by construction. Once that is said, the book's weights chapters and its identification chapters are one argument.

### Descriptive identification is real and undertaught

Most identification teaching starts with treatments. This book can start with description, because it already has the cases:

- Turnout among people who did not answer the voting question (Ch 1). The two conventions are two points in an identified set; the memo's §5.1 sensitivity surface is the identified set drawn out.
- Calibration margins (Ch 2). The weight repairs representation on the margins used and assumes it on everything else.
- Measured versus reported hypertension (Ch 3). The National Health and Nutrition Examination Survey (NHANES) identifies prevalence by measurement; the National Health Interview Survey (NHIS) identifies awareness by report. They answer different targets, and the gap between them is an identification fact, not a survey error.
- Top-coded wages (Ch 4). The mean above the cap is not identified without a distributional assumption.
- Empty cells (Ch 2 and Ch 5). A target cell with no support is unidentified; the interface should say so rather than merge.
- Trends from repeated cross-sections (memo §5.5). A change over time is identified for the population only if the frame and measurement were stable.

Manski's "law of decreasing credibility", that stronger assumptions buy sharper conclusions at the price of credibility, is the anchor for the descriptive half and fits the book's target-first discipline. Meng's data defect correlation, already in the bibliography, is its large-sample version: a huge nonrandom sample can be worse than a small random one.

### Causal identification is the same question as Chapter 7's

Chapter 7 asks "whose decision was it?" to choose the repetition behind a standard error. Identification asks the same question about the point estimate. The mechanism that made the variation in the regressor both identifies the effect and defines the repetition. That is the bridge that makes an identification section belong in this book rather than beside it: one question, two uses, and both answered by reading the design.

---

## 3. Structural options

### Option A: Part IV in this book

Add "Part IV · Can these data identify it?" after the field guide, with chapters 9 through 11 (or 12) and labs. Routes stay stable; the field guide remains the reference destination.

**Benefit:** readers who follow the "intervention effect" route arrive somewhere. **Cost:** the book grows by roughly half. The memo warned against a full causal-inference text inside Part II; the author's new direction loosens that constraint, but the risk of a catalogue remains.

### Option B: a sibling volume on the shared platform

Keep this book as the weights volume. Build identification as a second volume that shares the `Fact`, `Ledger`, artifact, and citation pipeline, the synthetic population, and the reading routes. Cross-link at the section level.

**Benefit:** fits "a collection of interrelated ideas" and keeps each volume readable in a sitting. **Cost:** two things to maintain; readers may not find the second.

### Option C: identification cards inside existing chapters plus one synthesis chapter

Add the memo's analysis card, with a claim-type field, at each chapter's first result, and one closing chapter that unifies them.

**Benefit:** cheapest. **Cost:** no lab, so no reader watches an identification argument built from a mechanism.

### My choice

Write it as Option A with Option B's packaging discipline. Give the part its own TOC entry, stable slugs with an `id-` prefix, its own artifact namespaces, and no dependence on chapter numbers in prose, so it can be split into a sibling volume later without breaking a single link. Add Option C's cards in the existing chapters regardless; they cost little and make the fourth question visible before Part IV. The memo's Option B (four parts, with "When can a contrast describe an effect?" as a part) becomes the natural second-edition shape once Part IV exists.

Scope rule for the part: teach identification families through replications, one lab per family, with the "remove the assumption" move in every lab and one shared sensitivity component. No derivations of estimators; cite and use the packages.

---

## 4. The spine: four chapters

Working numbers assume Option A. Titles state the question.

### Chapter 9 · Can these data identify the quantity?

The descriptive half, built almost entirely on data already in the pipeline.

1. **The missing-data matrix.** The table from section 2, drawn on the synthetic population: toggle a reason for missingness and watch the target go from a point to a set to nothing.
2. **Frame and response: turnout.** Manski bounds on 2020 CPS turnout, extending the memo's §5.1 sensitivity surface into an identified set with the two conventions marked as points inside it. The racial gap's identified set is the payoff.
3. **The big-data paradox.** The Delphi–Facebook COVID vaccination survey against the CDC benchmark, from Bradley et al. (2021), already cited: a weekly sample of roughly 250,000 that missed by double digits beside a poll of about a thousand that did not. Public aggregates suffice; no microdata.
4. **Measurement: validated turnout.** Self-reported versus record-validated turnout in the Cooperative Election Study; overreport concentrated among the educated and engaged. Connects to Chapter 1's turnout and to the Michigan experiment in Chapter 10, whose outcome is a record, not a report.
5. **Support.** The empty-cell lesson from memo §5.3, framed as unidentification.
6. **Trends.** Repeated cross-sections and frame changes (memo §5.5); the 1980 CPS coverage change that reappears in the Mariel lab.

The chapter introduces the **assumption dial** (section 9) on the turnout case and uses it in every later lab.

### Chapter 10 · Identification by design

1. **Assignment as identification and as repetition.** Randomization makes the missingness assumption true; the same mechanism defines the standard error (Chapter 7's question, now used twice).
2. **Offer versus receipt.** Intention-to-treat, uptake, and the complier effect, with the compliance-flow figure.
3. **Attrition.** Outcomes that vanish when a person leaves; Lee trimming bounds as Chapter 2's trimming idea turned into an identification tool.
4. **Clusters and spillovers.** Assignment at the school or village and effects on the untreated; why clustering does not repair interference.
5. **Whose effect.** The trial population, and why random assignment says nothing about generalization (memo §4.6 restraint).

Labs: one randomized study with noncompliance (Trip.com or Michigan social pressure); Oregon as the instrumental-variables version; deworming or Progresa in reserve for spillovers.

### Chapter 11 · Identification by assumption

One section per family, each ending with what the estimate is without the assumption.

1. **Selection on observables.** Overlap, balance, and weighting as a missingness assumption; the National Supported Work benchmark (memo §4.3).
2. **Comparison over time.** Chapter 6's Medicaid design, now with a HonestDiD relative-magnitude breakdown value: how large a post-period departure from the largest pre-period gap would erase the effect.
3. **Thresholds.** Medicare at 65 in NHIS and ACS: coverage jumps at the threshold, the running variable is age in whole years, and retirement changes at the same age. Bandwidth, polynomial, and donut sensitivity on the dial.
4. **Instruments.** Angrist–Evans on IPUMS 1980: sibling-sex composition, the first stage, compliers, and the exclusion argument; the same extract on ACS 2024 to show a first stage that has shrunk.
5. **One treated unit.** Mariel on CPS and Proposition 99 on state cigarette sales: synthetic controls, placebo-in-space as Chapter 6's placebo laws in another guise, and sample definition as the identification decision.

### Chapter 12 · Robust to what? (optional; could fold into closings)

The four kinds of change, the reporting rules (section 10), the example-selection record, and a template for the identification paragraph of a methods section.

---

## 5. The lab template: replicate, ledger, remove, redefine

Every lab makes four moves in the same order. The template is what keeps a dozen labs from becoming a dozen tutorials.

| Move | What happens | Artifact produced |
|---|---|---|
| **Replicate** | Reproduce one primary published number from the public package or the book's own extract; record any discrepancy and its cause | Facts with an `external benchmark` comparison; a reproduction note |
| **Ledger** | Write the Analysis Ledger with the identification block: claim type, observed feature, named assumption, made true by design or by argument, falsification checks and what they cannot detect | Ledger with `identification` (section 8) |
| **Remove** | Report the estimate without the key assumption: an identified set, or the sensitivity parameter's breakdown value | A `bounds` figure; a `sensitivity` fact |
| **Redefine** | Change the sample rules or target definition and classify each change as target, assumption, estimator, or repetition | A sample-rules table; a comparison ledger (memo §6.1) |

Chapter 6 already makes moves one, two, and four: it reproduces a two-by-two, writes two ledgers, and reports what adding back the prior-coverage states or dropping the small-program states does to the coefficient. It lacks move three. Adding HonestDiD to Chapter 6 is the cheapest demonstration that the template fits the existing book.

The template also fixes the tone for contested cases. Mariel and deworming each have a published reanalysis. The lab reports each side's sample rules and assumptions in the same ledger format and lets the reader see which move separates them. No verdict on who was right.

---

## 6. Case candidates

Grouped by fit with the pipeline, then by teaching job. "Verified" means the data source page or repository record was found today; "not verified" means the item rests on memory. Section 13 lists the pages found.

### 6.1 Novel replications on surveys already in the pipeline

These are the highest-value cases because the extracts, weights, replicate variance, and declaration code already exist, and because no other text runs these designs with the survey machinery intact.

**Mariel boatlift on CPS (Card 1990; Borjas 2017; Peri and Yasenov 2019; Clemens and Hunt 2019).**
- *Teaching job:* sample definition as the identification decision. The published estimates disagree in sign, and the disagreement traces to who is in the sample (age, education, sex, ethnicity), which comparison cities, and a 1980 change in CPS coverage of low-skill Black men that shifted Miami's sample composition. That last point is a Part I lesson (frame and measurement) sitting inside a Part IV dispute.
- *Also teaches:* synthetic control; one treated unit; sampling noise in tiny CPS cells, which is visible with the book's replicate machinery in later years and must be argued for earlier ones.
- *Data:* IPUMS CPS (already licensed) for the ASEC; the NBER merged outgoing-rotation files for hourly earnings; the Peri–Yasenov replication package on Harvard Dataverse (verified). Check which years IPUMS carries hourly earnings before committing.
- *Risks:* politically charged; must present all sides in the same format; the small-cell inference is subtle.
- *Verdict:* first lab of the part. It uses the book's data, its variance tools, and its ledger discipline, on a case every reader has heard of.

**Medicare at 65 in NHIS and ACS (Card, Dobkin, and Maestas 2008, coverage results).**
- *Teaching job:* regression discontinuity with survey weights and replicate variance. Coverage jumps at 65; the public-use running variable is age in whole years, so the design is a discrete-running-variable RD and the local-randomization framing applies; retirement and other transitions at 65 challenge the exclusion of everything except Medicare.
- *Data:* NHIS and ACS, both in the pipeline. The utilization results used restricted hospital data and are out of scope.
- *Risks:* the paper's exact NHIS years and age coding must be reconstructed; the ACS asks about coverage type, so "any coverage" and "Medicare" are separate targets.
- *Verdict:* second lab. Small, novel, and entirely on existing data.

**ACA dependent coverage at 26 (ACS and NHIS).**
- *Teaching job:* an age threshold and a policy date together; RD in age, difference in differences across years; Chapter 6 already sets its window after this provision.
- *Verdict:* a short companion to the Medicare lab or an exercise; not a full lab.

**Angrist–Evans 1998 on IPUMS USA 1980, extended to ACS 2024.**
- *Teaching job:* instrumental variables as a missingness assumption about a subpopulation (compliers); first stage, exclusion, monotonicity; a first stage that has weakened as fertility fell. The book already uses IPUMS USA with `PERWT`.
- *Data:* IPUMS USA 1980 and 1990 public-use samples (the paper's inputs) and ACS 2024.
- *Verdict:* the IV lab. Prefer it to Oregon for a first IV treatment because the data are unrestricted and already licensed; keep Oregon for the offer-versus-coverage lesson if the noncommercial terms fit.

**Staggered Medicaid adoption (memo §4.4).** Unchanged: a strong long-run synthesis, not a first build.

**Minimum-wage bunching in CPS (Cengiz, Dube, Lindner, and Zipperer 2019).** A distinct identification family (missing and excess mass around the new minimum) on the book's own CPS. Replication code not verified today; reserve.

### 6.2 Canonical public replication packages

**Trip.com hybrid work (memo §4.1).** Unchanged. Dataverse deposit noted in the memo. The randomized lab if the author wants continuity with Chapters 4 and 5.

**Michigan social-pressure experiment (Gerber, Green, and Larimer 2008).**
- *Teaching job:* a randomized mailing to about 180,000 households with turnout measured from the voter file, so the outcome is a record, not a report; assignment at the household, so clustering follows assignment; a pure intention-to-treat design with no noncompliance to explain away. Connects to Chapter 1's turnout target and to Chapter 9's validated-turnout case.
- *Data:* Yale ISPS publication page verified; the ISPS data archive entry not verified today.
- *Verdict:* the strongest alternative randomized lab. If the author prefers a political-science thread over the WFH thread, choose this over Trip.com.

**Oregon Health Insurance Experiment (memo §4.2).** Unchanged. Terms must be resolved before download.

**National Supported Work (memo §4.3).** Unchanged. The selection-on-observables lab; compact.

**Bertrand and Mullainathan 2004, resume audit.**
- *Teaching job:* "the effect of what?" A name is a bundle (race, class, region), and the target is the effect of the bundle; randomization inference; callback as a binary outcome; a 2016 reanalysis dispute (Data Colada) on which names drive the result, useful for the redefine move.
- *Data:* openICPSR project 116023 (verified).
- *Verdict:* a short lab or extended exercise; marketing-adjacent because it is a field experiment on a signal.

**Card and Krueger 1994, New Jersey and Pennsylvania.**
- *Teaching job:* the original two-period difference in differences with 410 establishments, and a measurement dispute (survey versus payroll records) as a data-quality identification issue.
- *Data:* the author's data page (verified per search).
- *Verdict:* exercise-length; the design is taught everywhere, and Chapter 6 already carries the DiD lesson.

**Deworming in Kenya (Miguel and Kremer 2004) and the 2015 reanalysis.**
- *Teaching job:* assignment at the school in a stepped-wedge rollout; spillovers to untreated pupils within and across schools; what a reanalysis with different rules found and why.
- *Data:* Harvard Dataverse; the twenty-year follow-up deposit verified, the original 2007 materials not verified today.
- *Verdict:* the spillover lab, if the author wants one. Progresa is the alternative.

**Progresa spillovers to ineligibles (Angelucci and De Giorgi 2009).**
- *Teaching job:* village-level assignment, effects on households that were never eligible, and a survey design with its own weights inside a cluster-randomized rollout. The clearest case for keeping survey weighting and assignment weighting apart (memo §5.2).
- *Data:* openICPSR project 113289 (verified).
- *Verdict:* preferred over deworming when the lesson is the survey-plus-assignment combination.

**California Proposition 99 (Abadie, Diamond, and Hainmueller 2010).**
- *Teaching job:* one treated state, 38 donors, placebo-in-space; the canonical synthetic control.
- *Data:* the state-year panel ships with the Synth R package (not verified today).
- *Verdict:* a companion to Mariel; use it if Mariel's small cells prove too noisy for a first synthetic-control lesson.

**China shock (Autor, Dorn, and Hanson 2013).**
- *Teaching job:* shift-share exposure as identification, with Chapter 7 already motivating its inference.
- *Data:* openICPSR project 112670 and chinashock.info (verified).
- *Verdict:* reserve; heavy, and the inference lesson is already in Chapter 7.

**Maimonides' rule (Angrist and Lavy 1999; Redux 2019).**
- *Teaching job:* fuzzy RD as IV; a 2019 update with a different result on newer data, useful for the redefine move.
- *Data:* MIT archive URL surfaced in search (not opened).
- *Verdict:* reserve behind the Medicare RD, which uses the book's data.

**Management consulting in Indian textile plants (Bloom et al. 2013).** Fewer than thirty plants: identification by randomization with few clusters, so Chapter 6's few-cluster lesson applies to an experiment. Data not verified; reserve.

### 6.3 Descriptive identification cases

- **Big-data paradox** (Bradley et al. 2021; Meng 2018). Public aggregates. Belongs in Chapter 9.
- **Validated turnout** (Cooperative Election Study with Catalist matches). Public microdata by registration; validated-vote variables in recent waves. Belongs in Chapter 9.
- **Measured versus reported** (NHANES against NHIS and BRFSS). Already in Chapter 3's interlude; reframe as an identification fact and link forward.
- **Coverage** (BRFSS landline era against the cell era). Already in Chapter 2; add a one-paragraph identification reading.

### 6.4 Marketing and consumer-facing cases

- **Hillstrom email test.** 64,000 customers, three randomized arms, two-week outcomes (visit, conversion, spend). Widely mirrored (TensorFlow Datasets, scikit-uplift, Kaggle; verified) with the original 2008 blog post as the source. *Teaching job:* an average effect, then heterogeneous effects, then the difference between estimating an effect and choosing whom to target, which is a decision rule and not an estimand. Zero-heavy spend makes the outcome-scale lesson concrete.
- **Criteo uplift dataset.** Large and randomized; reserve for the same lessons at scale.
- **dunnhumby "Complete Journey".** Observational coupon data; selection on observables in retail with rich covariates; license to check; reserve.
- **South African loan mailers (Bertrand et al. 2010).** Randomized advertising content; data not located today; reserve.

### 6.5 Author-original cases

The pipeline already forbids microdata from leaving Box and exports aggregates only. A proprietary case therefore fits, at the reproducibility tier "reproduced from inputs by the author only", and must say so on the page. Rules for a novel case:

- One case per identification family, and only where the public replication in that family lacks something (a survey design, a marketing outcome, a spillover structure).
- The assignment or sampling mechanism must be documentable in the ledger to the same standard as a public case.
- The redefine move must be possible: alternative sample rules and their estimates published as aggregates.
- Candidate shapes that fit the audience: a store-level price or promotion change with a synthetic control; a platform experiment with noncompliance or attrition; a geographic rollout with spillovers.

### 6.6 Feasibility table

| Candidate | Family | Data and terms | Verified today | Fits pipeline | Main risk | Verdict |
|---|---|---|---|---|---|---|
| Mariel on CPS | Comparative case study; sample definition | IPUMS CPS; NBER ORG; Peri–Yasenov Dataverse | Package yes | Yes | Contested; small cells | First lab |
| Medicare at 65 | RD | NHIS, ACS | Paper yes | Yes | Year and age coding | First lab |
| Turnout bounds | Partial identification | CPS Voting Supplement | n/a | Yes | None new | Chapter 9 |
| Big-data paradox | Nonresponse at scale | Public aggregates | Citation already in book | Yes | None | Chapter 9 |
| Validated turnout | Measurement | CES public files | Not verified | Mostly | Validation variable availability by wave | Chapter 9 |
| HonestDiD on Medicaid | Sensitivity | Existing Ch 6 artifacts | CRAN yes | Yes | Package version pinning | First build |
| Angrist–Evans | IV | IPUMS USA 1980, 1990; ACS 2024 | Paper yes | Yes | Extract size | IV lab |
| Trip.com | RCT with attrition | Dataverse (memo) | Memo | No | Package terms | RCT lab (choice) |
| Michigan social pressure | RCT, cluster by household | ISPS | Publication page yes; archive no | No | Archive access | RCT lab (alternative) |
| Oregon | Lottery, IV | NBER, noncommercial | Memo | No | Terms | Later |
| NSW | Selection on observables | Dehejia page (memo) | Memo | No | Sample versions | Later |
| Bertrand–Mullainathan | RCT on a signal | openICPSR 116023 | Yes | No | None | Exercise |
| Card–Krueger | DiD | Author's site | Search yes | No | None | Exercise |
| Deworming | Cluster RCT, spillovers | Dataverse | Follow-up yes; original no | No | Contested | Later |
| Progresa ineligibles | Cluster RCT, spillovers, survey weights | openICPSR 113289 | Yes | Partly | Size | Later |
| Proposition 99 | Synthetic control | Synth package | No | No | None | Companion |
| China shock | Shift-share | openICPSR 112670 | Yes | No | Weight | Reserve |
| Hillstrom | RCT, targeting | Mirrors; original blog | Yes | No | Provenance of mirrors | Later |

---

## 7. The interrelated-ideas graph

The author's direction is a collection of interrelated ideas. The relations should be explicit, not left to the reader. Each row is a pair of sections that perform the same operation under different assumptions; each deserves a two-way link and one sentence saying what differs.

| Existing idea | Identification counterpart | Same operation | What differs |
|---|---|---|---|
| Raking and calibration (Ch 2) | Inverse-probability and entropy-balancing weights | Reweight one group to match another's margins | Missing by nonresponse versus missing by assignment; the target group |
| Age standardization (Ch 3) | Regression standardization, the g-formula | Estimate within cells, average over a chosen distribution | Whether the cell contrasts have a causal reading |
| Weight trimming (Ch 2) | Lee attrition bounds; overlap trimming | Trim to control extreme contributions | Trimming for variance versus trimming to bound a target |
| Two turnout conventions (Ch 1) | Manski bounds | Fill missing cells under an assumption | Two points versus the whole identified set |
| Replicate weights (Ch 3) | Randomization inference; placebo-in-space | Repeat the mechanism that produced the data | Sampling versus assignment as the repetition |
| Implicit regression weights (Ch 5) | Negative weights in staggered two-way fixed effects | Regression averages contrasts with weights nobody chose | Which contrasts, and whether any are invalid comparisons |
| Placebo laws (Ch 6) | Placebo-in-space for one treated unit | Assign the treatment where it did not happen | Many treated units versus one |
| "Whose decision was it?" (Ch 7) | The assignment mechanism | Read the design | Used for the standard error versus used for the point estimate |
| Top-coding (Ch 4) | Censoring; bounds on a mean | A missing tail | Whether the tail matters for the target |
| Kish effective sample (Ch 2) | First-stage strength; effective compliers | Variance inflation from unequal contributions | Unequal weights versus a weak instrument |
| Empty cells in the weight builder | Lack of overlap | No support for a target cell | Narrow the target, or extrapolate under a model |
| Sample rules in Chapter 6 | The redefine move | Change the sample and classify the change | Same move, now applied everywhere |

Publish the graph as a page (a concept map with links), and let it double as the memo's task index (§6.12). It is the single artifact that makes "a collection of interrelated ideas" visible.

---

## 8. Ledger and artifact extensions

Extend the schema in `docs/CONTRACT.md` rather than adding a parallel one. Proposed additions, all optional so existing artifacts remain valid.

**Ledger: `identification` block.**

```json
"identification": {
  "claim_type": "assumption_based_causal",
  "observed": "State-year uninsured shares, 2011–2019, cohort and comparison states",
  "assumption": "Parallel trends; no anticipation; no cross-state spillovers",
  "made_true_by": "argument",
  "falsification": [
    {"check": "Pre-period event-study coefficients, 2011–2012",
     "detects": "Level differences in pre-trends larger than survey noise",
     "cannot_detect": "Post-period departures; violations smaller than the test's power",
     "result": "Joint p = 0.62 under state clustering"}
  ],
  "sensitivity": {
    "method": "Rambachan–Roth relative magnitudes",
    "parameter": "M",
    "breakdown_value": 1.4,
    "display": "The effect's interval includes zero once post-period departures may be 1.4 times the largest pre-period gap"
  },
  "identified_set_without": {"low": null, "high": null, "note": "Unbounded without a trend restriction"},
  "sample_rules_version": "ch6-rules-2026-03"
}
```

- `claim_type` is one of `descriptive`, `design_based_causal`, `assumption_based_causal`, `partially_identified`, `simulation`.
- `made_true_by` is `design` or `argument`.
- The numbers inside are illustrative placeholders; every value must come from a build.

**Facts.** Add explicit `ci_level` and `ci_method` (memo §6.11) before any 90 percent interval, randomization interval, or bounds appears. Add `variance` values `randomization_inference`, `placebo_in_space`, and `bounds`.

**Figures.** Three new types: `bounds` (an interval as a function of a sensitivity parameter, with the breakdown value marked), `flow` (assigned, offered, took up, observed, with counts), and `donor` (synthetic-control weights by unit). All keep the determinism rules.

**Comparison ledgers** (memo §6.1) get a `changed` list whose entries are typed `target`, `assumption`, `estimator`, or `repetition`.

---

## 9. Components: few and shared

The memo's rule stands: no widget per example. The part needs one new shared component and three small ones, and reuses the rest.

**The assumption dial** (new; shared by every lab). Horizontal axis: the strength of an assumption, from "none" to "the paper's". Vertical axis: the identified set or the interval. A marker at the breakdown value. Presets per family: the assumed turnout rate among nonrespondents (Manski), the relative-magnitude bound (HonestDiD), the selection ratio (Oster), the trimming share (Lee), the bandwidth (RD), the donor pool (synthetic control). Static fallback: a three-row table with the paper's assumption, the breakdown value, and no assumption. Acceptance test: at the paper's assumption the dial reproduces the replicated number to displayed precision.

**Missing-data matrix** (extends `PopulationSampler`). Toggle a reason for missingness on the synthetic population; the panel reports whether the target is point-identified, bounded, or unidentified, and shows the bounds.

**Sample-definition explorer** (for Mariel). Choose age range, education, sex, ethnicity, comparison cities, and weighting; the panel reports the sample count, the weighted total, the estimate, and its interval, and labels each change as a target change or an estimator change.

**Compliance flow** (for the randomized labs). A static flow with counts; the intention-to-treat and complier numbers beside it. Interactive only if changing the uptake assumption reveals something the static figure cannot.

**Reuse.** `HiddenEffectWeights` for overlap and contribution (memo §6.7); `VcovExplorer` for randomization inference beside clustering; `RejectionGrid` for placebo-in-space distributions; `Ledger` comparison view for the redefine move.

---

## 10. Robust to what?

A robustness section belongs in the identification part because most robustness checks are identification claims in disguise. Rules:

1. **Every row of a robustness table says what changed:** target, assumption, estimator, or repetition. A row that changes the sample rules is a target change and gets a ledger entry, not a footnote.
2. **A specification curve is grouped by kind of change** before it is sorted by estimate. A curve that mixes the four kinds shows only that numbers can differ.
3. **Report breakdown values, not adjectives.** "Robust" is replaced by the sensitivity parameter's value at which the conclusion changes, on the dial.
4. **State the null.** Sharp, average-effect, or projection-coefficient (memo §8).
5. **Preserve the example-selection record** (memo §9): what was explored before the displayed comparison was chosen.
6. **Contested cases get symmetric treatment.** Each side's sample rules and assumptions in the same ledger format; the reader sees which move separates them.

Mariel is the demonstration, because the published disagreement is almost entirely a disagreement about rule 1. Chapter 6's sample-rule sensitivities are the existing precedent.

---

## 11. Guardrails

- **Replications, not derivations.** Use `did`, `HonestDiD`, `rdrobust`, `Synth` or `tidysynth`, `fixest` and `ivreg`, `WeightIt`, and `leebounds` or their Python equivalents; pin versions; record execution status as the memo's §6.10 asks.
- **Label every study's role**: replication, motivating study, or simulation inspired by its structure (memo §8).
- **No verdicts on disputes.** Mariel and deworming are taught as sample-rule and assumption disagreements, in the same format for each side.
- **No transport.** The trial population is the target; no extrapolation to the ACS workforce (memo §4.6).
- **No causal badge from a checklist.** The ledger records assertions; the reader-owned ledger (memo §10) records the reader's assertions.
- **License before download.** NBER Oregon is noncommercial; ICPSR and Dataverse deposits carry their own terms; IPUMS terms already govern the pipeline. Kaggle and package mirrors are conveniences, not sources; cite the original deposit.
- **Cap the first build.** The part is done for a first edition when one lab per family exists and the dial appears in each; the reserve list stays a list.

---

## 12. A bounded first build

### Package I: pipeline data only

- Chapter 9 with the missing-data matrix, turnout bounds, the big-data paradox, and validated turnout.
- The Mariel lab on CPS.
- The Medicare-at-65 lab on NHIS and ACS.
- HonestDiD on Chapter 6; Manski bounds on Chapter 1; an Oster selection ratio on Chapter 4's adjusted contrast, reported as what it assumes and no more.
- The assumption dial, the ledger `identification` block, and identification cards in Chapters 1 through 7.

**What it replaces:** the scattered caveats become links to Chapter 9; Chapter 6's "what the design assumes" callout becomes a ledger block with a breakdown value.

### Package II: one public package and one IPUMS extract

- The randomized lab (Trip.com or Michigan social pressure) with the compliance flow and Lee bounds where attrition exists.
- Angrist–Evans on IPUMS 1980 and ACS 2024.
- The interrelated-ideas page.

### Package III: after reader feedback

- NSW; Progresa or deworming; Proposition 99 beside Mariel; Hillstrom for the marketing route; one author-original case per family where the public case lacks something.
- Chapter 12 as a standalone, if the closings have not absorbed it.

### Selection rule

The memo's seven criteria (§4, "A selection rule for all new cases") plus two:

8. A "remove the assumption" calculation exists and is computable from the public inputs.
9. Where a published reanalysis exists, it is included as the redefine move.

### Reader tasks that test the part

1. Given a result and its ledger, name the identifying assumption and say whether design or argument made it credible.
2. Read the dial and state the breakdown value in a sentence.
3. Explain why the Mariel estimates differ without saying one author was wrong.
4. Run the Medicare RD with and without survey weights and say which target each answers.
5. Classify each row of a published robustness table as a target, assumption, estimator, or repetition change.
6. Write the identification paragraph of a methods section for one of the labs.

---

## 13. Sources checked today

Search-level checks on September 17, 2026. None of these constitutes a license review or a successful download.

**Verified at the source or repository level**

- Bertrand and Mullainathan (2004), replication data: openICPSR project 116023, https://doi.org/10.3886/E116023V1
- Peri and Yasenov (2019), replication code and data: https://doi.org/10.7910/DVN/ZBB91X
- Autor, Dorn, and Hanson (2013): openICPSR project 112670; https://chinashock.info/data/
- Angelucci and De Giorgi (2009): openICPSR project 113289
- Miguel and Kremer, twenty-year follow-up deposit: https://doi.org/10.7910/DVN/TTYMHI (the 2004 study's 2007 replication materials are described as available on Dataverse; not opened)
- Card and Krueger (1994): data and code described as available at https://davidcard.berkeley.edu/
- Angrist and Lavy (1999): archive URL surfaced, https://economics.mit.edu/faculty/angrist/data1/data/anglavy99 (not opened)
- Gerber, Green, and Larimer (2008): ISPS publication page https://isps.yale.edu/research/publications/isps08-001 (data archive entry not confirmed)
- Card, Dobkin, and Maestas (2008), AER 98(5): NHIS used for coverage and access outcomes; https://www.aeaweb.org/articles?id=10.1257/aer.98.5.2242
- Clemens and Hunt (2019), ILR Review; Borjas (2019), ILR Review reply: the CPS composition argument and its rebuttal
- HonestDiD: https://cran.r-project.org/package=HonestDiD; Stata port https://github.com/mcaceresb/stata-honestdid
- Oster's `psacalc` (SSC) and Masten's `regsensitivity`; Lee bounds via `leebounds` (SSC)
- Hillstrom email test: original announcement https://blog.minethatdata.com/2008/03/minethatdata-e-mail-analytics-and-data.html; mirrors on TensorFlow Datasets and scikit-uplift
- Cooperative Election Study FAQ, https://cces.gov.harvard.edu/frequently-asked-questions (validated-vote variable availability by wave not checked)

**Not verified today; from memory or from the memo**

- Trip.com (Bloom, Han, and Liang 2024) Dataverse deposit: memo [S1]
- Oregon HIE terms: memo [S2]
- NSW samples: memo [S3]
- Bloom et al. (2015) Ctrip and Bloom et al. (2013) management: replication packages not located
- Bertrand, Karlan, Mullainathan, Shafir, and Zinman (2010): data not located
- Cengiz et al. (2019): replication code not located
- Proposition 99 panel inside the Synth R package
- Delphi–Facebook CTIS microdata terms (aggregates are public)
- IPUMS CPS coverage of hourly earnings for 1979–1985

**Already in the book's bibliography and reusable here:** `meng2018`, `bradley2021`, `angrist1998`, `card1994`, `miguel2004`, `autor2013`, `krueger1999`, `roth2022`, `goodmanbacon2021`, `callaway2021`, `abadie2020`, `abadie2023`, `lundberg2021`, `sloczynski2022`.

## Bottom line

The book can own a question that survey texts stop before and causal texts start after: whether these particular data, with this frame, this response, this measurement, and this assignment, determine the quantity the reader named. One missing-data model, one lab template, one shared sensitivity component, and labs that begin on data the pipeline already holds. The first two labs, Mariel and Medicare at 65, need no new license and put a famous dispute and a famous threshold under the book's own weights, replicate variance, and ledgers.
