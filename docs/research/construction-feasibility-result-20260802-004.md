# Factorial benchmark v2 construction-feasibility result 004

Date: 2026-08-02

State: two header-only audits are byte-identical; all assigned cells are
constructible under the frozen source and transform constraints; no waveform
sample, benchmark audio, feature, score, or unopened label was read

## Replay result

The committed audit plan has SHA-256
`8dc633e50d530998ff6b87734375b3fd4639d3b2f54aacc71448a4d3d5901e94`.
Both complete private audits have SHA-256
`8d8b0f10fbad07b79770f5035e21e29fe30ecc63e4350e92a215630a1d8c3acf`.
Both path-free run aggregates have SHA-256
`d6a9f76b94acb12eaef07289bc8c2cbf14c9526b01cc7be13cec6f33fe2c3f86`.
The attested public result is
[`construction-feasibility-observed-20260802-004.json`](../../research/sources/evidence/construction-feasibility-observed-20260802-004.json),
with SHA-256
`13014dd9c8f26d69217865a8f62badfd0427b4a8ad808ddbe4a02ce9b4986110`.

Both replays independently reverified the bound source archives and probed all
793 exact selected source headers. The reports are byte-identical and record:

- zero groups with an unsupported native channel count;
- zero groups whose assigned trim transform is below 500 ms;
- zero groups whose assigned duration-prefix transform is below three
  seconds; and
- only FLAC or uncompressed `pcm_*` source streams.

The path-free public report contains no group, member, artifact, locator, or
private path identity. It records header and duration-stratum counts only. Its
`construction_authorized` field is a case-construction feasibility gate, not a
detector verdict or validation result.

## Disposition

The feasibility gate is passed for fractional-assignment recipe `004`. The
next permitted step is to freeze an exact, resumable, one-worker construction
recipe that binds this result, every tool and transform implementation, output
canonicalization, per-cell provenance, integrity checks, and storage limits.

No benchmark audio may be generated until that recipe and its validator are
committed. Feature computation, mechanism scoring, and external positive
encoder selection remain separately gated and unauthorized.
