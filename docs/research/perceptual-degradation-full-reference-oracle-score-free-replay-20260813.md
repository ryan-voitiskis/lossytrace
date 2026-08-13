# Full-reference oracle score-free replay - 2026-08-13

**State:** preregistered score-free schema replay complete; both perceptual
metric families and all human truth remain closed

## Outcome

LossyTrace now has a deterministic, path-free full-reference oracle envelope
before any real-audio metric execution or human-score access. This closes the
`score_free_schema_replay` prerequisite named in the frozen research plan. It
does not claim that the oracle can estimate perceptual degradation yet.

Two exact synthetic structural records were replayed byte-for-byte:

1. A supported stereo alignment becomes `execution_blocked`. Both metric
   families are `not_authorized`, human calibration is `unavailable`, and the
   record abstains.
2. An unsupported channel topology becomes `unsupported_alignment`. Both
   metric families are `not_run_alignment_unsupported`, preserving the
   distinction between an alignment failure and a metric execution boundary.

The two-record inventory SHA-256 is
`9777677b10ef6f0024855796f4e940e24149b04ad05ef8d95cb56e3a85414636`.
The complete canonical replay file SHA-256 is
`1bb110a6683b0c078245097de65f4243646f60f9e46d942cd8a3a96610b43560`.

## Output surface

The score-free envelope reserves explicit fields for:

- impairment severity and its interval;
- audibility probability and its interval;
- masking-relative error, bandwidth loss, temporal-modulation damage,
  transient smearing or pre-echo, tonal or birdie-like noise, stereo-image or
  phase change, and segment worst-case impairment;
- support and abstention reasons; and
- uncertainty and source-group bootstrap counts.

Every estimated value is structurally required to remain `null`; the
categorical state is `indeterminate`, support is false, uncertainty is
`unquantified`, and the bootstrap count is zero. A score-free record cannot be
mistaken for a transparent or degraded assessment.

## Determinism and privacy

The replay is assembled from fixed numeric alignment records rather than audio
or platform-dependent trigonometric calculations. Two fresh executions were
byte-identical. The committed evidence contains opaque recipe-derived case
IDs, no source paths, no audio hashes, no filenames, and no corpus membership.

The validator fails closed if a record:

- enables a public verdict;
- claims metric execution, human-score access, or retained/provider access;
- inserts a metric value or calibrated estimate;
- hides an alignment reason;
- claims support or quantified uncertainty; or
- includes a private path.

## Boundary and next gate

No ODAQ reference, processed condition, listening score, public or provider
audio, retained waveform, human response, metric output, or sealed evidence
was read. Neither ViSQOL nor the GstPEAQ proxy was executed. No no-reference
training occurred, and the Rust library and public CLI were unchanged.

This is infrastructure evidence only. The actual oracle remains gated on
separately authorized clean-reference delivery, valid listening evidence,
metric authority, human calibration, and grouped transfer. The GstPEAQ proxy
legal/conformance boundary also remains unresolved. A later scored oracle must
use a successor schema and mapping frozen before the relevant scores are
opened; it may not mutate this score-free evidence into an estimate.
