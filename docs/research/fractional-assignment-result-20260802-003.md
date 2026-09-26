# Factorial benchmark v2 fractional-assignment result 003

Date: 2026-08-02

State: sample-rate-aware, lineage-complete assignment replayed byte-identically;
path-free aggregate frozen; no benchmark audio, waveform statistic, feature,
score, or unopened label was inspected

## Bound inputs

Recipe `003` was executed only after correction commit `34aaf32` had been
pushed. Both complete runs used:

- rules SHA-256
  `372049ed3567443f171d60a7c93a1e547a7eb4e732ac9dfaebf9a33a78229f37`;
- generator SHA-256
  `07242c92df17207ccad8e2f7cdf57f01fd4819b9a0d56e7ca2e2c0341a76782e`;
- private source-allocation SHA-256
  `e4b7d2ab42253e00ce0e0b95c8049193f9b6178ecbb6212811fde96d58c088d4`;
  and
- the previously frozen factor, toolchain, and public-decoder evidence bound
  by the rules.

Only group identity, partition, source collection, source domain, and
provenance tier influenced assignment. Private source and cell mappings remain
outside Git.

## Replay result

Both private assignments have SHA-256
`e33ae9f961fd48ec3857ac41ad9197b86fd0d38a5897dd5144bbf35683110582`.
Both path-free run aggregates have SHA-256
`ec05acba7817bc1e2bb3e16cfe4c22f217f59cc4b499554db787658fc122ab03`.
The attested public aggregate is
[`fractional-assignment-observed-20260802-003.json`](../../research/sources/evidence/fractional-assignment-observed-20260802-003.json),
with SHA-256
`31573d8ee523d6572d89b884ca5cbb1d815596c37d47831a31cb51d130bebe90`.

The frozen assignment contains 793 source groups and 12,884 cells:

- 6,356 controlled positives;
- 6,528 identity references or hard negatives;
- zero unmatched positives;
- exact H0/H1 matching on group, partition, channel treatment, target sample
  rate, PCM transform, and wrapper;
- an explicit identity PCM recipe source for every generated H0 and H1;
- the same identity source on every positive and its matched negative;
- all source-domain, setting, channel, decoder, transform, wrapper, and sample
  rate coverage requirements; and
- a sealed 100-group external MP3 reserve with encoder, setting, decoder,
  feature, and score unset.

The 826-cell increase over recipe `002` is the expected materialization of
identity source combinations that had previously been implicit. The external
hard-negative assignments remain exactly 10/10 over 44.1 and 48 kHz for each
nonidentity transform.

## Interpretation and authorization boundary

Recipe `003` is deterministic, sample-rate-aware, lineage-complete, and
constructible without inferring relationships after the freeze. The earlier
recipes remain useful rejected audit evidence but must not enter a benchmark
denominator.

One-worker, resumable case construction is now authorized on storage that
preserves the frozen 15 GiB reserve. Mechanism scoring, representation
selection, encoder-transfer opening, and external positive materialization
remain unauthorized until their later gates.
