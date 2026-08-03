# Perceptual-degradation research contract - 2026-08-03

**Status:** frozen before retained-waveform metric execution, human-score
modeling, threshold selection, or opening any sealed LossyTrace label

**Public state:** evidence schema `1`, measurement feature version `0`,
`public_verdict_enabled: false`

## Objective and scientific boundary

Determine whether LossyTrace can estimate material perceptual degradation
caused by a controlled lossy encode/decode operation, rather than infer prior
codec history. Build a deterministic full-reference research oracle anchored
to controlled listening evidence. Train a no-reference estimator only after
that oracle passes its human-calibration gate, and validate any estimator on
source-, domain-, codec-, and encoder-held-out evidence.

The full-reference estimand is perceptual difference between a trusted clean
reference and a signal under test. Causal wording such as "caused by codec C"
is allowed only when the test signal was produced by a controlled, recorded
codec intervention on that reference. For an unknown standalone waveform,
signal evidence cannot distinguish coding from an observationally equivalent
non-codec process. This contract does not relax the decoded-PCM
non-identifiability result.

The public Rust library and CLI remain verdict-free. No research score,
threshold, feature, model, or explanation is eligible for public output under
this program without separate explicit approval.

## Outputs

For a supported reference/test pair the research oracle may report:

- continuous impairment severity with a confidence interval;
- estimated audibility under the declared listener and playback population;
- an artifact profile with evidence strength, not a causal history verdict;
- alignment and normalization provenance;
- evidence support, calibrated uncertainty, and reasons for abstention; and
- the two raw primary-family results.

The categorical research summary has four states:

- `transparent`: no material impairment is supported under the declared
  listening conditions;
- `audible_nonmaterial`: evidence supports audibility but not the material
  severity threshold;
- `materially_degraded`: both audibility and material severity gates pass;
- `indeterminate`: evidence is conflicting, underpowered, or unsupported.

`transparent` does not mean lossless. `materially_degraded` does not establish
which uncontrolled process caused the impairment.

## Operational human targets

The main listening phase will fit listener- and source-aware hierarchical
models to individual responses; raw means are never the sole ground truth.

### Audibility

In the subtle-impairment block, a randomized forced-choice response is
collected before the impairment grade. Audibility is the model-estimated
probability that a trained listener under the declared playback conditions
correctly identifies the test condition rather than the hidden reference.
Chance is `0.5`.

For aggregated condition truth:

- `audible` requires the one-sided 95% lower confidence bound on correct-choice
  probability to exceed `0.5` and the point estimate to be at least `0.75`;
- `not_demonstrably_audible` requires a two-one-sided 5% equivalence test to
  place correct-choice probability inside `[0.45, 0.55]`; and
- all other outcomes are `audibility_indeterminate`.

The equivalence margin is a design margin, not evidence that performance below
chance is meaningful. It will be checked by simulation in the power report
before a main trial is authorized.

### Severity

- Subtle conditions use a BS.1116-style subjective difference grade from `0`
  to `-4`.
- Intermediate and severe conditions use a MUSHRA-style basic-audio-quality
  score from `0` to `100`, with hidden references and required anchors.
- A bridge subset appears in both methods. A frozen hierarchical monotonic
  mapping places both on a `0` to `100` impairment-severity scale, where `0`
  is indistinguishable from the hidden-reference distribution and `100` is
  the most severe anchor region. The mapping is fit on development data only.

For the pre-mapping listening interpretation, a material severity signal is
present when the hierarchical 95% interval excludes both SDG `-1.0` and a
MUSHRA loss of `10` points in the impaired direction. The bridge mapping must
preserve these two reference points. A case is `materially_degraded` only when
the audibility gate also passes. Conditions in the transparent equivalence
region are non-degraded even when produced by a lossy codec.

### Artifact profile

The descriptive profile may contain masking/noise-to-mask evidence, bandwidth
loss, modulation disturbance, transient smearing or pre-echo, spectral holes,
tonality mismatch, stereo-image change, and temporal-localization summaries.
Profile components are continuous with uncertainty. They may say "consistent
with" a scoped artifact; they may not assert prior codec use.

## Primary metric families

Only these families may contribute to the first oracle:

1. `visqol_audio_v3_3_3`, Git commit
   `c3aa2e498e0f7f14202643594335a0b9ee40bdd9`, Apache-2.0. Primary raw output:
   MOS-LQO. Supporting outputs: similarity and patch/frequency summaries.
2. `gstpeaq_proxy_v0_6_1`, Git commit
   `c6e8b23d3374dbc937ef9f7cfbdb3b3f4c864352`, GNU Library GPL v2. Primary raw
   output: proxy ODG. Supporting outputs: available MOVs and time summaries.

All MOVs, a derived 2f-style analysis, and all transformations of the proxy are
one BS.1387-derived family. The 2f formula is not authorized in the initial
plan because published coefficients bind a different PEAQ implementation.
Alignment diagnostics are support evidence, not a third perceptual metric.

The proxy is explicitly non-conforming and must never be named `peaq` in a
public result. Before any execution, a signed-off local evidence record must
confirm the permitted research use of the standard technology and the
subprocess/redistribution boundary. If that record cannot be produced, metric
execution stops for a committed amendment made without inspecting scores.

## Deterministic alignment and support

Alignment operates before either metric and emits a replayable transform
record. Original and transformed hashes are private evidence; public reports
use opaque, recipe-derived IDs.

The initial support limits are:

- decode each signal to planar float64 without destructive normalization;
- preserve and report original sample rate, bit depth, channel count, channel
  map, duration, leading/trailing silence, peak, true peak, and integrated
  loudness when measurable;
- permit mono or stereo only in the first calibration; reject unknown or
  conflicting channel maps;
- search integer delay within `+-2.0 s`, then estimate fractional delay within
  `+-0.5 sample`;
- estimate linear clock drift within `+-100 ppm` and apply it only when the
  drift model materially improves held-out-window alignment;
- estimate one constant gain per channel within `+-12 dB` and polarity;
- allow no more than `2.0 s` or `10%` of the shorter signal, whichever is
  smaller, to be removed from either edge;
- resample only through the frozen oracle resampler and record source/target
  rates, filter, phase, and binary hash; and
- require at least `8.0 s` and `4.0 s` of non-silent aligned material for
  MUSHRA/ViSQOL and BS.1116-style analysis respectively.

Alignment is unsupported when peak ambiguity, time-varying gain, nonlinear
drift, edits, missing/duplicated regions, channel remixing, unstable polarity,
excessive trim, or structural differences make a unique mapping unsafe. Exact
numeric peak-ambiguity and window-consistency cutoffs will be frozen from
synthetic fixtures before retained audio is accessed. That freeze may tighten
support but may not remove a named hard-negative class.

The metric-specific views are deterministic derivatives of the aligned pair:
ViSQOL receives its documented 48 kHz audio-mode view; the proxy receives its
documented sample-rate/channel view. Stereo downmix is reported and prevents a
ViSQOL-only stereo conclusion.

## Data hierarchy and leakage controls

Every derivative of one clean master remains in one `source_group`. Related
performers, recording sessions, releases, collections, and production chains
remain in one `partition_group`. No partition group may cross development,
calibration, model training, thresholding, or final validation.

The planned evidence tiers are:

1. **Synthetic structural fixtures:** no listening truth; alignment and
   schema tests only.
2. **Published development listening evidence:** eligible ODAQ subsets and
   licence-audited public codec evidence; metric behavior and protocol design.
3. **New human calibration:** actual codec encodes, transparent encodes,
   anchors, codec-artifact isolates, matched PCM-only controls, and difficult
   production/natural negatives.
4. **Grouped oracle transfer:** unseen sources and collections, at least one
   unseen domain, codec family, and encoder implementation.
5. **No-reference development:** only if the full-reference gate passes.
6. **Fresh final validation:** generated or acquired after all models,
   thresholds, support rules, and explanations are frozen.

The existing held-out labels and the 280-case future codec-only subset remain
unopened. Their historical labels do not become perceptual-degradation truth.

## Negative and control policy

The study must retain, rather than filter away:

- perceptually transparent lossy encodes as non-degraded conditions;
- naturally bandwidth-limited, quiet, sparse, tonal, synthetic, noisy, and
  clipped references;
- gain, polarity, integer/fractional delay, resampling, bounded drift, and
  leading/trailing-silence controls;
- mastering and production controls such as equalization, limiting, stereo
  width, dither, and sample-rate conversion, with human truth where audible;
- actual codec outputs at multiple bitrates and encoder implementations; and
- current-lossy inputs and unsupported structural edits as explicit abstention
  tests where no trustworthy reference interpretation exists.

A non-codec control is not automatically perceptually transparent. Human
evidence determines impairment. Its non-codec recipe only prevents the oracle
or no-reference estimator from learning "difference implies codec."

## Listening protocol boundary

No main human collection is authorized by this contract alone. Before asking
the user for material participation or recruitment approval, commit:

- complete BS.1116-style and MUSHRA-style instructions and training;
- anonymized randomization and allocation code with deterministic seeds;
- hidden-reference and anchor construction recipes;
- source/condition manifest with licences and group assignments;
- declared DAC, amplifier, transducer, room/noise, level calibration, browser
  or native playback path, and lossless delivery verification;
- session timing, breaks, maximum trials, exclusion criteria, and adverse-event
  stop wording;
- simulation-based power analysis for audibility, equivalence, severity, and
  grouped transfer, including multiplicity control;
- privacy, consent, retention, deletion, compensation, and withdrawal text;
- a synthetic dry run and pilot report that does not inspect main outcomes;
  and
- a fresh score-blind preregistration amendment freezing listener count,
  repetitions, stimuli, and analysis hashes.

Sessions target 20-30 minutes with breaks, no more than 10-15 BS.1116-style
trials per session, and no more than 12 signals in a MUSHRA trial. Listener
training and playback checks are mandatory. Identities are separated from
responses; public artifacts contain only path-free aggregates that satisfy the
declared privacy threshold.

## Full-reference calibration and validation gates

All confidence intervals use a source-group bootstrap with a committed seed
and at least 10,000 replicates. Metrics are reported overall and by domain,
artifact, codec, encoder, bitrate region, and transparent/nontransparent
stratum. Published development datasets used for model selection are excluded
from final evidence.

The full-reference oracle passes only if every condition below holds on fresh
grouped transfer evidence:

1. **Determinism:** repeated runs produce byte-identical path-free records on
   one bound machine and raw family scores agree within `1e-6` across the
   supported reference environments.
2. **Severity ordering:** source-group-bootstrap 95% lower confidence bound on
   Spearman correlation is at least `0.75` overall and `0.55` in every eligible
   primary domain.
3. **Audibility calibration:** Brier score is at most `0.15`, expected
   calibration error is at most `0.10`, and the 95% lower confidence bound on
   ROC AUC is at least `0.75`.
4. **Transparent safety:** the upper 95% confidence bound on the
   `materially_degraded` rate for human-transparent lossy conditions is at most
   `0.10`, with a point estimate at most `0.05`.
5. **Material sensitivity:** the lower 95% confidence bound on sensitivity for
   human-material conditions is at least `0.80`.
6. **Coverage:** supported coverage is at least `0.80` overall and `0.60` in
   each eligible primary domain, while every named unsupported reason remains
   visible.
7. **No subgroup reversal:** no eligible codec, encoder, domain, or artifact
   stratum has a statistically supported reversed severity relationship.
8. **Added value:** the frozen two-family mapping must outperform each single
   family and simple signal-distance baselines by at least `0.02` absolute
   Brier score or `0.05` severity correlation on grouped transfer. If it does
   not, the simpler surviving full-reference result is preferred.

Failure of a metric family does not permit post-hoc replacement. The valid
outcomes are reject the oracle, retain a simpler full-reference-only result,
or preregister a new study without opening the final holdout.

## No-reference eligibility and gates

No-reference work begins only after a committed full-reference result passes
all calibration gates. The estimator may learn from raw audio plus oracle and
human development targets, but never from filenames, containers, tags,
declared codec, bitrate, encoder, partition, or construction metadata.

Training and evaluation are grouped by source and collection. Report at least
four non-overlapping transfer views: source-held-out, domain-held-out,
codec-held-out, and encoder-held-out. A single pooled split is insufficient.
Support and abstention are learned or frozen without deleting difficult
negatives.

Before fresh validation the model, preprocessing, weights, target mapping,
thresholds, support detector, abstention policy, and explanations are frozen by
hash. The no-reference estimator advances only if it independently satisfies
the transparent-safety, material-sensitivity, coverage, subgroup, and
calibration gates above and loses no more than `0.10` severity correlation and
`0.03` Brier score versus the full-reference oracle on human-labeled evidence.
Codec- and encoder-held-out gates must each pass; average success cannot hide a
failed transfer view.

## Stop rules and successful negative outcomes

Stop the current candidate before further tuning if:

- alignment cannot meet deterministic support without excluding a named hard
  negative or transparent codec condition;
- the legal/conformance boundary for the proxy is unresolved;
- either primary family is non-replayable under its binding;
- development evidence shows a primary domain or artifact with reversed or
  absent association and a predeclared support reason does not explain it;
- human calibration, transparent safety, or grouped transfer fails;
- performance is attributable to codec, bitrate, source, collection, or
  encoder leakage;
- a no-reference result fails any one held-out axis;
- the 15 GiB disk reserve or six-worker ceiling cannot be maintained; or
- a proposed correction would require opening sealed evidence or changing a
  threshold after seeing its result.

A rigorous negative result is successful completion. The final recommendation
must choose exactly one of:

- `reject_perceptual_estimation`;
- `retain_full_reference_only`;
- `continue_no_reference_research`; or
- `freeze_blind_final_validation`.

No recommendation implies merge, release, public CLI verdict, Reklawdbox
integration, or deletion of retained evidence.

## Reproducibility, resource, and publication boundary

- Sustained work uses at most six workers on the ten-CPU host.
- A 15 GiB free-space reserve is checked before every acquisition or material
  generation step. Corpus duplication is prohibited; processing is streamed
  or uses bounded temporary storage.
- Tools, models, resamplers, codecs, decoders, listening software, manifests,
  seeds, and source records are version- and SHA-256-bound.
- Private paths, listener identity, audio, model caches, and licensed source
  material stay outside Git. Public evidence is path-free and aggregate.
- Before each push: inspect status and staged diff, reject audio/models/caches
  and large files, scan credentials and absolute paths, and run all relevant
  gates.
- Changes after score access require a dated correction recording bytes/cases
  accessed, the reason, the affected estimand, and whether evidence is
  consumed. Silent edits are prohibited.

## Authorized next step

Commit this contract, its literature review, machine-readable plan, validator,
and tests before running either perceptual metric or accessing retained audio.
Then implement and test only the score-free alignment, schema, tool-binding,
licence-gate, and synthetic-fixture layers. Metric execution remains blocked
until the proxy legal record and exact binary hashes are present.
