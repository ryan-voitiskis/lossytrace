# Decoded-PCM lossy-history identifiability result

Date: 2026-08-03

Decision: close the current program as a rigorous conditional negative; do not
preregister a new representation and do not open transfer evidence

## Bottom line

Across the frozen factorial development benchmark, no completed and
interpreted detector or measurement demonstrates a source-independent trace of
prior lossy compression at the required paired-effect gate. High apparent
recall comes from content and bandwidth shortcuts, near-universal positive
decisions, or domain-specific effects. The nearest descriptive measurement
still misses both quantitative gate levels, has incomplete support, and
reverses in an eligible source domain.

LossyTrace should therefore remain at a verdict-free measurement boundary:
`feature_version: 0`, `public_verdict_enabled: false`. There is no frozen
survivor, so encoder-transfer and external-transfer scores remain unopened.
The proposed masking-conditioned coefficient-censoring and transient pre-echo
representations are not implemented under this goal; doing so despite the
failed discovery gate would turn a falsifiable program into another feature
search on consumed evidence.

This result is conditional, not a mathematical impossibility theorem. It says
that the tested fixed, descriptive, learned, exact-transform, and
analysis-by-synthesis families do not justify a safe decoded-PCM history claim
under this six-domain source and processing matrix.

## Methodology

The program first separated three claims: artifact triage, scoped history
assessment, and actual provenance. Only the second can even be tested from PCM
alone; provenance needs reference or chain-of-custody evidence.

The factorial v2 mechanism-development population contains 9,653 cells from
527 source groups and six source domains: 4,988 controlled lossy positives and
4,665 genuine or difficult PCM negatives. Exact decoded-PCM duplicates collapse
to 7,701 analysis units, while 9,513 retained WAV/FLAC/AIFF representatives
remain wrapper-invariance checks. Sources are crossed with codec, encoder,
setting, decoder, resampling, gain, trim, silence, low-pass, and container
factors rather than allowing those factors to act as labels.

Every interpreted baseline was frozen before waveform analysis or training.
The primary discovery statistic is the median positive-score minus exact
matched-reference score per source group after duplicate-PCM-pair collapse.
The fixed gate requires at least 90% positive direction, a one-sided 95%
Wilson lower bound of at least 85%, and no reversed eligible source domain.
Classification accuracy cannot substitute for this paired mechanism test.

## What the accuracy numbers mean

| System or measurement | Headline result | Paired mechanism result | Failure |
| --- | --- | --- | --- |
| Cannam published fixed rule | 91.82% positive recall; 64.05% negative FPR; 64.82% selected-population accuracy | 246/527 = 46.68% direction; 43.13% lower bound | Alerts in 488/527 negative groups; 0/53 direction in NSynth test and 1/200 in NSynth train |
| Feature-v0 spectral edge, nearest descriptive row | No classifier or accuracy claim | 236/269 = 87.73%; 84.06% lower bound | Only 269/527 groups supported; NSynth train reverses to 36.36% |
| Naive Koops-style CRNN | 98.30% recall; 95.48% negative FPR; 52.98% accuracy | 372/527 = 70.59%; 67.22% lower bound | Alerts in 518/527 negative groups; unique-PCM AUC 50.75% |
| Random-high-frequency-mask CRNN | 100% recall and 100% negative FPR; 51.67% accuracy | 312/527 = 59.20%; 55.64% lower bound | All-positive decision; unique-PCM AUC 46.31% |
| Historical exact-hybrid A0-A4 | 14.3-23.3% supported MP3-128 recall | No stable cross-domain survivor | Every row had a negative alert; zero recall in DEMAND/MAESTRO and public Tier A |
| Historical codec projection R1/R2 | 0/471 supported MP3-128 groups detected | No survivor | Each row had a negative alert; scores strongly content-correlated |

This is why the reported accuracy of a lossy detector is not portable without
its negative population. Cannam is useful as a sensitive artifact probe on
ordinary music, but a 64.05% false-positive rate on the hard factorial negative
matrix makes its 91.82% recall unsafe as history inference. The learned models
make the same point more starkly: nearly perfect recall and chance-level
ranking coexist because almost everything is called positive.

## What we learned from Cannam and related work

1. Spectral holes and bandwidth edges are real codec effects, but natural
   bandwidth, sparse spectra, historical recordings, denoising, mastering, and
   resampling create the same appearance.
2. Track-disjoint splits are insufficient. Source collection, session,
   performer, encoder family, setting, decoder, and processing path need group
   boundaries.
3. Random high-frequency masking is a useful shortcut diagnostic, not evidence
   of identifiability by itself. Here it worsened paired direction and produced
   an all-positive classifier.
4. Explainability is not transfer. Exact-hybrid and projection-residual
   mechanisms are physically meaningful yet remain source dependent.
5. A softmax output or positive-window fraction is not calibrated uncertainty.
   Calibration is irrelevant until a representation first survives sign,
   support, and domain gates.
6. Multiple summaries of one transform are not independent corroboration.
   Historical R1/R2 case correlations were Pearson 0.875 and Spearman 0.932;
   group correlations were 0.910 and 0.870.

The Koops-style replication is paper-aligned, not exact: author code, weights,
channel counts, optimizer details, and complete training defaults were not
published. LossyTrace's complete domain folds and hard negatives are also
stricter than the reported private-library task. The result therefore does not
claim that the paper is irreproducible; it shows that this intervention does
not survive the present history-identification contract.

## Retained-control protocol stop

The separately committed v2 adapter attempted to replay A0-A4 and R1/R2 as raw
paired controls over all 4,665 negatives and 1,367 MP3 positives. A0-A4 stopped
at 5,735/5,895 representatives because the bound oracle rejected the remaining
160 three-second cases as insufficient PCM before reaching the adapter's only
authorized unsupported state. The support mapping was not broadened after
scores existed.

R1/R2 completed, passed wrapper invariance, and produced a byte-identical
checkpoint replay. Their frozen public analyzer required both complete
reports, so R1/R2 scores remain uninterpreted rather than introducing a
projection-only analysis after score opening. The protocol failure adds no
paired evidence and does not erase the older complete R1/R2 rejection.

## Reproducibility and robustness

- Fixed and CRNN systems scored every retained wrapper representation and
  passed exact equality for 1,398 multi-wrapper PCM identities.
- The scoped projection control passed exact equality for 1,391 multi-wrapper
  PCM identities and replayed its 5,895-result private report byte-for-byte.
- Per-artifact and per-fold writes are atomic and commitment-bound; the CRNN
  resumed safely after a machine restart without retraining completed folds.
- Public aggregates reject private identities, paths, audio hashes, model
  artifacts, and raw case rows.
- Mandatory validation currently passes 321 Python tests (12 environment-gated
  skips), all root Rust targets, four exact-oracle tests, and six
  projection-oracle tests.

The benchmark and runners are reusable research infrastructure even though the
scientific result is negative. They make future claims pay the correct costs:
paired sources, hard negatives, complete domain folds, wrapper invariance,
sealed transfer, and explicit abstention.

## Gate decision

No completed interpreted representation passes the 90% / 85% paired gate.
The nearest row, spectral-edge height, is below both levels, supported on only
51.04% of source groups, and reverses in NSynth train. Cannam, naive CRNN, and
masked CRNN are much farther away. Historical A0-A4 and R1/R2 are already
rejected; their v2 control stage cannot add an admissible result.

Accordingly:

- new mechanism representations preregistered: **zero**;
- encoder-transfer scores opened: **no**;
- external-transfer scores opened: **no**;
- public history verdict authorized: **no**; and
- current research disposition: **conditional non-identifiability for the
  tested methods and scope**.

Fitting a hierarchical variance model is not warranted after every eligible
input representation fails the more basic sign and domain gate. Such a model
could quantify the already-visible source interactions, but it could not turn
an unstable or reversed within-source effect into a survivor and would add
degrees of freedom on consumed development evidence.

## Limitations

- The factorial population is deliberately difficult and is not a real-library
  prevalence sample; its precision and accuracy are selection-dependent.
- The result does not cover every possible codec, encoder, representation, or
  future theory and is not a proof that two arbitrary PCM arrays cannot differ.
- The CRNN is an independent paper-aligned implementation, not an exact author
  replay.
- The retained v2 exact/projection atlas is protocol-incomplete, and complete
  R1/R2 v2 scores were intentionally not interpreted.
- No transfer score was opened, so there is no independent-transfer accuracy
  claim—only the stronger decision that no development survivor justified
  consuming that evidence.

## Recommended next direction

Treat this subsystem as a falsification benchmark and keep the CLI descriptive.
For product-grade provenance, move the problem boundary toward reference-backed
verification: known-master fingerprints, signed production/export records,
watermarks, or chain-of-custody metadata. Those approaches can supply
information that decoded PCM alone has discarded.

If decoded-PCM mechanism research is revisited later, start a new goal with new
development evidence and a fresh preregistration. Masking-conditioned
coefficient censoring and transient pre-echo asymmetry remain reasonable
hypotheses, but this consumed benchmark supplies no gate-passing basis to tune
them now. Do not reopen the current transfer partitions merely to find out.

## Evidence bindings

| Evidence | SHA-256 |
| --- | --- |
| development-baseline plan | `9d483ec87365aa4253fa5997458f2fab604b27f029ce42ca20d917f79caa51b0` |
| Cannam path-free aggregate | `6531911c06f6ceaa7567e16a24bfba135b9aeabedbd6b15b1063d17d79de20ff` |
| feature-v0 path-free aggregate | `62bd6ce9c6f104b91b682ce07216760471cab7c87cded0016cc8153577a1132a` |
| CRNN path-free aggregate | `f42d4f1844524ef25f998810394a62361cd31efb42b0b38893ff42c706fde84c` |
| explainable-control adapter plan | `f654ddcaaa7bf331536cdd9e86117fe45d836f921fef67efafedc9903a367c4a` |
| explainable-control protocol failure | `6206ca5c61e42a238ee0530a13688fb22d491e1f47850f1aa7cd22267f6c4e80` |
| machine-readable identifiability decision | `a58a3d1cd15fad0defde19fdc3a0fd804f2a2566bb118edb27f41b4d5f9f1b9f` |

The machine-readable decision is
[`identifiability-decision-20260803.json`](../../research/baselines/v2/evidence/identifiability-decision-20260803.json).
