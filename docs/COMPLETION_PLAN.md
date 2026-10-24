# Completion plan: *Weights, Design, and Estimands*

- **Date:** October 24, 2026
- **Basis:** the repo at HEAD `1b6594f` plus the uncommitted Chapter 9 work; `docs/CONTRACT.md`; the v3 proposal and v4 plan; the alpha editorial review (September 10), the development memo (September 14), and the identification brainstorm (September 17); the independent numbers check in Box `book/reviews/verification.md`; the data inventory in Box `analysis/_meta`.
- **Purpose:** state what is finished, what the book still owes, which chapters remain, and what each needs, so that execution can run in separate sessions. No analysis was run and no page was changed for this plan.

**Jump to:** [where the book stands](#1-where-the-book-stands) · [what done means](#2-what-done-means) · [the remaining chapters](#3-the-remaining-chapters) · [cross-book work](#4-cross-book-work) · [waves and sessions](#5-waves-and-sessions) · [data to provide](#6-data-to-provide) · [decisions](#7-decisions-for-the-author) · [risks](#8-risks-and-stopping-rules)

---

## 1. Where the book stands

### Finished drafts

| Page | Words | Closing | Widget | Independently rechecked |
|---|---|---|---|---|
| Ch 0 Target, Contribution, Uncertainty | 3,400 | none (by design) | PopulationSampler | no (synthetic) |
| Ch 1 What Are We Trying to Estimate? | 4,700 | yes | EstimandSwitcher | yes, 58 of 62 facts |
| Ch 2 Where Survey Weights Come From | 4,800 | yes | WeightBuilder | yes, 76 of 96 |
| Ch 3 Point Estimates and Design-Based Uncertainty | 5,200 | yes | PopulationSampler | yes, 90 of 101 |
| Lab 3 How Much of a State Ranking Is Supported? | 3,300 | yes | ReplicateRanking | yes, 46 of 50 |
| Ch 4 What Are We Weighting For? | 4,700 | yes | none | **no** |
| Ch 5 Hidden Weights Under Heterogeneous Effects | 4,800 | yes | HiddenEffectWeights | **no** |
| Ch 6 Sampling Design, Assignment Design, and Clustering | 5,100 | yes | ClusterDesignWorksheet | yes, 47 of 53 |
| Ch 7 Whose Decision Was It? | 4,800 | yes | VcovExplorer, RejectionGrid | **no** (all simulation) |
| Ch 8 Field Guide: Six Surveys, Declared | 7,100 | yes | none | yes, 39 of 41 |
| App A, B, C | 2,500 / 3,500 / 2,400 | n/a | none | **no** |

Every chapter from 1 to 8 has a full Closing block and carries no draft callout, author query, or TODO. The four discrepancies the September numbers check found (a false sentence in Chapter 6's closing, a stale store description in Chapter 1, a provenance label, and a trimming description in Chapter 2) have been fixed in the prose.

### Chapter 9, drafted September 19, uncommitted

`app/ch09-identification` exists with 18 facts, 5 figures, and 2 ledgers, all computed from Chapters 1 and 6's exported artifacts with no microdata read. Two sections are real: Manski bounds on 2020 CPS turnout and the White–Black gap (with the zero-gap frontier), and Rambachan–Roth relative-magnitude sets for the Medicaid event study evaluated at the point estimates (breakdown values 6.74 for 2014, 1.98 for 2019, 2.96 for the post-period average). Eight `Callout kind="draft"` blocks mark planned cases: validated turnout, the big-data paradox with numbers, a randomized study, HonestDiD confidence sets, Mariel on the CPS, Medicare at 65, an instrument on IPUMS data, and author-original cases.

Uncommitted alongside it: the Ledger `identification` block (component, types, CONTRACT §5), the Part IV TOC entry, the Chapter 9 reader route in Chapter 0, 254 lines of new verified references, the `/tasks` "Find an answer" page and its route table, and the two idea memos. The tasks page links to two Chapter 9 heading anchors and will break if those headings are renamed.

### What the earlier reviews asked for that is still open

From the development memo and the identification brainstorm, not yet built:

- One actual causal replication (a randomized study), so that the "Regression and causal questions" route ends in a built causal estimate.
- The identification labs on pipeline data: Medicare at 65, Mariel on the CPS.
- The assumption dial as a shared component; `bounds`, `flow`, and `donor` figure types; `ci_level` and `ci_method` on facts.
- Identification cards (claim type) in Chapters 1 through 7; a ledger comparison view; the interrelated-ideas page that doubles as the task index.
- A robustness chapter or closing that classifies every change as target, assumption, estimator, or repetition.
- One lesson executable by a reader outside the author's store; a print pass; an edition identifier.
- A verification pass covering the pages not yet rechecked, after which the `noindex` and draft banner come off.

Smaller open items the audit found: Chapter 0 and Chapter 2 promise a "planned essay" (*When weighting is not enough*) that does not exist; Chapter 2's figures run 2.1, 2.2, 2.4, 2.3, 2.5; Chapter 6's first heading hard-codes "Thirty"; Appendix C's NHIS benchmark row needs its year alignment confirmed; the appendices say "booklet" where the chapters say "book"; Appendices A, B, and C have no notation, derivation, or source entry for Chapter 9; `angristevans1998` is only partially verified; Chapter 8 names ANES as "the next guide to add".

### Data in hand (Box `analysis/`, inventory of July 11, 2026)

ACS 2005–2024 with 80 SDR replicate weights; CPS ASEC 1962–2025 with 160 replicate weights from 2005; CPS supplements (voter, food security, civic, tobacco, computer use) weights only; NHIS core 1997–2024 with strata and PSU; ATUS respondent, activity, and who files; NHANES and BRFSS 2024 raw files outside the IPUMS tree. Nothing before 1997 in NHIS, nothing before 2005 in ACS, and no 1980 census sample.

---

## 2. What done means

The first edition is complete when all of the following hold.

1. **Every TOC entry is a finished page**: a lead puzzle with real numbers, a ledger on every headline result, a Closing with all three panels, no draft callouts, and `check-mdx` at zero errors.
2. **Part IV teaches identification through replications**, one lab per identification family in the first build (threshold, randomized assignment, one treated unit, instrument), and every lab makes the four moves: replicate, ledger, remove, redefine.
3. **Every identifying assumption in the book has a numerical companion**: an identified set without it or a breakdown value, shown on the assumption dial or in its static fallback.
4. **The fourth question is visible before Part IV**: an identification card at the first result of Chapters 1 through 7, and the Target–Identification–Contribution–Uncertainty line in Chapter 0.
5. **The appendices cover the whole book**: notation and crosswalk rows for identification, the scoped derivations Part IV uses, and sources, tiers, and auditions for every new dataset.
6. **An independent numbers check has covered every page**, the discrepancies are resolved, and the site ships without `noindex` and without the draft banner, with an edition identifier and a change record.
7. **One complete lesson is reproducible by a reader** from public inputs with stated expected outputs.

Out of scope for the first edition, by earlier decision and reaffirmed here: MRP, double machine learning, a general causal-inference text inside Part II, a chatbot, microdata uploads, a per-example widget, and a verdict on any contested study.

---

## 3. The remaining chapters

Part IV keeps the structure the brainstorm recommended (its Option A with sibling-volume packaging): stable slugs, own artifact namespaces, no chapter numbers in prose. Four pages remain to write and one to finish. Word budgets follow CONTRACT §7 (2,000–3,500 per chapter).

### Chapter 9 · Can These Data Identify the Quantity? (finish)

**Status.** The spine chapter is written. Three of its eight placeholders belong in this chapter and get filled; the other five become labs and chapters below, and their callouts turn into one-paragraph forward links.

**Fill in this chapter.**

| Placeholder | What fills it | Data | Build change |
|---|---|---|---|
| Confidence sets for the Medicaid dial | HonestDiD robust confidence sets for 2014, 2019, and the average; the set at $\bar M = 1$ beside Chapter 6's interval; robust breakdown values beside the point-estimate ones | none new | ch06 `build.py` exports the state-clustered event-study covariance matrix as an artifact; ch09 `build.py` calls R `HonestDiD` (pin the version) |
| Big-data paradox, with numbers | Delphi–Facebook, Census Household Pulse, and Axios–Ipsos first-dose estimates for one spring-2021 month against the CDC benchmark; each error, its implied data-defect correlation, and the simple-random-sample size with the same mean squared error | public aggregates (see §6) | new ch09 inputs; facts carry `variance: none` and an `external benchmark` label |
| Validated turnout | Overreport overall and by race and education in CES 2020; the White–Black gap under reported and validated votes; CPS bounds widened for misreporting | CES 2020 common content with validated vote (see §6) | new input; survey weights of the CES declared; reported-vote facts beside validated ones |

**Also.** Add `ci_level` and `ci_method` to the facts the confidence sets produce; state the null being used; keep the sets labelled as evaluated at point estimates where they are. Replace the five remaining placeholder callouts with short forward links once their pages exist. Rename nothing: the tasks page depends on the headings `#missing-answers-turnout-as-a-set` and `#no-support-an-empty-cell-is-an-unidentified-contrast`.

**Does not establish** (unchanged): which turnout convention is right; that parallel trends holds; any effect of working from home.

### Lab 9 · Medicare at 65: a threshold with survey weights (new)

- **Slug / key:** `ch09-lab-medicare` / `ch9lab`. **Part IV**, after Chapter 9.
- **Question.** Health coverage jumps at age 65. By how much, for whom, and what does the survey design add to a regression discontinuity that textbooks run on administrative files?
- **Lead puzzle.** The same discontinuity in coverage at 65 computed four ways from the NHIS: unweighted, weighted, weighted with Taylor standard errors, and weighted with a donut that drops ages 64 and 65. The first two answer different targets; the second two answer the same target with different uncertainty.
- **Replicate.** The coverage results of Card, Dobkin, and Maestas (2008) from NHIS: any coverage, Medicare, and private coverage by single year of age, with their years and sample rules reconstructed and recorded in the manifest. The utilization results used restricted hospital data and are out of scope.
- **Extend.** The same design on ACS 2019 and 2024 with `PERWT` and SDR replicate variance (HINSCARE, HCOVANY, HCOVPRIV), by sex and by race and ethnicity; the discrete running variable (age in whole years) treated with the local-randomization framing; bandwidth and polynomial sensitivity on the dial; what else changes at 65 (employment, retirement) shown as the exclusion problem.
- **Ledger identification block.** `claim_type: assumption_based_causal`, `made_true_by: argument` (continuity of everything else at 65), `sensitivity`: bandwidth and donut breakdown.
- **Artifacts.** A `dot` figure by age, a `bounds` figure (estimate against bandwidth), a `table` of specifications typed by kind of change, two ledgers (NHIS, ACS).
- **Widget.** The assumption dial, preset "bandwidth". No new widget.
- **Data.** In hand: NHIS core 1997–2024, ACS 2005–2024. Nothing to acquire.
- **Does not establish.** The effect of Medicare on health or utilization; the effect for anyone far from 65; that the 65 threshold is the only thing that changes.
- **Risks.** Reconstructing the paper's NHIS years and age coding; the NHIS redesign in 2019 changes the coverage items, so the replication years and the extension years are declared separately.

### Chapter 10 · Identification by Design (new)

- **Slug / key:** `ch10-design` / `ch10`.
- **Question.** When someone made the assignment, the same mechanism identifies the effect and defines what could have come out differently. What does a built randomized estimate look like, and what does it still not give you?
- **Lead puzzle.** The study's primary intention-to-treat contrast beside the comparison a naive analyst would run (treated-as-received, or volunteers against non-volunteers). Same file, same outcome, one defensible number and one that is not.
- **Case (decided October 24, 2026).** The Trip.com hybrid-work trial (Bloom, Han, and Liang 2024), subject to its package terms: quits as the primary outcome, assignment by odd or even birthday, 1,612 employees. It keeps the subject of Chapters 4 and 5 and changes the source of identification. Fallback if the terms do not permit a public book: the Michigan social-pressure mailing experiment (Gerber, Green, and Larimer 2008), which loses the compliance lesson.
- **Audit before building.** Read the Dataverse terms and the article's data-availability statement; list the files and confirm that assignment, quits, and the follow-up window are reconstructable; note which outcomes disappear when an employee leaves; check for team or manager identifiers before choosing the variance unit. Stop and report if any primary result depends on files the deposit does not hold.
- **Sections.** Assignment as identification and as repetition · The offer against its receipt (intention to treat, uptake, the complier effect) · Outcomes that go missing (attrition; Lee trimming bounds as Chapter 2's trimming turned into an identification tool) · Clusters in assignment (household or team; why clustering follows assignment) · Whose effect it is (the trial population; no transport to the ACS workforce).
- **Four moves.** Replicate one primary published number from the public package and record discrepancies; ledger with `made_true_by: design`; remove (Lee bounds under attrition, or the sharp-null randomization interval); redefine (prespecified subgroup or outcome window, each change typed).
- **Artifacts.** A `flow` figure (assigned, offered, took up, observed, with counts), a `dot` figure of estimates by estimator, one `bounds` figure, a ledger. Facts carry `variance: randomization_inference` where used.
- **Widget.** A static compliance flow; interactive only if changing the uptake assumption reveals something the static figure cannot. Reuse `VcovExplorer` for randomization inference beside clustering.
- **Data.** One public replication package (§6), after an audit of its files and terms.
- **Does not establish.** An effect for any population outside the trial; the effect of the treatment received for non-compliers; anything about the ACS wage gap.
- **Bridge.** A short "two kinds of selection" passage with two diagrams (population to analytic sample; eligible to assigned to treated to observed) and a synthetic example showing that perfect representation does not remove confounding and perfect randomization does not make volunteers representative.

### Chapter 11 · Identification by Assumption: One City, Several Answers (new)

- **Slug / key:** `ch11-assumption` / `ch11`.
- **Question.** When the assumption has to be argued, the sample definition is part of the argument. Four published estimates of one event disagree in sign; which of their differences are changes of target, of assumption, of estimator, or of repetition?
- **Lead puzzle.** The Mariel boatlift on the CPS: Card (1990) finds little effect of the 1980 arrivals on Miami wages; Borjas (2017) a large decline for one subgroup; Peri and Yasenov (2019) none with a synthetic comparison; Clemens and Hunt (2019) trace part of the gap to a change in CPS coverage of low-skill Black men around 1980. The same event, four sample rules, four numbers.
- **Sections.** Who is in the sample (age, education, sex, ethnicity, comparison cities) · A frame change inside a causal dispute (the 1980 coverage change as a Part I lesson) · One treated unit: synthetic control and placebo-in-space as Chapter 6's placebo laws in another guise · Sampling noise in tiny cells (CPS Miami cells by rule; replicate variance where it exists and an argued variance where it does not) · The four moves applied symmetrically to each paper.
- **Four moves.** Replicate each paper's headline under its own rules from the Peri–Yasenov package and the book's CPS extract; one ledger per paper in the same format, no verdict; remove (the donor-pool and placebo distributions); redefine (the sample-definition table, each rule change typed).
- **Artifacts.** A `table` of sample rules by paper, a `donor` figure (synthetic-control weights by city), a `dot` figure of placebo-in-space estimates, a `line` figure of Miami against its synthetic, four ledgers, one comparison ledger with a typed `changed` list.
- **Widget.** The sample-definition explorer (choose rules; see count, weighted total, estimate, interval; each change labelled by kind). Reuse `RejectionGrid` for the placebo distribution. This is the one new widget Part IV justifies beyond the dial.
- **Data.** In hand: CPS ASEC 1977–1992. To acquire: hourly earnings from the outgoing rotation groups for 1979–1991 (the ASEC has no hourly wage for those years) and the Peri–Yasenov replication package (§6).
- **Does not establish.** Who was right about Miami; the effect of immigration in general; a design-based variance for the early CPS cells.
- **Second case, as a section or Lab 11 (author's decision).** The sibling-sex instrument of Angrist and Evans (1998) on the IPUMS 1980 census sample, with the same specification on ACS 2024: first stage, reduced form, their ratio, the complier share, and a first stage that has shrunk as fertility fell. Needs the 1980 extract (§6). If time is short this becomes a lab after the first edition; Chapter 11 is complete without it.

### Chapter 12 · Robust to What? (new, short; the book's ending)

- **Slug / key:** `ch12-robust` / `ch12`. About 2,000 words; no new data.
- **Question.** The book now has four kinds of change. How does a report say which one each robustness row is, and what does the reader carry to their own analysis?
- **Content.** The four kinds of change (target, assumption, estimator, repetition) with one example of each from earlier chapters, as facts cross-referenced by id · Rules for a robustness table and a specification curve grouped by kind before sorting by estimate · Breakdown values instead of adjectives · Which null (sharp, average-effect, projection coefficient), stated for Chapter 6's placebo laws and Chapter 7's designs · The example-selection record · A template identification paragraph for a methods section, with the corrected version written for one book result · The interrelated-ideas map (brainstorm §7) rendered as a linked page, which also becomes the concept half of the task index.
- **Why a chapter and not a closing.** The book currently ends on a reference guide and a chapter of placeholders. It needs a page that is read last.
- **Does not establish.** A score for any analysis; that any listed check is sufficient.

### Pages not planned

An ANES guide for Chapter 8 (deferred; the ANES reference is verified and the Chapter 2 box exists); the housing-burden application; NSW, Progresa, deworming, Proposition 99, China shock, Hillstrom, and author-original cases (Package III of the brainstorm, after reader feedback); the *When weighting is not enough* essay, whose two promised topics are now Chapter 9's big-data section (built) and MRP (dropped from the first edition). Chapters 0 and 2 should point to Chapter 9 instead of the essay.

---

## 4. Cross-book work

### Schema and front-end (repo; FE and W agents)

| Item | Where | Needed by |
|---|---|---|
| Facts: `ci_level`, `ci_method`; `variance` values `randomization_inference`, `placebo_in_space`, `bounds` | `lib/types.ts`, `components/book/Fact.tsx`, CONTRACT §5 | Ch 9 confidence sets, Ch 10 |
| Figure types `bounds`, `flow`, `donor` with server-rendered SVG | `components/charts/`, CONTRACT §5 | Lab 9, Ch 10, Ch 11 |
| The assumption dial (shared widget; presets by family; static three-row fallback; acceptance: reproduces the replicated number at the paper's assumption) | `components/widgets/AssumptionDial` | Ch 9, Lab 9, Ch 10, Ch 11 |
| Sample-definition explorer | `components/widgets/SampleRules` | Ch 11 |
| Ledger comparison view with a typed `changed` list | `components/book/Ledger.tsx` | Ch 11, Ch 12 |
| Identification card at the first result of Ch 1–7 (`claim_type`, observed, assumption, made true by) | ledgers of Ch 1–7 gain an `identification` object; no new component | definition of done §2.4 |
| Finish `/tasks`: stable section ids, sidebar link, the Chapter 12 concept map | `app/tasks`, `lib/task-routes.ts` | Ch 12 |
| Edition identifier, result-level "last verified", change record | layout, footer, a `data/edition.json` | §2.6 |
| `@media print` pass on one dense chapter and one lab | `app/globals.css` | §2.6 |

### Contract and appendices (integrator)

- Sync `docs/CONTRACT.md`: the chapter table (Lab 9, Ch 10–12), new figure types, new fact fields, `weights_only_understated` reworded per Chapter 8's finding that the error has no fixed direction, and the Part IV lab template as a binding rule.
- Appendix A: notation for the identified set, breakdown value, $\bar M$, $q_g$; claim types; crosswalk rows (nonresponse weight / inverse-propensity weight, calibration / entropy balancing, trimming / Lee bounds, placebo laws / placebo-in-space).
- Appendix B: the Manski bound width identity; the relative-magnitudes set at the point estimates and what the confidence set adds; Lee bounds; one numerical check for each.
- Appendix C: sources and pinned releases for every new dataset and package; the reproducibility tier of each Part IV page (public replication packages are Tier 1; CES and Dataverse deposits carry their own terms); the auditions for Part IV; the one reader-executable lesson (candidate: Chapter 9's turnout bounds, which need only CPS Voting Supplement aggregates, or Chapter 10 if its package permits).
- Resolve the small items in §1: figure order in Chapter 2, "Thirty" in Chapter 6, the NHIS benchmark row, "booklet", the essay references, `angristevans1998`.

### Verification and release

- Independent numbers check, same protocol as September's, for Chapters 0 (synthetic claims), 4, 5, 7, 9, Lab 9, 10, 11, 12, and the appendices' numerical checks. Record in Box `book/reviews/verification.md`.
- A citation pass on every reference added since September 10.
- Remove `noindex` and the draft banner; set the edition identifier; write the reader-facing change record.

---

## 5. Waves and sessions

Each wave is one or more execution sessions. A session gets this file, CONTRACT, the chapter's row in §3, and the data in §6. Order within a wave is free; waves are ordered by dependency.

| Wave | Sessions | Needs data from §6 | Produces |
|---|---|---|---|
| **0. Land Chapter 9** | 1 | none | Commit the uncommitted work (Chapter 9, Ledger block, TOC, references, tasks page, memos). Fix the §1 small items. CONTRACT sync. |
| **1. Pipeline-only analysis** | 2, parallel | none | (a) ch06 covariance export and HonestDiD sets in Chapter 9. (b) Lab 9 Medicare at 65, full build on NHIS and ACS. |
| **2. Front-end for Part IV** | 1–2 | none | Fact fields, figure types, the dial, the comparison view, identification cards in Ch 1–7. Can run alongside wave 1 if the artifact schemas are agreed first. |
| **3. Public aggregates and CES** | 1 | A, B | Big-data paradox and validated turnout sections in Chapter 9; Chapter 9 placeholders closed. |
| **4. Chapter 11 Mariel** | 1–2 | C, D | Chapter 11 build, prose, sample-definition explorer. |
| **5. Chapter 10 randomized** | 1 | E (one of E1, E2) | Chapter 10 build and prose, compliance flow. |
| **6. Instrument** | 1 | F | Angrist–Evans as a Chapter 11 section or Lab 11. Optional for the first edition. |
| **7. Chapter 12 and appendices** | 1 | none | Chapter 12, concept map, Appendices A–C updates, tasks page finished. |
| **8. Verify and release** | 1–2 | none | Numbers check of unchecked pages, citation pass, print pass, edition identifier, `noindex` off. |

Waves 1 and 2 can start today. Waves 3 through 6 each wait only on their data. Wave 7 waits on 4 and 5 (it cross-references them). Wave 8 is last.

---

## 6. Data to provide

What the author can supply or authorize for the execution sessions. "In hand" means in Box `analysis/`. Terms are to be read before download; none was read for this plan.

| Id | Dataset | For | Status | What to provide |
|---|---|---|---|---|
| A | Spring-2021 first-dose vaccination estimates: Delphi–Facebook CTIS weekly, Census Household Pulse, Axios–Ipsos, and the CDC benchmark series, as used by Bradley et al. (2021) | Ch 9 big-data paradox | public aggregates; not in hand | The published series (Bradley et al. supplementary data and the CDC series), or permission for the session to download them; the month to use |
| B | Cooperative Election Study 2020 common content with Catalist validated vote (`CL_2020gvm`), and 2022 if wanted | Ch 9 validated turnout | public on Dataverse; not in hand | The downloaded file plus its codebook and the terms page, or permission to download; confirm the validated-vote variable in the chosen wave |
| C | CPS outgoing rotation group hourly earnings, 1979–1991 (NBER MORG files), with metropolitan area codes | Ch 11 Mariel | not in hand (the ASEC in hand has no hourly wage for those years) | The MORG yearly files, or permission to download from NBER; or an IPUMS CPS basic-monthly extract if it carries earnings and metro codes back to 1979 (to confirm) |
| D | Peri and Yasenov (2019) replication package, Harvard Dataverse `10.7910/DVN/ZBB91X` | Ch 11 Mariel | public; not in hand | The package and its terms, or permission to download; Borjas (2017) and Clemens–Hunt (2019) sample rules will be taken from the papers |
| E1 | Bloom, Han, and Liang (2024) Trip.com deposit, Harvard Dataverse `10.7910/DVN/6X4ZZL` | Ch 10 (chosen) | public; terms to audit | The package and its terms, or permission to download; which files hold quits and assignment |
| E2 | Gerber, Green, and Larimer (2008) Michigan social-pressure data, Yale ISPS archive | Ch 10 (fallback only) | public; archive entry to confirm | Nothing unless E1's terms fail |
| F | IPUMS USA 1980 5% state sample: AGE, SEX, MARST, RACE, HISPAN, EDUC, EMPSTAT, UHRSWORK, WKSWORK1, INCWAGE, INCTOT, NCHILD, MOMLOC, POPLOC, SERIAL, PERNUM, PERWT, plus attached children's sex and age; and 1990 if the paper's second sample is wanted | Angrist–Evans (Ch 11 section or Lab 11) | not in hand; IPUMS licence already held | An IPUMS extract placed in Box `parquet/usa/` through the existing pipeline, or the DDI and data file for the session to clean |
| G | ANES 2024 Time Series (already in Box `ANES/`) | Ch 8 guide, deferred | in hand | nothing now |

Nothing is needed for Lab 9 (NHIS and ACS in hand), for the HonestDiD sets (Chapter 6's own artifacts), or for Chapter 12.

Software to install before waves 1 and 4: R `HonestDiD` (CRAN), `rdrobust`, and a synthetic-control package (`Synth` or `tidysynth`), with versions pinned in each chapter's manifest.

---

## 7. Decisions for the author

1. **Which randomized study for Chapter 10:** decided October 24, 2026: Trip.com, subject to its package terms; Michigan social pressure is the fallback.
2. **Angrist–Evans in the first edition** as a Chapter 11 section, as Lab 11, or deferred. Recommendation: Lab 11 if the 1980 extract arrives before wave 7; otherwise defer.
3. **Chapter 12 as a chapter** (recommended) or folded into closings.
4. **Identification cards in Chapters 1–7:** add now (recommended; small ledger edits) or after Part IV is read.
5. **The reader-executable lesson:** Chapter 9's turnout bounds (smallest) or Chapter 10 (most convincing). Recommendation: both if Chapter 10's package permits; the turnout bounds at minimum.
6. **Publication cadence:** ship Part IV pages as they finish under the draft banner (recommended; the site already does this), or hold until wave 8.
7. **Author-original cases:** none in the first edition (recommended), or one, which needs its own data and a stated "reproduced by the author only" tier.

---

## 8. Risks and stopping rules

- **Mariel's early CPS cells are small and have no replicate weights.** If the design-based variance cannot be argued convincingly for 1979–1985, keep the chapter's lesson on sample definition and placebo-in-space, and move the synthetic-control variance discussion to Proposition 99 as a companion (its panel ships with the Synth package).
- **A replication package does not reproduce its paper.** Record the discrepancy and its cause as a fact; the four moves include "record what did not reproduce". Do not substitute the paper's number.
- **Package terms conflict with a public book.** Stop the audition; choose the other Chapter 10 option.
- **Scope creep in Part IV.** The first edition stops at one lab per family. Reserve cases stay a list in Appendix C.
- **Verification before release.** No page loses its draft banner until its numbers have been independently recomputed and its citations checked. Pages in Part IV carry the banner until wave 8 even if finished earlier.
- **Selection rule for anything new** (memo §4 plus brainstorm §12): a question readers care about independently of the method; one teaching job not already served; an auditable mechanism; compatible terms; a published number reproduced before any extension; a lesson even if the estimates agree; a static explanation that works without the interactive; a computable "remove the assumption"; the published reanalysis included where one exists.
