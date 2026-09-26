# Codec-history direction review — 2026-09-27

## Decision and authority

The user approved returning codec-history investigation to the centre of the
project, reviewing whether a genuinely new scoped test is justified, and
otherwise consolidating the inspector and benchmark. The user does not want
human recruitment to become a project dependency.

This successor records that reprioritization. It does not change earlier
experimental contracts, thresholds, consumed results or sealed partitions.
The prior perceptual objective remains unresolved, not successfully completed.
Listening studies, physical capture and perceptual-metric execution are not
prerequisites for the present inspection and history-research work. They are
not executed or newly authorized by this document.

**Disposition:** no new home-grown detector is selected. Consolidate the
existing verdict-free inspector now. Shortlist one external model, Lossprint,
for an implementation/reproducibility qualification before considering a
separately frozen diagnostic screen. No model, retained/provider audio, stored
listening scores or sealed transfer scores were downloaded or evaluated in
this review. Software tests use generated fixtures only.

The scope of the review is the local result archive plus targeted primary-source
searches for decoded-PCM compression identification, AAC quantization detection
and current implementations. It is not a systematic or exhaustive literature
review, and absence from this shortlist is not a scientific rejection.

## What is already ruled out by the local evidence

| Family | Existing evidence | Current decision |
| --- | --- | --- |
| Spectral cutoffs, holes and fixed rules | The factorial fixed Cannam rule had 64.05% case false positives; no feature-v0 representation passed the paired gate. | Useful observations, not safe history claims. |
| Naive and high-frequency-masked CRNNs | Unique-PCM AUCs were 50.75% and 46.31% in the tested development population. | Do not restart the same training intervention or repair thresholds. |
| AAC quantization-lattice search | The fixed rule detected 308/404 positives but alerted on 44/197 negatives; stricter and grouped follow-ups did not yield a safe useful detector. | Already tested, not a new mechanism. |
| MP3 hybrid-transform summaries | Earlier source-dependent results and the completed interpreted ablations supplied no cross-domain survivor. The later combined adapter also had a separate protocol stop. | Preserve both scientific negatives and the protocol stop; do not reinterpret unscored combined outputs. |
| Re-encode/decode projection residuals | Both locked representations detected 0/471 supported MP3 groups at their development-safe fold thresholds and still had negative alerts. | Recompression is not an unexplored escape route. |

Sources: [final identifiability result](decoded-pcm-identifiability-result-20260803.md),
[variant disposition](variant-disposition-20260801.md),
[projection result](codec-projection-result-20260802.md), and
[combined-adapter stop](development-explainable-control-protocol-failure-20260803.md).
Counts belong to different declared populations and must not be pooled.

In particular, the historical [AAC checkpoint](original-reklawdbox-plan.md)
already searched all 1,024 frame offsets, long/start/stop/eight-short windows,
and mono/stereo LR/MS paths. Merely proposing short blocks, stereo analysis or
exact alignment does not establish novelty against that experiment. Its
[redistribution boundary](licensing-boundary.md) also remains unchanged.

Narrowing a future product population is permissible only as a new prospective
question. Excluding observed failures and relabelling the resulting accuracy
as a repaired historical pass is not permissible.

## Primary-source update and shortlist

The external descriptions below were inspected on 2026-09-27. They are
publisher claims, not local results or immutable artifact bindings.

### Lossprint: qualify one external baseline, do not endorse it

The [model card](https://huggingface.co/maxdj/lossprint) describes a native-rate,
dual-resolution mid/side CRNN with downloadable weights and release-disjoint
evaluation. It reports 6 false positives among 2,469 untouched masters. It also
states that masters displaying codec cutoffs were screened out, notes higher
false positives on band-limited material, and leaves subsequent processing and
unseen encoders uncertain. That selection does not resolve our hard-negative
problem. Its score is not a calibrated probability for LossyTrace's population.

This is a new external artifact to assess, not proof of a new physical trace
or a refutation of our CRNN results. A fixed independently produced model
could test whether a different learned representation survives our controls
without another local training search.

The [implementation README](https://github.com/maxdjohnson/lossprint) exposes
the inference interface but describes sampling at most six windows from a
track, whereas the model card describes averaging windows. Those descriptions
are not a bound, identical file-level protocol. Qualification must reconcile
the frontend, model bytes and aggregation in exact source revisions. The
README also requests Rust 1.97.1 or newer; this workspace currently uses 1.94.0.
No runtime upgrade, dependency installation, binary execution or model fetch
was performed. A repository or model-card license label is an intake fact,
not a completed dependency/redistribution review.

### FlacCompagnon: implementation lead, not independent validation

The [project README](https://github.com/craft-and-code/FlacCompagnon) describes
AAC requantization and spectral heuristics, but also explicitly warns that its
detection results are not yet reliable. The AAC family overlaps our already
tested work. The documentation is not evidence for reopening that experiment,
and no companion or third-party implementation was copied or executed.

### Recent codec-identifier paper: insufficient inspected detail

A [2026 DSPA paper](https://doi.org/10.1109/DSPA69176.2026.11476765) advertises
a neural identifier across five codecs, uncompressed audio and varied rates.
Only publisher/search metadata was accessible in this review; full methods,
artifact availability and grouped hard-negative validation were not verified.
It remains a bibliographic lead, not a selected method or a negative result.

## Bounded next step: external-baseline qualification

The next deliverable is one source/metadata-only qualification of Lossprint,
not a scoring run. It must:

1. Bind immutable code and model revisions, verified model bytes, frontend,
   track aggregation, dependency closure, licenses and build/runtime choices.
   Avoid executing unreviewed acquisition or build scripts.
2. Check whether the exact inference path can run reproducibly in an isolated
   environment on the designated external research volume without changing
   this project's toolchain or importing a detector into the public CLI.
3. Specify tests for rate, channel, window-length, padding, score orientation,
   aggregation and wrapper behaviour. Synthetic fixtures can verify software
   behaviour, not its real-music accuracy.
4. If qualified, prepare one prospectively frozen diagnostic screen with
   explicit positive/negative source identities, processing histories,
   grouping, support rules, fixed model/threshold, resource budget, case
   accounting, stopping rule and exact execution-head checks.

No audio is selected from its scores. An unsuccessful qualification ends this
candidate intake; it does not trigger a model or threshold sweep. Unresolved
details stay unresolved rather than being filled with favourable assumptions.

The first diagnostic screen must retain non-codec low-pass, tonal/sparse,
resampled and other production controls alongside codec positives. Generated
signals have known construction histories but do not establish music transfer.
Natural-source negative labels need evidence beyond a lossless wrapper;
applying a codec proves an additional pass, not the starting file's whole past.

Report source-group false alerts, detection, unconditional detection coverage,
abstention and runtime by domain, including failures and unsupported cases.
Low false alerts alone are insufficient if the method never detects anything.
Repeated transformations are not independent sources. Existing consumed
development material can falsify this external baseline, not independently
validate it; training overlap with its private corpus may remain unknown.
Any favourable result requires new, independently sourced grouped evidence
under a separate protocol. Previously sealed transfer partitions stay sealed.

These are design requirements, not a completed preregistration: exact budgets,
identities, numeric acceptance criteria and executable bindings are not yet
selected. No new experiment can be described as frozen or ready to run.

## Useful product work independent of that result

The existing inspector now has an offline `explain` command using the
[inspection guide](../inspection-guide.md). It documents every current source
and measurement field, alternative explanations, null/support semantics,
mono-downmix limits and the difference between a file hash and provenance.
The analysis JSON, measurement implementation, feature version and
`public_verdict_enabled: false` are unchanged.

The existing benchmark remains valuable without a successful classifier:

- [Factorial construction and contracts](../../benchmarks/audio-integrity-v2/README.md)
- [Baseline aggregates and protocol history](../../research/baselines/v2/README.md)
- [Final conditional negative](decoded-pcm-identifiability-result-20260803.md)
- [Digital comparison engineering pass](perceptual-degradation-digital-v5-canary-result-20260908.md)

Do not turn experimental scores into file-health rankings, automatic deletion,
retagging, bitrate guesses or clean-history labels. Future scoped evidence
needs its own validation; no trace detected never certifies never lossy.

Public listening datasets can support an optional later perceptual comparison.
Their ratings attach to their exact stimuli; scores must not be transferred to
new encodes or used as history labels. No listening-data acquisition or human
recruitment is necessary for the present deliverable.

## Verification of this implementation checkpoint

The Rust 1.94.0 locked/offline all-target suite passed all 21 tests, including
three CLI tests. The new tests check the embedded guide, absence of output
files, rejection of an audio argument, documentation coverage of serialized
measurement/source fields, and the unchanged analysis envelope. Rustfmt,
Clippy with warnings denied, and the whitespace diff check passed. The package
file listing includes the embedded guide; no package was published.

Build artifacts were isolated on the designated external research volume.
No dependency or toolchain was upgraded. The old scientific records, decoder,
measurement implementation, library envelope and lockfile are unchanged.
These are software checks, not detector-performance results. The full Python
research suite was not rerun because no Python code or scientific runner was
changed. The existing HEAD's remote CI is green; it does not validate these
uncommitted successor edits. This checkpoint is local, not pushed or released.
