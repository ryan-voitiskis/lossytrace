# Exact-hybrid ablation preregistration — 2026-08-01

Status: frozen before inspecting any case-level v32 or v33 failure values and
before running the new probe on retained audio.

This document narrows the exact-transform work described in
`validation-plan-20260801.md`. It defines measurements and comparisons, not a
lossy-source verdict. All output remains feature version `0`, the release
holdout stays sealed, and the future SQAM codec-only subset is not opened.

## Scope and input population

The ablation targets an obvious MP3 128 kbit/s history only. AAC, Opus,
Vorbis, high-bitrate MP3, and provenance claims remain out of scope.

The first screen uses every observed negative plus every observed MP3-128
controlled positive in the composed 5,280-case development inventory. It does
not use labels from the 280-case future codec-only subset. Source groups are
the indivisible unit for sharding, folds, threshold selection, and reporting.
The public Tier A PCM-parent and controlled-transcode components share 48
source groups and are therefore one canonical `public_tier_a` source-domain
family for folds; treating the two component labels as independent would be
leakage.

The archived v32 measurement is replayed on a fixed checksum-bound subset
before the broader screen. Numeric agreement is required within an absolute
tolerance of `1e-12` for the exact-zero and small-coefficient fractions and
`1e-10` for the mean normalized magnitudes. A replay failure stops the new
screen.

## Fixed front end

- Decode once to mono 44.1 kHz float PCM.
- Analyze the 20-second interval beginning at 5 seconds.
- Use the pinned `oxideav-mp3 = 0.1.3` ISO/IEC 11172-3 32-subband analysis
  filterbank and long-block 36-point hybrid MDCT.
- Treat the first four complete 576-sample granules of each phase as warm-up.
- Do not infer an encoder block-switch sequence.
- Use precomputed, formula-derived analysis and MDCT matrices. Unit tests must
  compare them against the pinned crate's public reference implementation.

## Fixed ablation rows

All fractions use inclusive small-coefficient comparisons. No threshold is
changed after a source-domain result is viewed.

1. **A0 — archived replay.** At input phase zero, divide coefficient
   magnitudes by the RMS of all 576 coefficients in the granule. Measure the
   fraction at or below `1e-4` in coefficient indices 432 through 455. This is
   the locked v32 statistic, without its classification threshold.
2. **A1 — robust subband-relative scale.** For each of subbands 24 through 31,
   use the nearest-rank 75th percentile of that granule's 18 absolute hybrid
   coefficients as its local scale. A subband is measurable only when that
   scale exceeds `1e-4` of the granule-wide RMS. Pool measurable target
   coefficients and report fractions at or below `1e-4`, `1e-3`, and `1e-2`
   of the local scale. The primary A1 statistic is the `1e-2` fraction.
3. **A2 — time-robust aggregation.** Divide the post-warm-up granules into five
   contiguous regions whose sizes differ by at most one. Compute A1 per region
   and use the median of the five region values. A region with fewer than 32
   measurable granules is unsupported.
4. **A3 — phase-stable aggregation.** Repeat A2 at eight equally spaced input
   offsets modulo a 576-sample granule: 0, 72, 144, 216, 288, 360, 432, and
   504 samples. Use the median of the eight supported phase summaries. At
   least six phases must be supported. Report the phase interquartile range
   and full range; do not select the maximum phase.
5. **A4 — content guard.** Apply A3 only when at least half of the non-silent
   granules in every supported phase have at least 10% of coefficients 0
   through 431 above `1e-3` of the granule RMS, and every time region contains
   at least 32 such granules. This is the single preregistered sparse/tonal
   support guard.

The edge corroboration is unchanged from the archived exact-hybrid work:
`spectral_edge_drop_db > 3.0` and
`spectral_edge_persistence >= 0.0015`. It is joined from the checksum-bound
feature-version-0 baseline. Existing transform-alignment fields are excluded.

## Threshold and fold protocol

For each ablation row and each leave-one-source-domain-out fold:

1. On training domains only, select the smallest representable threshold
   strictly above the maximum supported Tier A or Tier B negative score after
   the unchanged edge gate. If no such negative exists, the fold is invalid.
2. Apply the frozen fold threshold to the omitted domain once.
3. Report case and source-group false positives, supported MP3-128 source-group
   recall, support coverage, and the threshold. Do not average away a failing
   domain.

A row is discarded if any omitted domain has a supported hard-negative alert,
if MP3-128 support coverage is below 75% overall or in any domain with at
least ten target source groups, or if it trades the known music and DEMAND
failures. Specifically, supported source-group recall must be at least 90%
overall with a one-sided 95% Wilson lower bound of at least 85%, and at least
85% in every omitted domain with at least ten supported target groups. The
pooled out-of-fold supported-negative source-group alert count must be zero and
its one-sided 95% Wilson upper bound must be at most 2.5%. Case-level
observations from the consumed SQAM invariance failures may be reported only
after all feature definitions above and tool hashes are frozen; they may not
change the design.

The raw statistics are not probabilities. Calibration metrics are therefore
not claimed during this screen. A separately frozen, source-group-disjoint
calibration step with Brier score, reliability bins, and expected calibration
error is required only if a row survives and is proposed as a probability.

## Robustness and performance checks

The selected row, if any, is evaluated without tuning on a separately staged,
ephemeral MP3 transform set covering FLAC/WAV/AIFF wrappers, gain, trimming,
leading silence, sample rate, duration, and content domain. The invariance and
runtime limits remain those in `validation-plan-20260801.md`.

The probe records its own elapsed time. A useful but slow research statistic
is not promotion-ready: integration stops unless the in-process measurement
can meet the frozen p95 overhead limit without a second decode, redundant
full-track FFT, or full-spectrogram-sized allocation.

## Stop rule

At most A0 through A4 are evaluated. There is no threshold repair, post-hoc
union, or new numbered policy. If A4 does not satisfy the observed-domain
safety, support, robustness, and performance gates, LossyTrace remains a
verdict-free measurement toolkit and the unopened subsets stay sealed.
