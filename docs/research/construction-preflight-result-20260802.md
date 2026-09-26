# Factorial benchmark v2 construction-preflight result

Date: 2026-08-02

State: two metadata-only preflights are byte-identical; all private lineage and
external-volume capacity checks pass; no benchmark waveform, codec output,
feature, score, or unopened label was read

## Replay result

The committed plan has SHA-256
`a45ab064897e677d82818ff4ce4547c24aebc4ae4739e145de2b07166416c3c7`.
Both complete path-free run reports have SHA-256
`52e71265bea5c11701f4eb52578991b36bcb362e35f044908117d073613b10f1`.
The attested result is
[`construction-preflight-observed-20260802-001.json`](../../research/sources/evidence/construction-preflight-observed-20260802-001.json),
with SHA-256
`53ad83236cf9975ac5394a429a4a2da3a479c9266380b55a606da506ce8e22d6`.

Both replays validate 793 groups and 12,885 exact cell recipes: 6,356
controlled positives and 6,529 negative or reference cells. Every positive
resolves to an exact matched H0; every generated H0/H1 resolves to its identity
PCM source; every factor is bound; no external positive has been instantiated;
and the 100 reserved external groups still have no encoder, setting, decoder,
feature, score, or label.

## Storage ceiling

The conservative retained upper bound is 31,917,486,459 bytes, about 29.7 GiB:

| Partition | Retained upper bound |
| --- | ---: |
| mechanism development | 26,030,512,868 bytes |
| encoder transfer | 4,676,750,930 bytes |
| external transfer | 1,210,222,661 bytes |

By wrapper, the bound covers 4,331 AIFF cells, 4,256 FLAC cells, and 4,298 WAV
cells. The largest single-artifact ceiling is 3,707,162 bytes.

After adding 2 GiB of one-worker workspace and the 15 GiB reserve, the selected
external volume must provide at least 50,171,097,467 bytes, about 46.7 GiB.
The intended `/Volumes/gelb` root passed this gate. Exact ambient free bytes are
intentionally absent from replay evidence.

## Disposition

The exact constructor may now be implemented and frozen against this result.
It must realize the preregistered recipe-addressed layout, atomic artifact and
sidecar commits, hash-revalidating resume behavior, one-cell codec
intermediates, wrapper and canonical PCM validation, and private-manifest/
path-free-public-evidence split.

This preflight does not itself authorize audio generation. The constructor,
its synthetic and bounded recipe smoke checks, and a construction authorization
must be committed before any benchmark waveform is decoded.
