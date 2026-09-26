# Factorial benchmark v2 analysis-manifest result

Date: 2026-08-02

State: the complete private schema-2 factorial manifest is materialized and
attested by two byte-identical artifact-only replays; feature extraction,
scoring, encoder-transfer opening, external positives, and public verdicts
remain unauthorized

## Result

The corrected analysis-manifest plan has SHA-256
`cef15bfd74b3f64f0cccc5d4898e9a4808acb85f9231550e7fc13b577efbf5cc`.
Two fresh runs independently rehashed every retained artifact and produced
byte-identical private manifests with SHA-256
`0937dfec3f9d5d203ec3d8c1700a3ae947226999e72a379b226c4c825fab96f9`.
Their complete path-free run reports are also byte-identical, with SHA-256
`1951dd6bd99dc1c8bbe47b8a1b8814c84a6b7a567b3ae8235a1d023c6ae1e7f4`.

The public attestation is
[`analysis-manifest-observed-20260802-001.json`](../../research/sources/evidence/analysis-manifest-observed-20260802-001.json),
with SHA-256
`b3d293c1ffcd226f0cc4323b6c6d3f4ab1eb8a054d3e5d4f532f2e3d27d4c1d6`.

The manifest joins all 12,885 construction cells to 19 source collections,
10 encoder implementations, 46 encoder settings, 6 decoders, 10 transforms,
and 8,446 generated recipes. Both replays rehashed 13,679,285,412 artifact
bytes. No waveform was decoded for analysis and no feature or model score was
computed.

| Partition | Cases | Positives | Negatives | Source groups | State after this gate |
| --- | ---: | ---: | ---: | ---: | --- |
| mechanism development | 9,653 | 4,988 | 4,665 | 527 | metadata materialized; feature plan still required |
| encoder transfer | 2,738 | 1,368 | 1,370 | 102 | feature and score access sealed |
| external transfer | 494 | 0 | 494 | 164 | negative-only metadata; positive construction sealed |

The structural, mechanism-development-freeze, and encoder-transfer-freeze
profiles all pass. Source groups, partition groups, source collections, and
source lineages remain single-partition; encoder-transfer lineages remain
disjoint from development.

## Corrections retained as evidence

Three metadata-only stops preceded the two successful complete replays:

1. the original compositor rejected Apple AAC's legitimate multi-tool binding
   before artifact access;
2. correction 001 rehashed two artifacts before discovering that negative
   cells inherit the global canonical analysis decoder; and
3. correction 002 rehashed all artifacts before the older manifest validator
   rejected the frozen `implementation_fixed_or_default` low-pass factor.

Each stop occurred before writing a private manifest or run report and before
feature or score access. Correction 003 admits only that already-frozen factor
level and now hash-binds the validator. The complete correction records remain
in the adjacent correction documents and in the committed plan.

## Interpretation and next gate

This result establishes a reproducible analysis index and validates the frozen
development and encoder-transfer populations. It says nothing about detector
accuracy or identifiability.

The next permitted step is a separately committed mechanism-development-only
baseline and feature-extraction plan. It must freeze the exact Cannam baseline,
the paper-aligned CRNN replication boundary, explainable controls, source-group
folds, matched-reference pairing, duplicate-PCM collapse, wrapper-invariance
checks, metrics, public aggregates, and stopping rules before decoding any
waveform for analysis. Encoder-transfer features and scores remain sealed until
any successor representation and analysis are frozen; external transfer stays
sealed for a final survivor.
