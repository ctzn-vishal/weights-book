# Where the book could go next

## Ideas for cases, structure, causal inference, interactives, and the reading experience

- **Book:** *Weights, Design, and Estimands — A Field Guide for Applied Researchers*
- **Date:** September 14, 2026
- **Basis:** Current manuscript and UI source, with Git HEAD at `db6bbfe` during review.
- **Stage:** Active-development ideas, not a publication-readiness audit.
- **Recommendation:** Deepen the reader's ability to make and defend decisions. Do not simply add more methods, examples, or controls to the interface.

This is a broader development memo than [the earlier prose review](EDITORIAL_REVIEW_ALPHA.md). Many earlier suggestions have already been implemented. The current book has a numerical cover story, revised openings, clearer empirical labels, new subgroup comparisons, a placebo-law exercise, a new Chapter 7 on clustering, and a field guide that is now Chapter 8. This memo evaluates that version, not the earlier chapter numbering.

The review examined current chapter openings and central empirical sections, the new clustering chapter, the field guide and reproducibility discussion, and the source of the shared reading components and principal interactives. External case-study suggestions were checked against the sources listed at the end. No new empirical result was estimated, no microdata downloaded, and no browser usability test performed. UI observations below are source-based; proposed new findings are explicitly questions to investigate, not promised results.

## If you only read one section

The most valuable next version would add **one actual causal replication**, **one missing-data sensitivity lesson**, and **a clearer path from a chapter's result to the reader's own analysis**.

My shortlist:

| Priority | Idea | Why it earns space | Main dependency |
|---|---|---|---|
| First | Pair ACS work-at-home with the randomized Trip.com hybrid-work study | A familiar topic becomes a concrete lesson in description versus intervention, assignment, outcome choice, and generalization | Audit the public replication package and its terms; reproduce a primary result |
| First | Turn the turnout nonresponse example into a sensitivity analysis | Teaches what to do when neither weighting nor a convention identifies the desired population quantity | Existing group aggregates plus a small, verified calculation |
| First | Add a comparison view for two Analysis Ledgers | Makes Target, Contribution, and Uncertainty visible as changes rather than recurring vocabulary | Existing ledger artifacts; small component extension |
| First | Separate the main reading path from the expanding case atlas | The book has accumulated good material faster than it has simplified navigation | Editorial choices, not new data |
| First | Make one complete lesson executable outside the author's store | Turns an honest reproducibility limitation into a demonstrable reader benefit | Small preparation pipeline, exact inputs, and expected outputs |
| Next | Strengthen the clustering worksheet's conditional advice | A decision aid should be able to say “not enough information” | Methods review and additional input fields |
| Next | Add a genuine causal weighting/overlap lab | Connects survey weighting to treatment assignment without conflating them | A deliberately scoped experiment or experimental/nonexperimental benchmark |
| Later | Oregon Medicaid lottery; modern staggered Medicaid analysis; transportability | Excellent extensions, but each adds substantial assumptions and technical machinery | Separate case auditions and author decisions |

**Do not implement every idea in this memo.** The recommendations below are a menu with explicit preferences and stopping rules.

**Jump to:** [reorganization](#3-reorganization-options) · [causal case studies](#4-causal-case-study-candidates-for-part-ii) · [lessons using current data](#5-new-lessons-that-can-mostly-use-the-current-data) · [UI ideas](#6-ui-components-and-changes-that-would-actually-improve-learning) · [bounded next edition](#11-a-bounded-next-edition) · [sources](#12-sources-and-implementation-anchors).

---

## 1. A diagnosis of the current book

### The strength is no longer just “weights matter”

The manuscript now teaches several more interesting propositions:

- A weighted number can describe the wrong denominator.
- Weighted and unweighted regressions can agree overall but differ within a reported subgroup.
- Very unequal implicit weights can either matter or barely matter, depending on how they covary with conditional contrasts.
- A large survey can measure state outcomes precisely without supplying many independent policy comparisons.
- A correct variance argument for one repetition can be irrelevant to another.

The new racial-turnout-gap example in Chapter 1, education split in Chapter 4, gender comparison in Chapter 5, and placebo laws in Chapter 6 strengthen those ideas. Keep the counterexamples where a method does not change the answer. They are safeguards against writing a methods book that selects its evidence for dramatic reversals.

### The largest substantive gap: Part II diagnoses causal mistakes more than it builds a causal analysis

Chapters 4 and 5 correctly remain descriptive. Chapter 6 takes the policy comparison's identifying assumptions as given to study inference. Chapter 7 introduces published causal designs, but its numerical demonstrations are simulations, not replications of those studies.

That is a coherent book about weighting and inference. But a reader following the route called **“Regression and causal questions”** may still leave without having watched a complete causal estimate being built from an actual assignment mechanism.

The opportunity is not to relabel the ACS wage coefficient as causal. It is to provide a companion study in which the author can say:

> Here is what was offered, who could receive it, how allocation happened, what was measured afterward, and why this comparison supports an intervention claim under these assumptions.

### The largest structural risk: accumulating a collection rather than developing an argument

Chapter 1 now has four substantial empirical subjects and a new racial comparison. Chapter 3 combines a cascade, period changes, standardization, domains, group contrasts, cross-survey design differences, measurement, and replication. Chapters 6 and 7 both open with versions of the advisor/referee dispute over clustering.

The individual sections are often worthwhile. The reader's problem is deciding which are necessary, which extend the main lesson, and what they should carry to the next chapter.

**A new example should replace, compress, or reorganize something unless it teaches a genuinely missing capability.**

### The UI already has a strong foundation

The site already includes:

- Chapter navigation, mobile navigation, active-section tracking, and section permalinks.
- Artifact-backed numbers with provenance popovers on hover and focus, narrow-screen positioning, and Escape dismissal.
- Ledgers, closing panels, expandable details, server-rendered charts, and “Show data” support.
- A population sampler, weight builder, estimand switcher, implicit-weight explorer, replicate ranking, clustering worksheet, variance explorer, and filterable/sortable rejection grid.
- Shared visual tokens, reduced-motion handling, keyboard-focus styling, and non-color cues in widget charts.

The next UI investment should connect these pieces, not recreate them.

---

## 2. A better organizing principle: the decisions behind a reported result

Keep **Target — Contribution — Uncertainty** as the book's central vocabulary. Give readers a second, practical sequence for using it:

1. **Define the quantity.** Population, outcome, unit, time, comparison, and intervention if any.
2. **Ask whether the data can identify it.** Coverage, response, measurement, overlap, assignment assumptions.
3. **Construct the estimator.** Explicit weights, adjustment, aggregation, and implicit contributions.
4. **Match uncertainty to a repetition.** What varies, at what level, under which assumptions?
5. **Stress-test the conclusion.** Alternative targets, plausible missingness, design choices, and small-sample limitations.
6. **Report the result so another reader can reconstruct those decisions.**

“Can these data identify the quantity?” deserves a more explicit place. It currently appears mainly as caveats scattered through the book. It should not be mistaken for a fourth weight family or another software argument.

### A recurring analysis card

At the first substantive result in each chapter, use a compact card:

| Field | Example of the information needed |
|---|---|
| Question | What intervention or comparison is of interest? |
| Population and time | Who is covered, when, and who is excluded? |
| Outcome and unit | What was measured, on which unit? |
| Claim type | Descriptive; randomized assignment effect; observational causal under assumptions; simulation |
| What changes here | Target, estimator, assumption, weighting, or variance rule |
| What remains unresolved | The principal limitation that this chapter will not fix |

This is a summary of the existing Ledger, not a competing metadata system. For causal cases, structured intervention and identification fields may need to be added upstream; do not infer causal status from the presence of an ATE label.

### A useful distinction the book can own

Many methods texts mix together:

- **A different answer to the same question.** Estimator sensitivity or an error.
- **An answer to a different question.** A changed target.
- **An answer under a different assumption.** Nonresponse, confounding, or parallel trends.
- **A different uncertainty statement around the same estimate.** A different repetition or variance approximation.

Make this classification visible at every comparison. It is more useful than teaching readers to distrust every disagreement.

---

## 3. Reorganization options

### Option A — recommended: keep the chapters, add a causal lab and reading routes

This is the smallest change that closes the largest gap.

| Current location | Recommended role |
|---|---|
| Chapter 0 | Short orientation and a worked ledger; vocabulary remains available but not prerequisite |
| Chapter 1 | Targets, denominators, definitions, and assumptions about unanswered questions |
| Chapter 2 | Representation weights, calibration, and their limits |
| Chapter 3 | Survey uncertainty, with core and advanced sections distinguished |
| Lab 3 | Replicate contrasts and rankings; a hands-on extension rather than a mandatory detour |
| Chapter 4 | Descriptive regression targets and explicit weighting |
| Chapter 5 | Heterogeneity, implicit weights, and direct aggregation |
| New companion lab after Chapter 5 | A real randomized study: assignment effect, adjustment, averaging, and generalization |
| Chapter 6 | One complete observational policy comparison and its uncertainty |
| Chapter 7 | An atlas of other dependence and assignment structures, explicitly separated from actual replications |
| Chapter 8 | Searchable reference by survey and task |
| Appendices | Proofs, notation, evidence provenance, and reproducibility |

Do not renumber everything to audition the lab. It can have a stable named route while its place in the permanent edition remains undecided.

**What to compress:** duplicate opening disputes in Chapters 6–7; repeated explanations of replicate-weight mechanics; the most technical Chapter 5 group decomposition on the main path. Keep the full material linked.

**Reader routes to add:**

- “I need a defensible descriptive table.”
- “I need to interpret a regression coefficient.”
- “I need an intervention effect.”
- “I need to justify my standard errors.”
- “I know the concepts; show me the declaration.”

These routes should link to specific sections, not just broad chapter ranges.

### Option B — a more substantial second-edition structure

Organize the book into four parts:

1. **What number are we trying to learn?** Targets, measurement, coverage, missingness.
2. **How do observations count?** Survey weighting, calibration, regression weighting, heterogeneous contrasts.
3. **When can a contrast describe an effect?** A randomized study, causal weighting/overlap, policy comparisons, aggregation of effects.
4. **What could have come out differently?** Survey variance, clustering, few-cluster inference, and sensitivity.

The field guide becomes a parallel reference rather than the final destination of the linear narrative.

**Benefit:** causal identification gets a clear home.

**Cost:** moving all uncertainty late would weaken early empirical examples. Short uncertainty statements must remain with each result, with the full machinery taught later. This structure is not worth the disruption unless a meaningful causal section is actually being developed.

### Option C — a core book plus a case atlas

Use the current main chapters as a compact conceptual spine. Move secondary cases into an indexed atlas with tags for:

- discipline;
- data source;
- decision being changed;
- descriptive/causal/synthetic status;
- prerequisite knowledge;
- public reproduction status.

The racial turnout gap, gender wage contrast, older-adult ranking, spatial dependence, and shift-share case all work well as discoverable extensions.

**Benefit:** room to grow without lengthening every chapter.

**Risk:** the book can become a link maze. Every atlas case needs a short introduction, a return link, and a stated relationship to the core lesson. Do not scatter essential qualifications into optional pages.

### My choice

Use **Option A now**, with the navigation discipline of **Option C**. Revisit Option B only after a causal lab has proved its value with readers.

---

## 4. Causal case-study candidates for Part II

### 4.1 First choice: Trip.com's randomized hybrid-work experiment

**Working title:** *What changes when working from home is offered rather than chosen?*

**Why this is the best fit:** Chapters 4–5 have already made readers care about remote work. A randomized hybrid-work policy keeps the subject familiar while changing the source of identification. The ACS wage gap and the trial do not answer the same question; making that difference explicit is the point.

**Published anchor:** Bloom, Han, and Liang (Nature, 2024) report a trial involving 1,612 Trip.com employees. The paper reports quit rates of 7.20% in the control group and 4.80% in the hybrid-policy group. These are published results to reproduce, not new book estimates. The article links data and code for its primary results to a public Dataverse deposit [S1].

**Opening question:**

> The ACS tells us who earns more. An employer wants to know what will happen if it offers a hybrid schedule. What comparison would answer the employer's question?

**Minimal first version:**

1. Define the offer: the option to work at home on specified days, not an undifferentiated “WFH treatment.”
2. Reconstruct eligibility and allocation. The paper describes allocation by odd/even day of birth; document that actual rule and its justification rather than drawing a generic coin-flip diagram.
3. Reproduce a primary intention-to-treat contrast in quitting, using assignment rather than realized WFH days.
4. Explain why employees who chose to WFH more often are not a newly randomized comparison.
5. Add one pre-treatment-adjusted estimate to show what adjustment can and cannot change.
6. End with the target population: employees in this trial, not all U.S. workers or all jobs.

**The three decisions:**

- **Target:** the effect of offering this hybrid policy on a specified outcome over a specified follow-up, for the trial population.
- **Contribution:** how eligible employees and any prespecified subgroups enter the estimate; whether the target is employee-weighted or some other average.
- **Uncertainty:** the documented assignment mechanism, dependence, and outcome availability—not the ACS survey design.

**An especially useful extension:** distinguish “not detectably different” from “small enough for a decision.” The article uses equivalence tests for some performance outcomes. Reproduce one only after explaining the chosen smallest effect of interest, outcome scale, interval/test relationship, and missing follow-up outcomes. Do not turn a nonsignificant conventional test into proof of no productivity harm.

**An important restraint:** a roughly balanced randomized design with the same assignment probability across prespecified strata need not produce a dramatic implicit-weight distortion. That is useful. It demonstrates when the Chapter 5 problem recedes. Do not force this study to show a regression/ATE gap it does not have. Any deliberately unequal assignment probabilities should be shown in a separately labeled synthetic variant, not manufactured in the real study.

**What to check before adopting:**

- Exact experimental phases, volunteering rules, eligibility, allocation, and allowed schedules.
- Which outcomes are fully observed and which disappear when an employee leaves. Quitting is an outcome; missing later performance reviews are a separate issue.
- Available identifiers and permitted joins. The article says anonymized data are split into files to protect participants; do not assume every desired subgroup or linked panel can be reconstructed.
- The appropriate variance procedure and any employee/team dependence. Do not cluster on “the firm” merely because the trial occurred in one firm.
- Replication-package terms, release version, source conflicts of interest, and the limits of the performance measures.

**Scope/cost:** one new dataset and a bounded replication; moderate empirical work. Higher cost if expanded into longitudinal performance, heterogeneous effects, or transportability.

**Verdict:** audition first. Start with quitting and assignment, not every outcome in the paper.

### 4.2 Strong alternative or second causal lab: the Oregon Medicaid lottery

**Working title:** *The effect of an offer is not the effect of coverage.*

**Why it fits:** the book already discusses uninsurance, hypertension, health measurement, and Medicaid expansion. Oregon provides an actual lottery and a natural contrast between being selected to apply and subsequently obtaining coverage.

**Source status:** NBER provides public-use data and replication code for the principal Oregon studies [S2]. Its posted terms include a noncommercial-use restriction and citation requirements. Data availability is not unrestricted reuse. Resolve compatibility with the intended publication and any future commercial edition before downloading or adopting the materials.

**Opening puzzle:**

> A lottery changed the opportunity to obtain Medicaid. Some selected people did not enroll. Is the effect of being selected the same number as the effect of gaining insurance?

**Minimal sequence:**

1. Choose one paper, outcome, sample, and follow-up window.
2. Reproduce the effect of lottery selection on coverage—the first stage.
3. Reproduce the intention-to-treat effect on a health-care-use or financial-strain outcome.
4. Explain the additional assumptions needed to interpret an instrumental-variable estimate as a complier effect: instrument exogeneity, exclusion, monotonicity, and a relevant first stage.
5. Name whose effect it is, and why it is not automatically an ATE for all uninsured adults.

**Weighting contribution:** allocation probabilities and household structure matter; outcome-survey sampling or response weights may also matter, depending on the chosen dataset. Distinguish them from treatment-receipt weighting. Reconstruct the lottery's household-related rules instead of treating every row as an independent equal-probability assignment.

**Bridge back to Chapter 6:** Oregon's lottery and state Medicaid expansion provide different identification arguments, different populations, different interventions, and different follow-up periods. Put their ledgers side by side, not their effects into a naive “which study is correct?” contest.

**Main risk:** IV can swallow a book about weights. Keep ITT versus complier effect to a short lab; leave weak instruments, multiple instruments, and extensive heterogeneity decompositions to further reading.

**Verdict:** the strongest health-policy alternative. Choose it over Trip.com if the author wants a more unified health narrative and accepts the extra IV prerequisites and access constraints.

### 4.3 A compact causal-weighting lab: National Supported Work / LaLonde

**Working title:** *Can reweighting replace the randomized control group?*

**Why it fits:** this is one of the clearest ways to distinguish a survey representation weight from a weight constructed to compare treatment groups. It also gives overlap and balance diagnostics a substantive reason to exist.

**Source status:** Dehejia's public data page supplies experimental NSW treated/control samples and nonexperimental CPS/PSID comparison samples, with variable definitions and distinctions between sample versions [S3]. It also records reconstruction differences and a correction. Do not use a convenience-package dataset without identifying exactly which sample it contains.

**Proposed lesson:**

- Estimate the experimental assignment contrast for a specified sample, with its uncertainty.
- Replace the experimental controls with an identified nonexperimental comparison sample.
- Examine the covariate distributions before fitting a propensity model.
- Compare a prespecified adjustment and a normalized weighting estimator for a clearly named target.
- Show weight concentration, balance, and remaining lack of support.
- Ask whether a plausible-looking estimate establishes exchangeability. It does not.

**Do not make the experimental estimate “truth.”** It is a benchmark estimate with sampling uncertainty. Keep the treated sample consistent when feasible; if using a different subset changes the target, say so explicitly.

**Why not use it as the flagship:** it is an old, heavily used teaching case, and a small set of demographic variables can create misleading confidence in observational adjustment. It belongs as a compact failure-and-diagnosis lab, not a proof that one modern estimator solves selection.

**Scope/cost:** small files and relatively accessible calculations; substantial care in the historical interpretation and sample comparison.

**Verdict:** best optional lab if the missing topic is explicitly causal weights rather than simply a real causal study. Do not add it alongside both Trip.com and Oregon in the next pass.

### 4.4 Deepen the existing Medicaid case with modern staggered adoption

**Working title:** *One policy, many adoption dates, several averages of effects.*

The current single-cohort analysis deliberately avoids staggered-adoption comparisons. Keep it: it is a clean vehicle for the inference lesson. A later companion could use the already discussed adoption dates and ACS state-year aggregates to ask what an overall policy effect averages.

**Proposed sequence:**

1. Define cohort-time effects under an explicit parallel-trends and anticipation assumption.
2. Specify eligible comparison units for each cohort and time.
3. Compare aggregation by treated population, cohort, and exposure duration.
4. Show where a conventional two-way fixed-effect coefficient differs in comparisons and weights.
5. Use state-level inference appropriate to the design, with few-cluster diagnostics.

**Signature display:** a cohort-by-time matrix whose valid comparison sets are highlighted. Selecting an aggregate highlights the cells and weights behind it.

**Risks:** long-run effects can be supported by different cohorts than short-run effects; policy timing and early partial coverage remain complicated; income-based sample membership may itself respond to policy. A newer estimator does not make those issues disappear. In repeated cross-sections, respect changing composition rather than pretending the same people were followed.

**Verdict:** excellent long-run synthesis of Chapters 5–6. Not the smallest way to add causal identification now, and not a replacement for a randomized case.

### 4.5 Make Project STAR a precise design case, not a generic classroom lottery

Chapter 7 already invokes STAR. The next improvement is not to add another mention of it, but to accurately reconstruct its assignment process.

Krueger's paper describes students and teachers randomly assigned to class types within participating schools [S4]. The current chapter then summarizes the assignment unit as the class and describes whole pre-existing classrooms switching together. Those are not automatically the same experiment.

**A worthwhile case would distinguish:** allocation of pupils, allocation of teachers, formation of classrooms, class-type assignment, switching, and attrition. Explain which parts are fixed in the chosen repetition and why the stated variance method follows. Retain a generic classroom-randomized simulation if useful, but label it as an illustration rather than a faithful replication of STAR.

**What it can teach beyond clustering:** child-weighted versus school-weighted effects, unequal allocation across strata, and why external validity is not supplied by random assignment.

**Data feasibility:** paper source located; a suitable full replication dataset and its reuse terms were not audited in this review. Do not schedule a full empirical chapter until that is done.

**Verdict:** high priority as a precision improvement to existing Chapter 7 prose; optional as a new replication.

### 4.6 Further candidates worth keeping in reserve

- **Cluster-randomized cash transfers with spillovers:** direct effects on recipients versus effects on untreated neighbors; village/population weighting; why arbitrary clustering cannot repair interference. Select a study only after auditing its randomization and public replication files.
- **A marketing encouragement experiment:** assignment to an offer versus actual ad exposure or purchase. This could serve the marketing audience better than more state-policy examples, but avoid proprietary-data dependence and avoid assuming exposed/unexposed comparisons are randomized.
- **Trial generalization:** the study effect versus an effect standardized to another covariate distribution. Start synthetic. Do not transport the Trip.com result to the entire ACS workforce, where many occupations cannot receive the same intervention and comparability fails.

These are research leads, not verified ready-to-use datasets. Their value depends on a real methodological contrast, not topical appeal alone.

### A selection rule for all new cases

A candidate earns a place only if it has:

1. A question a reader would care about independently of the method.
2. One primary teaching job not already better served elsewhere.
3. An auditable target, assignment/sampling mechanism, and outcome definition.
4. Inputs and reuse terms compatible with the book.
5. A primary published result that can be reproduced before extending it.
6. A useful lesson even if the competing estimates agree.
7. A static explanation that works without its interactive.

Stop the audition if the key result depends on inaccessible identifiers, undocumented cleaning, or a comparison selected because it makes the preferred method win.

---

## 5. New lessons that can mostly use the current data

### 5.1 Beyond two turnout conventions: a missing-answer sensitivity surface

Chapter 1 now shows that differential nonresponse changes the racial turnout gap. The next step is to stop presenting the two conventions as the only possibilities.

For group `g`, let `r_g` be the weighted share answering, `v_g` the reported voting rate among answerers, and `q_g` an assumed voting rate among nonanswerers. On the same covered population and weighting convention:

`T_g(q_g) = r_g × v_g + (1 − r_g) × q_g`.

The current Census convention corresponds to `q_g = 0`; extrapolating each group's respondent rate corresponds to `q_g = v_g`. Neither observes nonrespondents' votes.

**Display:** a line for each group's overall rate as its missing-answer assumption changes; a two-dimensional surface or a few transparent scenarios for the between-group gap. Allow different assumptions by group.

**Payoff:** the reader can see what assumptions would narrow, reverse, or preserve a substantive claim. Those thresholds are to be computed, not promised.

**Guardrails:** these are sensitivity scenarios conditional on the observed weighted components, not confidence intervals or identified turnout rates. They do not fix frame exclusion, voting misreporting, or household nonresponse. The current extract lacks design information, so do not invent design-based bands.

This is probably the highest-return new quantitative lesson available without acquiring another survey.

### 5.2 Two kinds of selection: who is observed and who is treated

A short bridge before the causal lab should use two separate diagrams:

- Population → sampled/responding/analytic units.
- Eligible units → assigned offer → treatment received → outcome.

A survey weight addresses a different selection mechanism from a treatment-propensity weight. A response adjustment is yet another object. Name the target before deciding whether any of these need to be combined.

A synthetic example can show that perfect sample representation does not remove treatment confounding, and perfect treatment randomization does not make volunteers representative of everyone else.

Do not give “multiply the survey and propensity weights” as a universal recipe. Combined estimation and variance depend on the target, designs, estimated nuisance models, and available support.

### 5.3 Missing cells: where weighting stops and modeling begins

Extend the weight-builder or hidden-weights lesson to a target cell with no observed support, or no treated/control overlap.

- Show the requested population share.
- Show that the relevant contrast is not estimable directly from observed data.
- Offer an explicit choice: narrow the target, collect data, or introduce a model-based extrapolation with stated assumptions.
- Label the resulting target change or extrapolation.

The interface should not silently merge, clip, or impute until the estimate appears. This would teach a limit of the machinery more forcefully than another example where weights repair the answer.

### 5.4 Make standardization the bridge between Parts I and II

Chapter 3 already standardizes age-specific prevalence to a chosen age distribution. Chapter 5 averages cell contrasts with chosen population shares. A short connecting diagram can show the common operation:

**Estimate within groups → choose a target distribution → average with that distribution.**

Then state what differs: age-standardized descriptive rates need not be intervention effects; causal standardization requires an identification argument for the conditional contrasts.

This would make the book feel like one accumulating framework rather than separate survey and econometrics treatments.

### 5.5 Repeated cross-sections are not panels of people

Use the existing ACS policy case and NHANES period comparison to distinguish:

- repeated measurements of the same people;
- new people sampled in recurring places;
- overlapping multi-year releases;
- changed measurement protocols or coverage across years.

A small timeline is more useful than another paragraph about pooling. Let the reader see which units or field periods overlap and therefore which independence claims need justification.

### 5.6 A design-budget experiment

The population sampler already changes neighborhoods and residents. Give that interaction a practical task: allocate a fixed interview budget across more clusters or more interviews per cluster.

Keep the cost structure explicitly hypothetical. Report precision for more than one outcome, since the best allocation depends on within-cluster similarity and the target. Do not optimize solely on Kish effective size or imply that one allocation is best for every estimand.

### 5.7 An evidence-of-smallness lesson

Connect Chapter 3's “no detectable change” with the proposed trial's equivalence analysis.

Show three situations:

- an interval compatible with a meaningful benefit and harm;
- an interval excluding zero but small relative to a stated practical threshold;
- an interval satisfying a stated equivalence criterion.

The threshold belongs to the substantive decision, not to the p-value. The default threshold should be justified before looking at outcomes; a slider can explore sensitivity but cannot turn post-hoc threshold choice into prespecified evidence.

---

## 6. UI components and changes that would actually improve learning

### 6.1 Analysis comparison: “What changed?”

**Build on:** `Ledger`, `Fact`, `HeldFixed`, and existing before/after figures.

**Interaction:** choose two named analyses; display their numbers together and highlight only differing ledger fields. Keep the full records expandable.

**Examples:** Census versus respondent turnout; WFH regression versus population-share average; descriptive versus policy uncertainty.

**Why it helps:** a reader sees whether a disagreement is about a target, assumption, contribution, or variance rule before comparing its numerical size.

**Data requirement:** explicit comparison metadata. String differences in prose are not a reliable way to decide whether estimands differ. Authors must classify substantive changes upstream.

**Smallest useful version:** static side-by-side ledger with author-specified changed fields. No new analysis engine.

### 6.2 Estimand sentence builder

**Build on:** `EstimandSwitcher`.

**Output:** a complete sentence, not only a number:

> Among [population], during [time], the [mean/share/difference] of [outcome], measured on [unit], under [definition/comparison].

For causal cases, add treatment version, comparator, follow-up, and target population. Display unsupported combinations as unavailable rather than producing a plausible-looking number.

**Smallest useful version:** a finite set of valid named choices backed by existing artifacts. Do not attempt unrestricted natural-language analysis.

### 6.3 Nonresponse sensitivity explorer

**Build on:** Chapter 1's new racial-turnout aggregates and shared sliders/plots.

**Controls:** assumptions about nonanswerers in each group; named convention presets; reset.

**Outputs:** implied group rates, implied gap, and a sentence saying what assumption produced them. Visually distinguish an estimated input from an analyst-specified parameter.

**Static fallback:** a small scenario table and the identity from Section 5.1.

**Acceptance test:** the presets reproduce the existing conventions at unrounded precision; zero missingness makes the assumption irrelevant; boundary assumptions stay within valid rate bounds.

### 6.4 A conditional design adviser, not a clustering oracle

**Build on:** `ClusterDesignWorksheet`.

The current rule engine uses the cluster count to move toward randomization inference below ten clusters. It cannot know whether a defensible assignment distribution exists. State policy is not automatically a lottery, and a small `G` does not make arbitrary label permutation valid.

**Add inputs for:**

- known randomized assignment versus an observational assignment argument;
- treated and untreated cluster counts, not just total clusters;
- imbalance and influential clusters;
- multiple sampling/assignment dimensions;
- plausible spillovers or common shocks;
- uncertainty about any answer.

**Return:** a candidate method, its prerequisites, and the missing information—not an unconditional green light. “Insufficient information” is a valuable result.

Do not turn the current rough cutoffs into universal validity thresholds. Keep source references and distinguish a finite-population assignment argument from a model-based dependence argument.

### 6.5 An assignment map

**Build on:** Chapter 7's design atlas and `VcovExplorer`.

Draw sampling units, assignment units, and observations as nested or crossed structures. Let the user change the mechanism while holding outcome correlation fixed, then explain why the inferential target and variance argument change.

For spatial or shift-share cases, use an exposure graph rather than forcing everything into nested boxes. In a shock-based shift-share interpretation, highlight industries with shared shocks across distant regions.

**Smallest useful version:** three static annotated diagrams: nested, crossed, and shared shocks. Make them interactive only if switching reveals something a side-by-side picture cannot.

### 6.6 Extend the rejection grid from verdicts to operating characteristics

**Build on:** the existing filterable/sortable `RejectionGrid` and variance explorer.

Add Monte Carlo intervals for rejection rates, the number of repetitions, the null being tested, and the repetition mechanism. Where new simulations are justified, show nonzero-effect power and interval coverage as well as null rejection.

“Rejects less often” is not automatically better: a procedure that almost never rejects may be badly conservative. Conversely, one simulated rejection of a true null is not proof that its standard error is wrong.

Replace decontextualized labels such as “valid, coarser” with “under this simulated design,” and keep assumptions visible. Do not select bandwidths by showing the one whose rejection rate happened to be closest to nominal.

### 6.7 An overlap-and-contribution view

**Build on:** `HiddenEffectWeights`.

The widget already shows group shares and implicit weights. Extend it to link three views of a selected cell:

1. target population share;
2. treated/control support;
3. contribution to the reported contrast.

Add the second empirical outcome already in the chapter—the gender contrast—only if the corresponding artifacts fit the same schema. This lets readers see why unequal weights matter in one application and little in another, without creating another standalone widget.

Keep empirical labels descriptive. The same UI's synthetic section can use causal effects because they are defined by the data-generating mechanism; the real-data section should not inherit those labels uncritically.

### 6.8 Equation as an accounting diagram

**Build on:** existing math and charts, not a symbolic algebra system.

For the weighted mean, show records contributing to the numerator and denominator. For implicit weights, select a cell and highlight its population, treatment variance, and contrast. For cluster variance, select a cluster and show how its score enters the sum.

**Purpose:** let readers inspect what the equation counts. Avoid decorative animations of symbols that do not explain the calculation.

**Fallback:** a fixed annotated equation with one worked cell/cluster. The notation must remain selectable text and accessible math, not only an image.

### 6.9 Shared simulation states

**Build on:** the existing seeded widgets and reset controls.

Add “Copy this setup” links containing a versioned preset, seed, and validated parameter values. A teacher and student should be able to discuss the same example.

Do not persist only an opaque seed if the simulation algorithm can change. Include a simulation version, reject invalid parameter ranges, and provide a clear reset. Store only public synthetic settings, not uploaded microdata or personal notes in URLs.

### 6.10 Language preference and copyable declarations

**Build on:** the variance explorer's language tabs and the generic `MdxPre` code wrapper.

Offer a book-level R/Python/Stata preference for parallel code examples; preserve a way to inspect all languages. Add copy controls and attach the tested package version and execution status to each snippet.

A translated snippet is not necessarily a verified numerical equivalent. Preserve the distinction between executed on real data, checked on synthetic data, and documented but unexecuted. Do not hide necessary import, centering, domain, or small-sample options to make a snippet shorter.

### 6.11 Better result provenance, building on what exists

`Fact` already exposes rich metadata. The next step is not “add tooltips,” but make a result easy to retain and revisit:

- a stable link to a result's evidence card;
- a copyable citation and analysis specification;
- the exact artifact and code version;
- verification status and unresolved caveats;
- permission-safe aggregate download where applicable.

The current generic `Fact` display assumes 95% intervals and often infers a t label from degrees of freedom. Before adding equivalence tests, randomization intervals, or other confidence levels, represent confidence level and interval construction explicitly in the data contract. A polished card with the wrong interval label is worse than no card.

### 6.12 Search by task and concept

The section navigation is already useful. Add a lightweight index answering queries such as:

- “Which weight for a lab measurement?”
- “Why did my denominator change?”
- “Do I have enough treated clusters?”
- “Where is the code for a difference between domains?”
- “Why is my coefficient not the average effect?”

Start with an editorially curated task index. Full-text search can follow. Include concepts inside expanded details even if those headings are omitted from the visible section rail. Do not add an AI answer box before ordinary navigation works well.

---

## 7. Reading, accessibility, and presentation

### Distinguish teaching modes without creating three books

Give substantial sections a small, consistent label:

- **Main argument** — necessary to follow the chapter.
- **Work it through** — equation or code.
- **Another case** — transfer or empirical extension.
- **Conditions and limits** — deeper qualification.

Keep essential assumptions beside the result regardless of mode. A “story” view must not become an overclaiming view with all caveats hidden.

### Make print and noninteractive reading first-class

The reviewed CSS has reduced-motion and focus handling, but no dedicated `@media print` block was found. A print pass would be a useful new feature, not merely visual polish.

Specify:

- a static default for every interactive, with parameters and source;
- essential details and caveats included in print;
- tables that do not lose columns to horizontal clipping;
- readable math, captions, and references;
- no floating navigation obscuring content;
- deliberate page breaks around figures where practical.

Start with one representative chapter and one dense lab. Do not promise a book-quality PDF until that path has been tested.

### Test existing accessibility, rather than assume it is missing or complete

The current components already use keyboard focus, labels, shape distinctions, responsive chart layouts, and Escape dismissal for fact popovers. Preserve those features.

Test real reader tasks with keyboard only, a screen reader, touch, narrow screens, zoom, and reduced motion. In particular: selecting a number and reading its provenance, navigating a long table, changing a slider, locating an expanded derivation, and returning from a linked section.

Avoid announcing an entire large table on every slider movement. Summarize the changed result concisely; expose detail on request.

### Use the cover's visual language carefully

The beam-and-pivot cover is memorable. It could support a visual identity across chapters, but do not imply that choosing a cluster changes the point estimate in the same way as changing contribution weights.

A more faithful recurring visual:

- **Target changes:** the highlighted population or reference marker changes.
- **Contribution changes:** marker sizes or the center of the weighted summary change.
- **Uncertainty changes:** the same point stays fixed while the interval or repeated-sampling spread changes.

This is also a useful refinement to the cover-page explanation. The metaphor should reinforce the book's separation of objects, not collapse them.

### Vary the openings instead of escalating their rhetoric

The revised direct address is engaging, but the repeated referee/advisor/software dispute can become a second template. Let different chapters begin with different tasks: choosing a denominator, explaining a discrepancy, interpreting a policy offer, reconstructing a figure, or deciding what a null result rules out.

The current Chapter 4 opening says a worker, manager, and reporter want the same number. They may want different quantities: an intervention effect, a pay-setting comparison, and a descriptive gap. That difference is a better opening opportunity than pretending they agree.

Likewise, “Nobody should publish that number” is too strong for the raw wage gap. It can be the correct descriptive quantity; it is not automatically an adjusted or causal answer. The book should teach that an unadjusted description is not an inferior causal estimate waiting for controls.

---

## 8. Make the new clustering chapter's scope exceptionally clear

Chapter 7 adds valuable breadth. It also moves between several inferential frameworks quickly enough that a reader could leave with a new reflex: “cluster at the regressor's level.” That would replace one overly simple rule with another.

### Separate three arguments

1. A known random assignment design, with a stated finite-population target.
2. A clustered sampling design.
3. A model-based or asymptotic argument about dependence, including spatial and common-factor structure.

Each can justify a variance procedure, but not through identical reasoning. Randomized treatment does not automatically remove sampling-cluster uncertainty for a broader target. Correlated regressors and errors do not by themselves establish exogeneity. A permutation distribution needs an assignment argument.

### Label the role of every famous study

Use “motivating study,” “replication,” or “simulation inspired by this structure.” They should not be interchangeable.

For example, a spatial simulation motivated by rainfall/conflict does not test the validity of rainfall as an instrument or reproduce that paper's effect. A shift-share example can motivate shock-based inference without claiming it is the only possible identification framework for every shift-share design.

### Add adverse designs, not just more methods

Before adding another variance option, stress-test existing conclusions with:

- very few treated clusters despite a larger total cluster count;
- unequal cluster sizes and leverage;
- heterogeneity plus unequal assignment probabilities;
- short time dimensions for common-shock methods;
- spillovers or misspecified dependence ranges;
- a finite-population target versus a superpopulation target.

Report the whole prespecified grid, including failures of favored procedures. If a simulation only studies a zero-effect null, do not infer its power against alternatives from the low rejection rate.

### Distinguish nulls

A sharp null of no effect for any unit, an average-effect null, and a zero coefficient in a projection model are not the same hypothesis. State which is used in the placebo-law exercise and each synthetic design. That small addition would substantially improve the book's causal precision.

---

## 9. Reproducibility, evidence quality, and alpha maintenance

### Deliver one genuinely portable case

Appendix C now explicitly states that the full preparation pipeline is unavailable and fresh-reader execution is not yet possible. Keep that honesty; do not repeat the earlier memo as though the distinction still needed to be written.

The next step is an actual executable path:

1. Pinned input source and release.
2. Exact extract variables and permitted acquisition steps.
3. Public preparation code defining every derived field.
4. A minimal analysis command with a clear environment.
5. Expected sample counts and displayed results.
6. A small independent check.
7. Artifact export that preserves existing no-microdata publication rules.

A compact external trial or a small ATUS calculation may be easier than making the whole ACS pipeline portable. This is a practical reason to audition small replication packages.

### Distinguish verification types on the page

A result can be:

- reproduced from its inputs;
- checked against a second implementation;
- compared with an external benchmark;
- supported by an identification argument;
- sensitive to untestable assumptions.

Passing the first three does not prove the fourth. Display these as separate facts, not one universal “verified” badge.

### Preserve an example-selection record

For new empirical extensions, record the candidate outcomes/subgroups, primary teaching hypothesis, and what was explored before selecting the display. A statement that a family was prespecified is stronger when its specification is preserved with the code version.

This is especially useful now that the book has new subgroup contrasts. Honest exploration is not a flaw; presenting an explored comparison as if selected independently of its result is avoidable.

### Version the book as a research object

Add an edition/build identifier, a result-level “last verified” date, and a short reader-facing record of substantive changes: revised definitions, changed estimates, corrected inference, and new datasets. Separate those from cosmetic UI changes.

Keep a policy for changed chapter routes so citations from a course do not break when a new chapter shifts numbering. Stable named routes and redirects are more durable than chapter numbers alone.

### Maintain the authoring rules alongside the book

The current contract still describes the older chapter list and retains some earlier wording, including the blanket `weights_only_understated` terminology, while the current field guide correctly says the error can go in either direction. Synchronizing the authoring contract with accepted manuscript decisions would prevent later development from restoring superseded claims.

That is a separate author-approved maintenance task, not something this ideas memo changes.

### Make feedback specific

A lightweight “Report a problem with this result” affordance could prepare a report containing the result ID, page anchor, build version, and user-selected category: wording, target, calculation, display, or reproducibility. Let the reader review and submit it deliberately. Do not automatically upload notes, data, or browsing state.

For an alpha book, targeted feedback on a denominator or figure can be more valuable than generic engagement metrics.

---

## 10. Larger possibilities, with explicit reasons to defer some

### A reader-owned Analysis Ledger

Let readers fill a blank ledger for their own project, optionally starting from a book example, and export Markdown or plain text locally. This would turn the book into a useful research companion without requiring a statistical analysis service.

Do not generate a claim of causal validity from checked boxes. Record assumptions as user assertions, not verified facts. No account or server storage is needed for an initial version.

### A capstone rather than another topic chapter

Give readers a deliberately flawed analysis packet: target statement, code, descriptive table, coefficient, and interval. Ask them to identify the mismatches and repair the report. Use synthetic data or explicitly permitted public aggregates; label the errors as teaching examples.

The answer should include valid alternative targets, not one secret preferred specification. A capstone can test whether the framework transfers across chapters.

### A small teaching edition

Offer an instructor route, suggested prerequisites, short exercises with answers, and reproducible widget links. The existing “A new case” prompts are a good start; the next step is a progression from recognition to diagnosis to independent reporting, not simply more quiz boxes.

### Quantiles and distributional targets

Most of the current argument uses means, proportions, and linear coefficients. A later short essay could ask whose median, which quantile, or what share above a threshold is relevant. It would broaden the estimand lesson without turning the entire book into a generalized-linear-model reference.

Do not describe a median as a simple weighted average merely to fit the mnemonic. State the mnemonic's scope and show how the three-decision framework survives beyond it.

### Partial pooling and small-area estimates

The state-ranking lab naturally raises a question: what if the estimate is too noisy to be useful? A later extension can contrast design-based direct estimates with model-assisted or hierarchical estimates, then examine how shrinkage changes interpretation and uncertainty.

This needs a clear distinction between design-based and model-based claims. Do not add smoothing to the existing ranking as if it were a free precision improvement.

### Things I would not build yet

- A generic chatbot that answers “which weight should I use?” from incomplete inputs.
- Arbitrary microdata uploads or a server-side analysis workbench.
- One more bespoke interactive for each additional example.
- A full causal-inference textbook inside Part II.
- MRP, double machine learning, synthetic controls, IV, regression discontinuity, and shift-share estimation all at once.
- A mandatory animated/scrollytelling interface that prevents ordinary reading or printing.
- A single score claiming that an analysis is “correct.”

The book is strongest when it gives readers a defensible argument, not an automated verdict.

---

## 11. A bounded next edition

### Package A — high value, mostly current evidence

- Mark core versus extension sections and improve task-based routes.
- Add the ledger comparison view.
- Build the turnout nonresponse sensitivity lesson.
- Add explicit empirical/synthetic and descriptive/causal status to key results.
- Review Chapter 7's assignment descriptions and conditional recommendations.
- Test a static/print path through one dense chapter.

**What it replaces:** repeated framework paragraphs, duplicated opening disputes, and some table-reading prose. These additions should not simply lengthen every page.

### Package B — the causal addition

- Audition the Trip.com replication and select one primary outcome.
- Add a short “selection into the sample versus assignment to treatment” bridge.
- Publish one complete causal lab with an assignment diagram and a ledger.
- Make that lab independently reproducible if the package permits it.
- Include one careful limit: noncompliance, missing follow-up, or generalization—not all three at full length.

**Alternative:** choose Oregon instead if the health-policy connection is more important than the WFH continuity. Do not begin both as mandatory chapters.

### Package C — after reader feedback

- Extend the hidden-weights widget with the second empirical contrast and unsupported-cell behavior.
- Add shareable, versioned widget states and a persistent code-language preference.
- Develop either the NSW causal-weighting lab or the staggered Medicaid companion, based on what readers still cannot do.
- Expand print/export and the reader-owned Ledger.

### Test success through tasks, not page count

Ask a few representative readers to:

1. Explain why two turnout rates differ without calling one merely “weighted.”
2. State the target of the ACS regression and the target of the randomized hybrid-work estimate.
3. Identify which assumption connects an observed comparison to a causal effect.
4. Defend a standard error while naming its repetition and independent units.
5. Recognize when the interface lacks enough information to recommend a method.
6. Reproduce one number and write its methods paragraph.
7. Use a figure and its caveat on a narrow screen, by keyboard, and in print.

Watch where they get stuck. Do not treat reading progress or correct answers to memorized terminology as evidence that the book teaches these tasks.

---

## 12. Sources and implementation anchors

### External candidate sources checked for this memo

**[S1] Bloom, Han, and Liang (2024), “Hybrid working from home improves retention without damaging performance.”**

- Article: https://www.nature.com/articles/s41586-024-07500-2
- Data/code deposit linked by the article: https://doi.org/10.7910/DVN/6X4ZZL
- Checked: published study description, allocation rule, primary quitting figures, equivalence-test discussion, and the article's data/code availability statement.
- Not checked: downloaded files, successful independent replication, all desired subgroup identifiers, or package reuse terms. The article says anonymized data are split into files; feasibility of additional analyses must be established from the package.

**[S2] Oregon Health Insurance Experiment, NBER data and study pages.**

- Data/code and terms: https://www.nber.org/research/data/oregon-health-insurance-experiment-data
- Study overview: https://data.nber.org/oregon/index.html
- Checked: availability of public-use data and replication code for the principal papers; posted noncommercial-use and citation terms. The lottery and treatment-receipt distinction is the candidate's teaching premise.
- Not checked: package contents, full lottery protocol, analysis-specific survey weights, or a fresh replication. Resolve permitted use before acquiring data.

**[S3] Rajeev Dehejia's NSW data page.**

- https://users.nber.org/~rdehejia/nswdata.html
- Checked: experimental versus nonexperimental files, sample-version distinctions, variable lists, and documented reconstruction/correction notes.
- Not checked: execution of an estimator, full randomization details for a selected subset, or reuse permissions beyond the page's data-publication statement.

**[S4] Krueger (1999), “Experimental Estimates of Education Production Functions.”**

- DOI identified in the source search: https://doi.org/10.1162/003355399556052
- Paper copy located: https://hceconomics.uchicago.edu/sites/default/files/events/Krueger_1999_QJE_v114_n2.pdf
- Checked at source-search/abstract level: students and teachers assigned to different-size classes, and the importance of attrition/transitions.
- Not checked: a full protocol reconstruction or public replication package. This is a reason to review the current STAR simplification, not a certification of a replacement variance rule.

The remaining candidates are explicitly proposed research leads. No external headline number should enter the book directly from this memo: reproduce or properly attribute it through the existing facts/figures/citations pipeline.

### Current manuscript anchors

| Opportunity | Current source |
|---|---|
| Navigation, numbering, and reader routes | [TOC](../lib/toc.ts), [landing page](../app/page.tsx) |
| Turnout assumptions and racial-gap sensitivity | [Chapter 1](../app/ch01-estimands/article.mdx) |
| Weight construction and support limits | [Chapter 2](../app/ch02-weights/article.mdx) |
| Standardization, covariance, and period comparisons | [Chapter 3](../app/ch03-design/article.mdx) |
| Rank interpretation and changing populations | [Lab 3](../app/ch03-lab-replicates/article.mdx) |
| Descriptive regression and the causal-study bridge | [Chapter 4](../app/ch04-regression/article.mdx), [Chapter 5](../app/ch05-hidden-weights/article.mdx) |
| Policy identification, aggregation, and placebo inference | [Chapter 6](../app/ch06-clustering/article.mdx) |
| Assignment/dependence atlas and simulations | [Chapter 7](../app/ch07-cluster-choice/article.mdx) |
| Task reference and reporting | [Chapter 8](../app/ch08-field-guide/article.mdx) |
| Portable reproduction | [Appendix C](../app/appendix-c-reproducibility/article.mdx) |

### Existing components to extend rather than replace

| Proposed improvement | Existing foundation |
|---|---|
| Ledger comparisons | [Ledger](../components/book/Ledger.tsx), [shared widget UI](../components/widgets/ui.tsx) |
| Evidence cards and interval metadata | [Fact](../components/book/Fact.tsx), [FactPositioner](../components/book/FactPositioner.tsx) |
| Conditional clustering advice | [ClusterDesignWorksheet](../components/widgets/ClusterDesignWorksheet.tsx) |
| Variance/assumption comparison | [VcovExplorer](../components/widgets/VcovExplorer.client.tsx) |
| Simulation uncertainty and operating characteristics | [RejectionGrid](../components/widgets/RejectionGrid.client.tsx) |
| Overlap and contribution display | [HiddenEffectWeights](../components/widgets/HiddenEffectWeights.client.tsx) |
| Declaration copy/language controls | [MDX elements](../components/book/MdxElements.tsx) |
| Core/extension navigation | [BookShell](../components/book/BookShell.tsx), [OnThisPage](../components/book/OnThisPage.tsx) |
| Static/print-ready figures | [Chart](../components/book/Chart.tsx), [Figure](../components/book/Figure.tsx), [styles](../app/globals.css) |

## Bottom line

The most distinctive future version is not a longer catalogue of weighting methods. It is a book in which a reader repeatedly learns to **name the question, locate the identifying assumptions, see whose information enters the answer, and justify the uncertainty**.

Keep the existing descriptive evidence. Add one real intervention study that answers a different question honestly. Make the interactive layer reveal assumptions and unsupported choices, not just produce changing numbers. Then make one complete lesson reproducible by someone who does not have the author's data store.
