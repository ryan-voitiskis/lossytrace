# LossyTrace research restart review — 2026-09-05

This is a strategic review and proposed research sequence, not a frozen
experimental amendment, new observation, or final scientific disposition.
It preserves the existing evidence and execution boundaries. The recommendation
is to resolve the meaning and feasibility of the perceptual target before
making another sparse-source acquisition the critical path.

## What we are trying to establish

The useful question is whether coding has made audio meaningfully worse to
listeners, and whether that difference can be estimated reliably on unfamiliar
material. There are three distinct versions of this question:

| Available evidence | Defensible research target | Principal limitation |
| --- | --- | --- |
| A trusted reference and its controlled encode/decode output | Incremental perceptual impairment caused by that intervention | Listener population, playback, source support and metric validity |
| Two versions with a verified common source | Relative fidelity or preference under a declared comparison | A different master can introduce intentional differences; similarity is not automatically quality |
| One unknown waveform | Population-conditional prediction of perceived impairment or a request for human review | The missing reference and production intent are not identifiable from that waveform alone |

The first is the strongest initial scientific and practical target. A useful
reference-based comparator would be a substantive result even if standalone
estimation never succeeds. Transcoding regression checks and choosing an
encoding setting for a known source are plausible applications; they are not
currently validated or enabled products.

For standalone inference, changing the label from codec history to degradation
does not eliminate the missing-information problem. The same observed signal
can be an intended master or a degraded version of a different master. Its
reference-dependent impairment can differ while the estimator's input remains
identical. This is an identifiability argument about the requested mapping,
not a new empirical result or a claim that useful statistical prediction is
impossible. A standalone system needs a declared population, uncertainty and
abstention; it cannot recover an arbitrary unknown counterfactual.

The existing [research contract](perceptual-degradation-contract-20260803.md)
already recognizes much of this distinction. The restart should make it
operational in the target schema and study design.

## What the research has actually established

The previous codec-history program produced a meaningful conditional negative.
Across the tested development scope, no completed interpreted representation
passed its paired-direction and domain gates. This is narrower than a theorem
against every possible future detector. The
[machine-readable disposition](../../research/baselines/v2/evidence/identifiability-decision-20260803.json)
explicitly preserves that limitation and keeps transfer evidence unopened.

The learned baselines are especially informative. On the selected factorial
cases, the naive CRNN achieved 98.30% recall with 95.48% false positives; the
masked model classified every negative as positive. Their unique-PCM AUCs were
50.75% and 46.31%. These are results on a deliberately difficult development
population, not real-library prevalence estimates. They show that high recall
was not useful discrimination, and the near-chance rankings make threshold
repair an inadequate explanation of those runs. The
[CRNN report](development-crnn-baseline-result-20260803.md) also documents
source-dependent paired effects and wrapper invariance.

The perceptual program has established engineering readiness and several
limitations, but has not yet tested the main quality-prediction hypothesis:

- Sixteen clean ODAQ references were acquired and delivered with provenance
  and attribution accounting. They remain development material.
- The declared RME/Adam playback chain passed its historical delivery and
  qualification checks. That is not listening truth or a fresh verification
  of the physical setup today.
- ViSQOL replayed deterministically on four synthetic fixtures in two bound
  environments. That is not perceptual calibration.
- The retained drift experiment was reproducible, but six of 112 cases per
  replay failed the mandatory post-correction correlation gate. Its
  [technical negative](../../benchmarks/perceptual-degradation-v1/odaq-retained-drift-validation-result-20260817.json)
  remains unchanged. Correlation is not an audibility measure.
- One tonal/non-sparse descriptor contrast passed; three sparse/non-tonal
  candidates failed or abstained. These are descriptor outcomes, not evidence
  against perceptual estimation.
- The GstPEAQ candidate stopped at its recorded legal/conformance boundary;
  the ViSQOL-only successor is prepared but unselected. This review does not
  reassess patent clearance or execute either metric.
- Controlled human calibration, validated perceptual outputs and no-reference
  training are absent. The latest
  [objective audit](../../research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260819-022.json)
  still records four satisfied requirements out of fourteen. That checklist is
  not a completion percentage.

## Assumptions that need a successor review

### 1. Audibility currently refers to two different prediction targets

The contract defines audibility as the probability that a listener answers a
forced-choice trial correctly, with chance at 0.5. However, the
[full-reference evaluator](../../scripts/perceptual_degradation_full_reference_evaluation.py)
computes Brier score, ECE and AUC using `human_audible`, a Boolean condition
label, against `audibility_probability`.

Probability of a correct response and probability that a condition belongs to
an audible class are different quantities. For a transparent condition, an
ideal correct-response prediction of 0.5 incurs squared error 0.25 against a
false audible-class label. An ideal audible-class prediction would instead
approach zero. This is a design-level semantic inconsistency, not a measured
failure of an existing calibrated model.

A successor should name both quantities if both are needed, identify their
analysis units, and evaluate each against the matching target. It must also
represent indeterminate human evidence explicitly rather than silently treating
it as an inaudible negative. This should precede model or threshold selection.

### 2. Transparency and absence of material damage are different claims

The frozen equivalence interval is 0.45–0.55 correct-choice probability. The
original [power simulation](perceptual-degradation-listening-power-20260803.md)
found zero equivalence power for the tested smaller designs. A stress case
with 240 listeners, 120 source groups and 3,600 judgments reached 0.850 power
for one aggregate condition stratum under its assumptions.

The later [condition-strata workload analysis](perceptual-degradation-listening-condition-strata-workload-20260814.md)
puts the 16-recipe, four-partition, one-device scenario at 16,688 enrolled
session slots under optimistic MUSHRA packing, or 27,048 with dedicated
strata, at 90% retention. These are model-dependent planning sensitivities,
not empirical recruitment requirements or counts of unique people.

The dominant cost follows from a particular claim and uncertainty model. The
[analysis plan](../../benchmarks/perceptual-degradation-v1/listening-analysis-plan.json)
even fixes variance components from planning assumptions rather than estimating
them from outcomes. The 39-source asymptotic boundary in the
[feasibility report](perceptual-degradation-listening-feasibility-frontier-20260813.md)
is conditional on those assumptions, not a universal law of audio research.

I recommend comparing three explicitly different estimands before main data
collection: strict detectability equivalence, an upper bound on material
impairment, and relative severity ordering. A noninferiority claim about
material impairment must not be relabelled as proof of transparency. Its margin
needs an independent listening interpretation and prospective justification.
Neither failing to detect a difference nor a high bitrate establishes a
non-degraded label.

An exploratory pilot can estimate variance, repeatability, carryover and
session duration. Its sources and outcomes become consumed development
evidence. It cannot certify transparency or independent transfer, and partial
pooling cannot manufacture missing source diversity.

### 3. The sparse-source descriptor has untested construct validity

The [implementation](../../scripts/perceptual_degradation_source_trait_sparse_tonal_descriptor.py)
uses ten blocks spanning the entire file for occupancy, and a 1,024-sample FFT
with a 512-sample hop for spectral flatness and concentration. The spectral
function receives samples without a sample-rate argument. Existing exact-member
runners classify the native-rate channel samples directly.

Consequently, the same window represents 21.33 ms at 48 kHz, 10.67 ms at 96 kHz,
and 5.33 ms at 192 kHz. Its frequency bins also cover different physical bands.
Flatness includes almost the entire spectrum to Nyquist: a high-rate recording
with little ultrasonic energy can be penalized even when the audible event is
broadband. File-relative occupancy also depends on the amount and position of
recorded context. These are structural concerns inferred from the code; this
review has not established that they caused any of the retained failures.

Passing three ideal synthetic fixtures demonstrates implementation behavior,
not that the cutoffs identify the desired class across microphones, rates,
natural spectral slopes and event durations. A frozen cutoff prevents tuning
on a result; it does not itself validate the construct being measured.

The proposed next audit should test rate, context and spectral-envelope
sensitivity on newly preregistered synthetic structures before selecting fresh
natural evidence. Existing candidate outcomes must remain unchanged. Any
replacement descriptor needs its own justification and fresh validation;
reclassifying consumed candidates until one passes is not an admissible repair.

### 4. A successful impulse capture may still be outside oracle support

The [capture specification](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-acquisition-spec.json)
asks for one impulse in 15–30 seconds, with at least five seconds of quiet on
each side. The oracle contract requires four active seconds for subtle analysis
and eight for MUSHRA/ViSQOL. The descriptor and alignment code use different
definitions of activity, so this is a compatibility risk, not a proof that
every permitted capture must fail.

The risk is independently consistent with
[ViSQOL's guidance](https://github.com/google/visqol/blob/master/README.md?plain=1),
which favors active excerpts with limited silence and converts multichannel
input to mono. Padding an impulse with quiet does not create the active content
the metric needs. A capture could close a descriptor gate while leaving the
perceptual gate unsupported.

The clean-capture authorization remains valid, but the scientific role should
be explicit: descriptor challenge, abstention test, or supported listening
stimulus. Keeping sparse material in a challenge set with honest abstention is
different from pretending it contributes calibrated severity. All seven traits
still need appropriate evidence before the existing broad claim can pass.

### 5. Alignment choices can change what impairment means

For a digitally generated controlled encode/decode pair, independent hardware
clock drift is generally not the central uncertainty. Rate conversion and
encoder delay still need exact handling. An initial, explicitly narrower study
can focus on a known digital timebase while preserving drift as a separate
robustness question. That would require a successor scope; it does not turn the
retained drift failure into a pass.

The contract also permits estimation of gain and polarity by channel. Before
constructing metric views, distinguish common level differences from channel
imbalance or relative polarity changes. Correcting the latter away could erase
a stereo impairment we intend to study. Likewise, flexible temporal alignment
needs a check that it does not absorb transient smearing. These are audit
requirements for proposed metric views, not verified current scoring bugs.

### 6. Reference provenance should match the causal claim

An unprocessed, never-lossy source is useful for studying first-generation
coding from clean material. It is not logically necessary for measuring the
incremental effect of an additional controlled operation: an exactly retained
input can define that comparison even when its earlier history is uncertain.
That narrower experiment says nothing about total historical damage.

This distinction could support future transcoding or production-chain work.
It must be a separate reference-eligibility stratum and explicit amendment;
unknown-lineage sources cannot be promoted into the existing clean-reference
population. Natural negatives and generated matched controls answer different
questions and should complement one another.

### 7. Failure of one full-reference model is not failure of every target

The current rule requiring a full-reference pass before no-reference work is
a useful project constraint, particularly when oracle outputs become training
targets. It is not a theorem that a poor full-reference metric makes every
human-trained no-reference estimator impossible. Similarity and judged quality
can diverge; published experiments document concrete examples in
[Manocha et al.](https://arxiv.org/abs/2206.13411).

The alternative would be direct human supervision of a clearly scoped
standalone perceptual target, followed by fresh transfer tests. That is a
possible later research amendment, not authority to start training now. A model
trained only to imitate ViSQOL could inherit its limitations and must not be
validated solely against the same surrogate.

## Research directions worth pursuing

| Priority | Direction | Experiment that would change the decision |
| --- | --- | --- |
| First | Supported reference-based impairment comparison | Does a fixed metric preserve within-source human ordering and control false material alerts on fresh groups? |
| First | Target and measurement validity | Can the probability semantics, activity support and descriptor rate/context behavior be made coherent before real outcomes? |
| Next | Artifact localization and stereo evidence | Can temporal or channel diagnostics predict independently collected artifact judgments, with explicit unsupported regions? |
| Later | Standalone perceptual triage | Do matched-source human targets transfer when genre, production, codec and encoder cues change? |
| Separate possible expansion | Known-master matching or provenance records | Can an independently established reference or signed production record supply the missing historical evidence? |

The most relevant addition to the metric review is
[Google's Zimtohrli](https://github.com/google/zimtohrli), whose design targets
differences near the hearing threshold. Its
[2025 paper](https://arxiv.org/abs/2509.26133) describes an auditory filterbank,
physiological modeling and a DTW/NSIM comparison. The implementation is
[Apache-2.0](https://github.com/google/zimtohrli/blob/main/LICENSE). It predates
this restart and was absent from the original review; it is not a development
that occurred during the pause.

Zimtohrli merits a bounded implementation and data-overlap audit alongside the
already-bound ViSQOL baseline and simple signal-distance controls. Published
performance does not establish LossyTrace calibration. Shared similarity ideas
and overlapping evaluation datasets also mean the two tools cannot simply be
declared independent corroborating evidence. Its alignment and level behavior,
exact dependency closure and reproducibility would need examination before a
separately authorized execution checkpoint. No forced ensemble is necessary;
added value should decide whether complexity survives.

For later no-reference comparisons,
[PAM](https://arxiv.org/abs/2402.00282) and
[Audiobox Aesthetics](https://arxiv.org/abs/2502.05139) are relevant published
baselines. PAM uses audio-language similarity; Audiobox separates multiple
human aesthetic dimensions. Neither publication establishes a predictor of
incremental coding impairment for this program. Their susceptibility to
content, production style and intentional noise would be part of the test,
not an assumption of validity. The
[AudioMOS 2025 challenge](https://arxiv.org/abs/2509.01336) likewise concerns
synthetic-audio quality targets, which are useful context but not substitute
codec-degradation labels.

Neural codecs are a worthwhile eventual codec-held-out expansion, especially
for plausible reconstruction that changes detail. They should enter only after
the initial target is stable; adding that axis now would enlarge the scope
before the present hypothesis has been tested.

## Proposed sequence and decision points

1. **Resolve target semantics and measurement support.** Prepare a prospective
   amendment distinguishing correct-choice probability, condition-level
   audibility and material impairment. Specify the supported domain and the
   separate challenge population. Audit descriptor invariance and which
   transformations may be normalized. Deliver a small set of falsifiable
   requirements, not another objective-completion count.
2. **Choose a feasible first experiment.** Compare strict transparency,
   material noninferiority and within-source ordering designs using declared
   assumptions and sensitivity analysis. A possible pilot envelope is 12–24
   source groups and 4–6 conditions per source, explicitly for protocol,
   variance and model-falsification work, not powered certification. These
   counts are proposals, not selections or recruitment authority. The exact
   sources, conditions, listeners, timing, analysis and consent must be made
   concrete before collection is proposed.
3. **Run one bounded comparison after its prerequisites are frozen.** Audit
   the metric shortlist and eligible development data first. Existing public
   human datasets can support method development through an explicit access
   amendment, with overlap and rights recorded. ODAQ's simulated artifacts
   cannot become actual-codec truth. Test simple baselines and limited metric
   candidates on matched inputs; preserve the entire pilot as development
   evidence and retain failures.
4. **Invest in new human evidence only where it resolves uncertainty.** Use
   actual codec interventions and fresh groups to test the surviving
   reference-based model. Reserve independent evidence before choosing models
   or thresholds. Missing traits or transfer axes limit the claim instead of
   disappearing from the denominator. The broad original gate remains open
   until its full requirements are actually met.
5. **Reassess standalone work from that result.** A useful reference-based
   result, a justified narrower follow-up, or a well-supported negative are
   all legitimate decisions. No-reference expansion needs its own target,
   uncertainty evaluation and transfer evidence. An inability to obtain one
   source or afford one study design is an operational limitation, not a
   scientific demonstration that perceptual estimation cannot work.

The decision to restart should prioritize information gained about the target.
Preregistration remains essential for preventing retrospective tuning, while
exploratory work should be explicitly labelled and contained. Existing consumed
evidence stays consumed; new claims must earn new evidence.

## Verification and current execution state

The repository was clean at review start on `codex/perceptual-degradation`,
at `50d05dfaff1a89db6b726058c93dc0faf58e0f43`, matching both its local upstream
reference and the branch commit verified through GitHub. GitHub confirms that
[CI run 32240914461](https://github.com/ryan-voitiskis/lossytrace/actions/runs/32240914461)
succeeded for that commit and that there is no open PR for this branch. This
is a current check of the historical run, not newly executed tests.

The host reports ten online CPUs and approximately 30 GiB free on the data
volume. The 15 GiB acquisition reserve still matters and must be rechecked
before material work. This review accessed repository text, public aggregate
evidence and primary literature only. No research waveform, listener response,
ODAQ processed condition or row-level score, or sealed evidence was opened.

The prior one-capture authority persists. The physical chain remains
undeclared in the latest committed evidence, and outreach/spending authority
has not been granted. This memo requests no capture or listening action from
the user. It changes no executable plan, threshold, old evidence, public CLI
output or scientific completion state.
