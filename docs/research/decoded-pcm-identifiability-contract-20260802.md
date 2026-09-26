# Decoded-PCM identifiability and claim contract - 2026-08-02

**Status:** frozen before the successor baseline replay and mechanism scores
are opened

**Public state:** evidence schema `1`, measurement feature version `0`,
`public_verdict_enabled: false`

## Purpose

This contract separates questions that can be investigated from decoded PCM
from historical claims that decoded PCM cannot establish on its own. It is the
scientific boundary for the next LossyTrace research program. A future
implementation, benchmark result, or learned score may narrow its supported
domain; none may silently broaden the claim.

The immediate task is not to decide whether a file is "authentic" or
"lossless." It is to determine whether a named measurement has a stable,
source-independent response to a controlled prior codec history under a
declared generative model.

## Observation and histories

Let:

- `X` be the decoded finite PCM sample sequence presented for analysis;
- `M` be non-historical metadata explicitly admitted by a study, such as
  sample rate and channel count;
- `H` be the signal history before `X` was observed;
- `S` be the source-content process;
- `C` be a codec implementation and configuration;
- `T` be post-codec signal processing; and
- `D` be the source and production domain.

The primary controlled study contrasts:

- `H0`: PCM reference or a named PCM-only negative transform, with no lossy
  codec in the controlled path; and
- `H1(C, T)`: encode with `C`, decode to PCM, apply the predeclared `T`, and
  store the result in a lossless wrapper.

This is a comparison of controlled histories. It is not a claim that every
unknown real-world file belongs cleanly to `H0` or `H1`.

Container tags, filenames, extension, encoder strings, embedded pictures,
checksums from an untrusted party, and current lossy bitstream syntax are not
part of `X`. They may be useful provenance or triage evidence in a different
system, but they must not leak into a decoded-PCM experiment.

## Non-identifiability result

### Proposition

Unrestricted prior-lossy-compression history is not identifiable from decoded
PCM alone.

### Construction

Take a PCM sequence `x` produced by decoding a lossy bitstream. A lossless
container can store `x` exactly. A PCM source or deterministic renderer can
also emit the same finite sequence `x` directly without invoking that codec.
Both histories present the analyzer with exactly the same observation `X=x`.
Any deterministic or randomized function that sees only `x` therefore has the
same output distribution for both histories and cannot be correct about both
historical labels with certainty.

This is an observational-equivalence construction. It does not assert that
the two histories are equally likely in a particular music library. It shows
that a universal historical proof is impossible without assumptions or
external evidence.

### Consequences

1. A larger classifier cannot remove the boundary; it can only learn a prior
   over histories and sources represented in its data.
2. A high score may be evidence under a specified model, but it is not a
   codec-use probability unless the model, prevalence, calibration population,
   and transport conditions are declared and validated.
3. Abstention is mandatory when the source or processing path is outside the
   supported model.
4. A signal-only result cannot establish chain of custody, originality,
   mastering lineage, or authenticity.
5. Exact PCM equality is stronger evidence about the current signal than any
   inferred history: identical decoded samples must receive identical
   signal-only measurements even when external provenance records differ.

## Research targets that remain meaningful

The non-identifiability result does not make signal research useless. It
changes the estimand and the language.

### Artifact triage

Measure an observable property such as a persistent spectral edge, codec-frame
periodicity, masking-aligned coefficient censoring, or transient pre-echo
asymmetry. This can prioritize human review. It must be named as an artifact
measurement, not a history verdict.

### Conditional history assessment

Estimate how much more compatible `X` is with `H1` than `H0` inside a declared
source, codec, encoder, bitrate, decoder, and transformation universe. This is
eligible only if transfer and calibration are measured against that universe
and the output can abstain outside it.

### Paired mechanism effect

For a measurement `f`, estimate the within-source effect

`delta(s, c, t) = f(H1(s, c, t)) - f(H0(s, t0))`.

The first mechanism-discovery question is whether the direction and magnitude
of `delta` remain stable when source group, domain, encoder, codec setting,
decoder, and post-transform vary. Pooled class separation is secondary because
it can be produced by a correlation between source content and label.

### Reference-based provenance

Compare against a trusted reference, production manifest, signed hash,
delivery record, or chain-of-custody event. This can support an actual
historical claim, but it is a different evidence system and is not supplied by
the current LossyTrace signal path.

## Claim ladder

| Level | Required evidence | Allowed wording | Prohibited inference |
| --- | --- | --- | --- |
| L0 measurement | deterministic decoded-PCM calculation | "measured spectral edge at ..." or "research score ..." | codec history, authenticity, or probability |
| L1 triage | validated artifact association plus declared failure modes | "contains an artifact associated with the scoped codec process" | "was encoded with" or "fake lossless" |
| L2 scoped assessment | frozen conditional model, independent transfer, calibrated uncertainty, support and abstention | "under model V and domain U, evidence is more compatible with ..." | universal provenance or use outside U |
| L3 provenance finding | trusted reference or chain-of-custody evidence joined to signal identity | "does/does not match the documented source history" | claims beyond the supplied record |

The public LossyTrace library and CLI remain at L0. Reaching an experimental L2
research result would not authorize a product change. L3 is out of scope for a
signal-only detector.

## Support and abstention contract

A research assessment is unsupported if any predeclared condition required by
the measurement is absent. At minimum, support must account for:

- duration and amount of active audio;
- quiet, clipped, sparse, tonal, synthetic, and bandwidth-limited content;
- sample rate, channel topology, and resampling history;
- current lossy originals and unsupported decoders;
- encoder and codec settings outside the frozen scope;
- post-processing outside the tested transform set; and
- source domains outside the independent-transfer evidence.

Unsupported is not a negative result. Coverage is reported separately from
recall and specificity. A support rule may not delete difficult negative
examples merely because their measurements resemble positives.

## Study estimands and hierarchy

The next program reports, in this order:

1. **Within-source direction:** proportion of supported source pairs with the
   preregistered sign of `delta`.
2. **Effect hierarchy:** codec-history effect relative to source-group,
   source-domain, encoder, setting, decoder, transform, and interaction
   effects in a grouped hierarchical or mixed-effects analysis.
3. **Transport:** the same signed effect on encoder-held-out and
   source-collection-held-out partitions.
4. **Safety:** supported-negative case and source-group alert rates, including
   every predeclared hard-negative class.
5. **Coverage and recall:** only after support and safety are fixed.
6. **Calibration:** only for a surviving continuous assessment; never infer
   calibration from a softmax value.

Before threshold selection, a mechanism must have the expected direction in at
least 90% of supported source pairs overall, with a one-sided 95% Wilson lower
bound of at least 85%. It must also avoid a reversed or negligible effect in an
eligible source domain or encoder-held-out fold. This is a discovery gate, not
a product threshold.

## Split and leakage contract

- Every derivative of one PCM master stays in one `source_group`.
- Related artists, performers, sessions, collections, or recording chains
  stay in one `partition_group`.
- A partition group may occur in exactly one evidence partition.
- A new external-transfer partition is disjoint from all sources and source
  collections used for design, training, thresholding, and earlier candidate
  selection.
- At least one codec encoder implementation in external transfer is unseen by
  mechanism selection.
- Decoder and post-transform settings are recorded as factors rather than
  allowed to become hidden label shortcuts.
- Existing future SQAM and release evidence remain sealed. They are not
  reclassified as development data for this program.

## Falsification and stop conditions

A proposed mechanism is rejected before classifier or threshold work if any
of the following occurs:

- paired direction or its confidence bound fails the discovery gate;
- source or interaction variance dominates the codec-history effect;
- an eligible source domain has a reversed or absent effect;
- the effect disappears for an unseen encoder or setting;
- support filtering creates the effect or removes hard negatives;
- a grouped permutation analysis does not reject the predeclared null; or
- the representation is a relabelled cutoff, exact-zero, quantization,
  exact-hybrid, CNN, or projection-residual score already rejected by the
  retained evidence.

Failure is a successful scientific result when the inputs, implementation,
grouping, and analysis are reproducible. It keeps LossyTrace at L0 and prevents
another unsafe accuracy claim.

## Change control

This contract is frozen by the Git commit that first contains it. Changes
after any successor score is opened require a dated amendment that lists the
reason, affected estimand, and whether prior evidence has become consumed.
Silent edits are prohibited. Relaxing the public verdict boundary, opening a
sealed holdout, or promoting `feature_version` requires explicit approval.
