# Independent validation plan

**Frozen:** 2026-08-01 before baseline scoring or candidate tuning
**Repository baseline:** `3526bf5a49039466203f66dcca439e0e46c59ab8`
**Public state:** experimental measurements only; no provenance verdict

## Decision boundary

LossyTrace may improve and version its measurement and evaluation machinery
without enabling a public verdict. A public positive assessment remains
disabled unless one frozen candidate passes every independent-validation gate
below. Failure of any safety, independence, invariance, or reproducibility
gate keeps the output verdict-free even when recall is promising.

## Evidence partitions

1. **Observed development evidence.** The 5,280 retained cases whose feature
   scores or labels were already consumed by earlier research may be used for
   baseline measurement, failure analysis, feature removal, and ablation.
   Results on these cases are never described as independent validation.
2. **Codec-only transfer holdout.** The 280 retained SQAM MP3, Opus, and Vorbis
   cases not scored by the earlier candidate stay unopened until a candidate,
   implementation hash, policy, support rules, and analysis are frozen. They
   test codec transfer only because their 70 source groups already occur in
   observed SQAM evidence.
3. **Release holdout.** The existing sealed release labels stay unopened. They
   are not a substitute for a fresh external-transfer set after the prior
   candidate sequence consumed MUSDB18-HQ, SQAM, DEMAND, and MAESTRO.
4. **Fresh independent transfer.** A promotion attempt requires at least 150
   Tier A source or partition groups that are disjoint from all development
   data and previous candidate selection. It must include genuinely lossless
   PCM negatives, difficult negatives, and controlled lossy-to-lossless
   variants. At least one encoder implementation and one source domain must be
   unseen during candidate selection.

Every transform of one master stays in the same `source_group`; related
performers, sessions, collections, or recording chains stay in the same
`partition_group`. Split validation fails closed if either identity crosses a
boundary. Case-level random splitting is prohibited.

## Promotion criteria

All thresholds below are frozen before baseline scoring. They are evaluated at
source-group level as well as case level, with Wilson 95% confidence intervals.

### False-positive control

- Zero positive assessments across every Tier A negative case and source
  group in the fresh independent transfer set.
- The one-sided 95% Wilson upper bound for the Tier A source-group false-
  positive rate must be no greater than 2.5%. With zero observed errors this
  requires at least 150 independent negative groups. This is the minimum
  experimental-promotion bar, not a mature-product claim; demonstrating an
  upper bound near 0.5% would require roughly 765 clean independent groups.
- Zero positives in each predeclared hard-negative class: sharp low-pass,
  gentle or natural bandwidth limitation, low sample rate, sparse or tonal
  content, PCM-only resampling, gain-only, trim/silence-only, bit-depth or
  dither-only, and container-only rewrites.
- A persistent cutoff or bandwidth limit alone can only reduce support or
  remain an experimental measurement. It cannot cause a positive assessment.

### Recall and coverage

- For each scoped obvious low/medium-bitrate codec and encoder class, at least
  90% of supported source groups must be detected, with the 95% interval
  reported and a lower bound of at least 85%.
- At least 75% of positive source groups in every scoped class must have enough
  support to be assessed. Unsupported cases are reported, never counted as
  successful negatives.
- High-bitrate AAC/MP3 and difficult Opus/Vorbis classes may remain
  unsupported or undetected, but must not weaken the false-positive gate.
- Lossy originals are measured for equivalence and diagnostic coverage only.
  A file whose current codec is lossy is not eligible for a prior-history
  provenance assessment.

### Calibration and policy isolation

- Feature selection, normalization, support rules, score direction, and any
  decision threshold are fixed using observed development evidence only.
- If a continuous score is used, calibration is fitted on source-group-
  disjoint development folds and reported with reliability bins, Brier score,
  and expected calibration error. No final-transfer label may alter the score
  or threshold.
- Every research positive must contain at least two separately named evidence
  families. Correlated summaries from the same transform calculation count as
  one family.
- An ablation remains eligible only if its source-domain holdout result is safe
  in every fold. A strong pooled result cannot hide a failing source domain.

### Robustness and invariance

- Container-only FLAC/WAV/AIFF variants: zero support or assessment changes.
- Non-clipping gain changes at -3 dB and -12 dB: zero assessment changes;
  continuous scores must have 99th-percentile absolute delta at most 0.02 and
  maximum delta at most 0.05 after normalization.
- Leading silence and deterministic trim offsets: zero assessment changes;
  the same score-delta limits apply when the analyzed content overlaps.
- Duration checks at 10, 30, 60, and 120 seconds: no negative may escalate to
  positive; at least 95% of supported obvious-positive groups must agree with
  the 120-second result from 30 seconds onward.
- Sample-rate and PCM-resample controls: zero positive escalations. Raw scores
  need not be invariant because resampling changes available evidence.
- Low-rate, very short, quiet, or sparse material must fail to `unsupported`
  or neutral measurements rather than fabricate evidence.

### Reproducibility and performance

- The final report binds schema versions; code, runner, manifest, fingerprint,
  policy, and toolchain hashes; encoder commands and versions; and the frozen
  split identities.
- Repeating a run with the same inputs produces identical non-timing evidence.
- No private path, per-case private identity, audio, feature cache, or model
  artifact is committed to Git. Mandatory CI uses deterministic synthetic
  fixtures only.
- The measurement adds no second decode, no redundant full-track FFT, and no
  full-spectrogram-sized clone. The isolated-process p95 runtime overhead is at
  most 10%, with peak memory reported.

## Disciplined candidate sequence

1. Reproduce the current feature-version-0 measurement baseline on observed
   development evidence without fitting a verdict.
2. Evaluate feature support, class distributions, paired lossy-original versus
   lossless-wrapper equivalence, source-domain separation, and the frozen
   invariance checks.
3. Shortlist at most two explainable candidates. The starting shortlist has
   one direction: the exact MP3 hybrid-transform front end from v32 with new
   content-dependence guards and aggregation. The v29 confirmation machinery
   may be used as a diagnostic but its failed policy is not a candidate. The
   v32+v33 union is diagnostic evidence only and is not a candidate.
4. Run one factor at a time: support guard, content normalization, transform
   statistic, then corroborating family. Keep a fixed ablation table and do
   not create a new numbered candidate for every threshold observation.
5. Freeze or stop. Open the codec-only transfer subset once only if the
   observed source-domain gates support a defensible candidate. Acquire and
   seal fresh Tier A transfer evidence before any release-gate attempt.

The release holdout remains sealed if the candidate fails earlier gates. Even
a passing independent evaluation requires explicit review before changing the
public interface or integrating with Reklawdbox.
