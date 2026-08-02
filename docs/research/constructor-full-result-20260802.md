# Factorial benchmark v2 full construction result

Date: 2026-08-02

State: the complete 12,885-cell frozen assignment is constructed and attested;
feature extraction, scoring, partition opening, external positives, and public
verdicts remain unauthorized

## Construction result

The committed full-authority construction plan has SHA-256
`0dd6744a7548f9ee5e22af5df66e64bf64c2c5150800a2457e14158f4e4e19f3`.
The complete sorted private manifest has SHA-256
`0fe9bde6eed57a61d3c721d5bfd8cd36031b9981442c39dc502162aeeab3a1b1`,
and the complete path-free run report has SHA-256
`83627afe77cf0ff44cb0667324f3bfa2acbf7eb93344fb9adcb5884d883c2389`.
The public attestation is
[`constructor-full-observed-20260802-001.json`](../../research/sources/evidence/constructor-full-observed-20260802-001.json),
with SHA-256
`45588d01d0bbc6afde2245034c297dc799ccc3fb66e52892b9b6f1d92c81d1fa`.

The one-worker, checkpointed run constructed all 12,885 frozen cells: 6,356
controlled positives and 6,529 matched negatives across 793 source groups.
The partition totals are:

| Partition | Cells | Retained artifact bytes |
| --- | ---: | ---: |
| mechanism development | 9,653 | 11,808,788,568 |
| encoder transfer | 2,738 | 1,326,389,004 |
| external transfer | 494 | 544,107,840 |
| **Total** | **12,885** | **13,679,285,412** |

Every retained artifact has one private checkpoint. Before checkpoint commit,
the constructor validated the assigned lossless wrapper and freshly decoded
canonical analysis PCM against the exact transformed signed-s16 input. The
finished transient work root is empty. The retained artifact hash-set digest is
`9131c6543bb02bc76cba5370b2cf586e2fb7cd49ff0d58932090ab5f7b8f98f3`;
the canonical analysis-PCM hash-set digest is
`241d92ce86c3a43687a4bf26b5e3c44f5b5a0a0065d562200913d47fbf5ce5f3`.

The preregistered full scope requires one complete run because resumability
rehashes every retained artifact and freshly decodes canonical PCM before a
checkpoint may be reused. Constructor determinism was separately demonstrated
by the earlier two complete synthetic and two complete smoke replays. This
result therefore does not claim a second 12,885-cell byte-for-byte replay.

## Execution note

The first full command invocation supplied nonexistent public-evidence paths.
The plan validator rejected it at the absent toolchain-result binding before
source or benchmark audio access and before any output or workspace creation.
The corrected invocation supplied the files whose hashes matched the committed
bindings and completed without a recipe change, retry, or exception.

## Interpretation and disposition

This result establishes a complete, reproducibly addressed corpus and exact
construction lineage. It is not evidence of detector accuracy or of
codec-history identifiability. No feature, model input, score, positive
external-transfer case, or public verdict was produced.

The next permitted step is a separately frozen feature-extraction and baseline
evaluation plan. That plan must preserve source grouping, keep encoder and
external transfer sealed until their declared gates, reproduce baselines
without tuning, and define its public path-free aggregates before any feature
is computed.
