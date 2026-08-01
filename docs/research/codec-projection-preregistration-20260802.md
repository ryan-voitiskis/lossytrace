# Codec-projection feasibility preregistration - 2026-08-02

**Status:** frozen before generating a new codec-projection score or opening
the archived exploratory recompression scores.

**Repository parent:**
`8c044cdce6a927f5034b5d9bfc33a1d784e60b5e`

**Public boundary:** evidence schema `1`, measurement feature version `0`,
`public_verdict_enabled: false`. This study does not change the Rust library or
CLI evidence contract.

## Question, hypothesis, and null

Question: can a controlled MP3 encode/decode projection produce a
source-independent, explainable measurement of an obvious prior MP3-128
history when the analyst has only decoded PCM in a lossless wrapper?

Hypothesis: after canonical gain and sample-rate normalization, PCM that has
already passed through an MP3-128 encoder is closer to a local fixed-point path
of a controlled MP3-128 projection than genuinely lossless PCM. Consequently,
the first and second projection residuals should retain more similar energy and
direction on prior-MP3 material.

Null: the relationship between successive projection residuals is determined
by content, source domain, encoder mismatch, and transforms rather than prior
MP3 history. Under the null, a threshold that is safe for every observed
negative domain will fail the support/recall gate, or a useful threshold will
alert on at least one hard-negative group.

## Scope and partitions

- Target history: MP3 at constant 128 kbit/s, decoded into a lossless wrapper.
- Out of scope: AAC, Opus, Vorbis, high-bitrate MP3, lossy originals as
  assessment targets, codec attribution, and provenance verdicts.
- Design/evaluation evidence: the already-consumed 5,280-case observed
  baseline only. The primary screen contains all 1,734 genuinely lossless
  negatives and the 527 controlled MP3-128 positives used by the completed
  exact-hybrid screen.
- The 280-case future SQAM codec-only subset, release-held-out labels, and any
  newly acquired transfer labels remain unopened.
- `source_group` is indivisible. Related sessions, performers, collections,
  or recording chains remain in one `partition_group`. The PCM-parent and
  controlled-transcode components sharing the 48 public Tier A groups form one
  canonical `public_tier_a` domain. Case-level random splitting is prohibited.

## Controlled projection

There is one development encoder implementation: the LAME library exposed by
FFmpeg's `libmp3lame` encoder. The executable, linked library, full version
output, and commands are recorded and hashed at run time. The preflight system
reported FFmpeg 8.1.2 and LAME 4.0; those observations are not a portable
substitute for the run-time bindings.

The fixed encoder setting is MPEG-1 Layer III, CBR 128 kbit/s, 44.1 kHz,
stereo, joint stereo enabled, bit reservoir enabled, ABR disabled, and Xing
gapless metadata enabled. Metadata and chapters are removed. FFmpeg bitexact
format/codec flags are used where supported. There is no encoder bank and no
claim of encoder independence. A future one-shot transfer, if reached, must
include an unseen MP3 encoder implementation.

The encode arguments after the input are fixed as
`-map_metadata -1 -map_chapters -1 -fflags +bitexact -flags:a +bitexact -ar
44100 -ac 2 -c:a libmp3lame -b:a 128k -abr 0 -reservoir 1 -joint_stereo 1
-write_xing 1 -f mp3`. Decode arguments after the input are fixed as
`-map_metadata -1 -map_chapters -1 -fflags +bitexact -flags:a +bitexact -ar
44100 -ac 2 -c:a pcm_s16le -f s16le`. The runner adds only machine-local input
and output endpoints plus `-nostdin -hide_banner -loglevel error -y`.

**Pre-observed implementation clarification - 2026-08-02:** a deterministic
synthetic-tone command smoke test, performed before opening any observed or
archived codec-projection score, confirmed that FFmpeg's raw-PCM input also
requires `-f s16le -ar 44100 -ac 2` before `-i`. Those input-demuxer arguments
are fixed for both projection encodes. This clarification does not change the
PCM boundary, encoder, formulas, support rules, thresholds, gates, or stop
decision; the synthetic score is not evaluation evidence.

Let `P(x)` be one encode/decode cycle with that configuration and a 16-bit PCM
boundary. The oracle constructs `x1 = P(x0)` and `x2 = P(x1)`; it never uses a
current MP3 bitstream or its side information.

## Canonical PCM and support

1. Decode the interval beginning at 5 seconds, up to 20 seconds long, to two
   channels at 44.1 kHz float PCM. Mono input is duplicated by the decoder;
   multichannel input uses its deterministic stereo downmix.
2. Require at least 18 seconds of decoded PCM. Reject an interval when more
   than 0.1% of decoded samples have absolute amplitude at least `0.999969`.
   Remove each channel's mean.
3. Divide the interval into non-overlapping 100 ms blocks. A block is active
   when its combined-channel RMS is at least both -60 dBFS and 40 dB below the
   maximum block RMS. Require at least half the blocks to be active and a
   median active-block RMS of at least -50 dBFS.
4. Scale once so the median active-block RMS is -20 dBFS, except cap the scale
   so the resulting peak is at most -1 dBFS. Quantize deterministically to
   signed 16-bit PCM. The first and second projections are not renormalized.
5. Use decoder gapless metadata. The three PCM sequences must differ in length
   by no more than 1,152 frames; truncate only trailing surplus to the common
   length. Cross-correlation or label-dependent alignment is prohibited.
6. Exclude the first and last 1,152 frames, then form non-overlapping one-second
   blocks. A measurement block requires signal power and both residual powers
   greater than `2^-40`. A case requires at least eight supported measurement
   blocks and at least half of its eligible one-second blocks.

Quiet, clipped, too-short, or insufficient-residual material is unsupported;
it is never treated as a successful negative. Sparse and tonal cases remain in
the hard-negative screen even when supported.

## Two fixed representations

For each supported one-second block, let `r1 = x0 - x1`, `r2 = x1 - x2`,
`e1 = mean(r1^2)`, and `e2 = mean(r2^2)` over both channels.

1. **R1 - cycle residual retention.** Block value `e2 / (e1 + e2)`. The case
   score is the median supported block value. A higher score is fixed as more
   consistent with prior MP3-128 history. The interquartile range and the
   equivalent `10*log10(e2/e1)` diagnostic are reported but are not alternate
   candidates.
2. **R2 - residual directional recurrence.** Subtract each residual's
   per-channel mean, then compute the absolute cosine similarity between `r1`
   and `r2`. The case score is the median supported block value. A higher score
   is fixed as more consistent with prior MP3-128 history. The interquartile
   range is diagnostic only.

Both scores lie in `[0, 1]`. They are two representations of one physical
codec-projection family, not independent corroboration. No union, conjunction,
learned combination, alternate aggregation, phase search, or threshold repair
is permitted after scores are viewed.

## Threshold and grouped evaluation

Each representation is evaluated separately in leave-one-source-domain-out
folds. On training domains only, its threshold is the smallest representable
float strictly above the maximum supported Tier A or hard-negative case score.
The threshold is then applied once to the omitted domain. A negative source
group alerts when any supported negative case in that group reaches the
threshold. A positive source-group score is the median of its supported scoped
MP3-128 cases.

The report includes case/group support, alerts, source-domain distributions,
thresholds, recall, and one-sided 95% Wilson bounds with `z = 1.6448536269514722`.
It reports Pearson and Spearman correlations between R1 and R2 on paired
supported cases and groups, plus domain-specific medians and failure overlap.
Neither raw score is a probability; calibration, Brier score, reliability bins,
and expected calibration error are not claimed. If a representation survives
and is later proposed as a probability, calibration requires a separate frozen
source-group-disjoint preregistration.

## Survival gates

A representation survives the observed screen only if all are true:

- zero Tier A and hard-negative case and source-group alerts in every omitted
  source-domain fold;
- pooled one-sided 95% Wilson negative-group upper bound no greater than 2.5%;
- at least 75% MP3-128 positive source-group support overall and in every
  source domain containing at least ten target groups;
- at least 90% supported MP3-128 source-group recall overall, with a one-sided
  95% lower bound of at least 85%;
- at least 85% supported recall in every omitted domain with at least ten
  supported target groups; and
- no pooled result hiding a failing source domain.

If both R1 and R2 fail a false-positive, support, recall, or domain gate, this
direction stops. Threshold changes, new residual summaries, post-hoc guards,
and a third representation are prohibited.

## Robustness stage for a survivor only

Only a representation that passes the grouped screen is run on a separately
staged, ephemeral transform set. Selection and transforms are deterministic and
remain grouped with their parent. The set covers:

- FLAC/WAV/AIFF wrappers of identical PCM;
- non-clipping gain at -3 dB and -12 dB;
- leading silence and trim offsets including non-MP3-aligned offsets;
- 10, 30, 60, and 120 second views where parent duration permits;
- 32, 44.1, and 48 kHz PCM/resample controls; and
- quiet, sparse, tonal, naturally bandwidth-limited, and sharp-low-pass
  negatives.

Container rewrites must produce identical support and score. Gain, silence,
and overlapping trim comparisons require identical assessment, 99th-percentile
absolute score delta no greater than 0.02, and maximum delta no greater than
0.05. No negative may escalate under duration or sample-rate transforms; from
30 seconds onward at least 95% of supported obvious-positive groups must agree
with the 120-second result. Unsupported output is reported explicitly.

## Oracle, evidence, and reproducibility contract

- Research-only implementation; no public Rust or CLI integration.
- Versioned raw-case, run-metadata, and path-free aggregate schemas.
- Bind repository commit, configuration, runner/analyzer/test hashes,
  manifest/fingerprint/audio hashes, encoder/decoder executable hashes,
  versions, linked LAME library, and exact commands.
- Atomic per-case checkpoints. Resume only when every stored commitment
  matches; otherwise fail closed.
- Private roots, paths, case identities, raw measurements, commands containing
  paths, and timing rows stay outside Git.
- Aggregate evidence contains no paths or case identities. Identical inputs
  must regenerate byte-identical non-timing raw and aggregate evidence. Timing
  is stored separately and excluded from the reproducibility hash.
- Mandatory CI uses deterministic synthetic/golden fixtures and does not need
  private audio. At least one golden test covers the two formulas, support
  aggregation, and canonical JSON; property tests cover bounds, gain
  normalization, order independence, resume commitment checks, and path
  redaction.

The external encoder and two additional codec cycles make this oracle
product-ineligible by construction. Runtime and peak memory are still measured
and reported. Product eligibility would separately require a deterministic
in-process implementation, no second full decode, no external encoder, no
redundant full-track transform, and p95 overhead no greater than 10%.

## Freeze, external transfer, and stop decision

If exactly one representation survives, freeze it. If both survive, choose the
one with the larger worst-domain recall margin; if tied, choose R1. The frozen
record binds implementation/configuration/support/threshold/report code and all
hashes before any new label is opened.

Fresh evaluation requires a newly sealed corpus with at least 150 independent
Tier A negative groups, difficult negatives, scoped MP3-128 positives, an
unseen content domain, and an unseen MP3 encoder implementation. It is scored
once; its labels cannot change the candidate. If suitable licensed evidence
cannot be acquired under existing authority, stop and ask the user. The
retained future SQAM subset and release holdout remain unopened throughout this
study unless separately authorized.

A rigorous rejection is successful completion. A surviving research
measurement still does not enable a verdict, advance `feature_version`, alter a
release gate, or authorize Reklawdbox integration.
