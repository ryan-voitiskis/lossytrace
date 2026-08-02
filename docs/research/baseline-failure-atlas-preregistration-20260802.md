# Baseline replay and failure-atlas preregistration - 2026-08-02

**Status:** frozen before any new full-population external-detector score is
opened

**Purpose:** establish comparable failure behavior, not select or tune a
candidate

**Holdout state:** future SQAM codec-only scores unopened; release labels
unopened; no new external-transfer evidence acquired

## Questions

1. How does the exact published Cannam detector behave across all 5,280
   already-consumed LossyTrace development cases?
2. Which source domains, positive codec classes, and genuine-PCM negative
   classes explain its errors?
3. How does its behavior compare with retained learned and explainable
   baselines when the task and population are made explicit?
4. Which failure families must the successor factorial benchmark preserve?

The null for the external detector is that its apparent separation is not
stable across source domains and hard-negative classes. No threshold search is
needed to test that null because the published file rule is fixed.

## Evidence populations

### P1 - general consumed population

Use the existing composed observed-development manifest:

- 5,280 cases;
- 597 source groups;
- 1,734 negative cases;
- 3,546 controlled-positive cases; and
- eight retained source-domain labels.

This population is appropriate for a general lossy-versus-original detector.
It includes MP3, AAC, Opus, and Vorbis positives, codec and wrapper transforms,
genuine PCM, low-pass and resampled PCM, sparse and tonal material, full mixes,
and earlier transfer populations whose scores are already consumed.

The composed-manifest SHA-256 must equal
`e19b5b408fedf348fa9b6499d5cdd1b6b734d84b19b895d5b0a528f0c4423b7a`
before execution.

### P2 - MP3-128 comparison population

Derive a view containing all 1,734 P1 negatives and the 527 controlled
MP3-128 positive cases used by the exact-hybrid and codec-projection studies:

- 2,261 cases total;
- seven canonical source-domain families after the existing public-source
  aliasing; and
- 597 negative source groups plus the matched positive groups represented in
  the retained reports.

P2 permits a task-matched comparison with MP3-specific methods. It must not be
used as the headline population for a general multi-codec detector.

### Exclusions

- the 280 future-only SQAM cases;
- all release-held-out labels;
- any newly acquired or newly sealed transfer data;
- private blind case studies not already represented in P1; and
- unsupported current lossy originals when a baseline cannot decode them.

No exclusion may be made because a score looks surprising.

## Baselines and reproduction status

### B1 - Cannam published-weight CNN

Run the exact repository revision
`7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b` with plugin output
`vamp-lossy-encoding-detector:lossydetector:cf`.

Freeze the published decisions exactly:

- a window is positive when `cf >= 0.5`;
- a file is positive when at least 25% of its windows are positive;
- the complete retained file is supplied to the plugin without an additional
  crop;
- no resampling, gain normalization, channel remix, denoising, or silence
  removal is inserted by LossyTrace; and
- the plugin weights, architecture, and host output are unchanged.

The runner must record repository revision, plugin key, host hash, plugin
binary hash, input audio hash, window count, positive-window fraction, and the
fixed binary label. Existing complete partials may be resumed only when every
binding matches. Run with one low-priority worker.

The earlier 112-file, eight-source pilot remains a separate audit fixture. Its
archived report and member hash must verify before P1 starts. The retained
compact corpus contains lossless-wrapper equivalents for 104 of the 112 case
IDs; re-score those cases and compare their fixed binary decisions with the
historical report as an environment regression. The eight original
private-source sharp-low-pass files were not retained in the compact corpus,
so an exact 112-input replay is impossible. Preserve that limitation rather
than regenerating alleged equivalents after seeing their results. P1 still
contains consumed sharp-low-pass negatives from independent source domains.
The audit output cannot modify B1.

### B2 - retained feature-version-0 measurements

Do not turn feature version `0` into a classifier. Reuse the byte-reproducible
schema-2 aggregate with SHA-256
`e41e2da69c78a8f34dfcdcc3b8c3f8d1b9bac5f28229b8d355b53eab74679e1d`.
Its support and within-source deltas are descriptive baselines only; no
accuracy or calibration metric exists.

### B3 - retained explainable codec-specific probes

Reuse, without new thresholds:

- the AAC quantization-lattice fixed-boundary reproduction;
- exact-hybrid A0-A4;
- codec-projection R1 and R2; and
- container/wrapper equivalence.

Their committed path-free reports and recorded raw-input hashes are the replay
evidence. They are already rejected candidates. The atlas may compare failure
classes and support, but may not recombine their scores or call them an
ensemble.

### B4 - paper-aligned robust learned baseline

Koops, Micchi, and Quinton (ISMIR 2024) publish the architecture and masking
strategy but no reference implementation or weights. A LossyTrace
implementation is therefore a replication, not an exact replay. It is deferred
until the factorial benchmark manifest and train/development partitions are
frozen. It must then include both the naive and random-high-frequency-mask
training conditions under identical source-grouped folds.

B4 cannot use P1 as independent validation because P1 has already informed
the research direction. It will be evaluated on grouped development folds and
later encoder/source-collection transfer only. Differences from the paper
must be recorded explicitly.

## B1 execution and output contract

The raw report is private schema `2` and contains per-case identities. It must
state:

- `evidence_partition: observed_development`;
- `holdout_scores_opened: false`;
- `decision_rule.window_threshold: 0.5`;
- `decision_rule.file_positive_fraction_threshold: 0.25`;
- `thresholds_retuned: false`;
- the manifest and tool hashes; and
- one deterministic result per manifest case.

The committed aggregate is path-free and rejects keys or values containing
case IDs, audio hashes, source-group identifiers, private paths, or absolute
machine paths. It contains only counts, named public source domains/classes,
summary statistics, fixed-rule metrics, confidence intervals, and input
hashes.

## Fixed metrics

### Case level

For P1 and P2 report:

- true positives, false negatives, true negatives, and false positives;
- recall, specificity, false-positive rate, precision, accuracy, balanced
  accuracy, and F1;
- two-sided 95% Wilson intervals for binomial rates; and
- the distribution of positive-window fraction by expectation, class, and
  source domain.

Precision and accuracy are labelled selected-population quantities because P1
does not estimate real-library prevalence.

### Source-group level

- A negative source group alerts if any supported negative case in that group
  is positive.
- For a named positive class, a source group is detected if any case in that
  group and class is positive. If a class contains repeated variants of one
  setting, also report the all-variants and median-score summaries without
  substituting them for the primary any-case definition.
- Report counts and Wilson intervals overall, by source domain, and by
  predeclared negative/positive class.
- Never pool a group containing both negative and positive derivatives into a
  single "correct" or "incorrect" label.

### Calibration diagnostics

The plugin's `cf` output and positive-window fraction are not called
probabilities. Reliability bins, Brier score, and expected calibration error
may be reported only as diagnostics against the selected P1 labels, with an
explicit statement that they do not establish transferred calibration.

## Predeclared failure atlas

Report each slice even when small:

### Negative histories

- untouched/provider-confirmed PCM;
- trusted commercial lossless PCM;
- gain, trim, leading-silence, dither, and bit-depth-only;
- ordinary and sharp low-pass;
- PCM resampling and low sample rate;
- container-only rewrites;
- sparse/tonal synthesized instruments;
- speech, noise, and other non-music domains where already consumed; and
- lossy-original diagnostic rows separately from eligible prior-history
  negatives.

### Controlled-positive histories

- codec family;
- bitrate or quality setting;
- encoder implementation where recorded;
- source domain;
- post-codec gain, trim, resample, and wrapper variant; and
- current lossy original versus lossless wrapper where decodable.

### Co-failure comparisons

Only aggregate overlap with retained baselines may be published. Compare
whether negative failure classes align with:

- high-frequency bandwidth limitation;
- sparse/tonal content;
- source-domain failures of earlier CNN/CRNN systems;
- AAC quantization hard negatives;
- exact-hybrid failures; and
- codec-projection failures.

No post-hoc subgroup becomes an exclusion or support rule.

## Frozen interpretation rules

1. B1 is rejected for a safe scoped assessment if it produces any Tier A or
   predeclared hard-negative source-group alert. This restates the existing
   gate; it is not fitted to B1.
2. High recall cannot compensate for a safety failure.
3. A P1 result does not estimate universal accuracy or real-library positive
   predictive value.
4. A failure concentrated in bandwidth-limited, sparse, historical, or
   denoised content is evidence of a content shortcut, not evidence that those
   sources are secretly lossy.
5. A success on one encoder or cutoff setting does not transfer to another
   setting without an encoder/settings-held-out test.
6. B2/B3 negative results remain negative; the atlas cannot tune or combine
   them.
7. The future benchmark must retain, not clean away, every observed genuine
   hard-negative family that causes a baseline failure.

## Stop and continuation decision

After the atlas is frozen:

- do not tune B1 or train a derivative of its weights;
- do not search an alternative file aggregation threshold;
- do not promote an empirical support filter based on its failures;
- use the failure atlas only to test balance and coverage of the factorial
  benchmark; and
- continue to mechanism discovery only through representations that are
  materially different from the rejected baseline families.

If the exact B1 revision cannot be reproduced, retain the environment and
error evidence, stop the run, and resolve only the reproducibility defect. Do
not substitute a newer fork, architecture, model, host, or weights under the
same baseline name.

## Change control

This preregistration is frozen by its first Git commit. After the first new P1
score is opened, any change requires a dated amendment and the original run
remains retained. Implementation-only corrections may restart a separately
bound run if they occur before aggregate results are inspected and do not
alter the detector, inputs, decision rule, or metrics.
