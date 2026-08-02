# Audio-integrity factorial benchmark v2

Benchmark v2 is the machine-validated challenge-matrix contract for the
identifiability-first LossyTrace research program. It does not contain real
audio, a private manifest, a model, scores, or a provenance verdict.

Version 1 asked whether existing measurements or candidates cleared a release
gate. Version 2 asks an earlier question: does a proposed mechanism have a
stable within-source response to codec history after source, domain, encoder,
codec setting, decoder, and PCM-only processing are crossed explicitly?

Read these before constructing a manifest:

- [`decoded-pcm-identifiability-contract-20260802.md`](../../docs/research/decoded-pcm-identifiability-contract-20260802.md)
- [`baseline-failure-atlas-preregistration-20260802.md`](../../docs/research/baseline-failure-atlas-preregistration-20260802.md)
- [`factorial-contract.json`](factorial-contract.json)
- [`manifest.example.json`](manifest.example.json)

## Evidence partitions

`mechanism_development` is paired, source-grouped discovery evidence. It may
be consumed for effect estimation and preregistered representation design, but
never described as independent validation.

`encoder_transfer` is frozen before mechanism scores are inspected and uses
encoder lineages absent from mechanism development. Opening it consumes it for
candidate selection.

`external_transfer` is source-collection and encoder disjoint. It stays sealed
until a candidate and analysis are frozen. It is the only partition eligible
for an independent-transfer claim, and even then the decoded-PCM claim remains
conditional rather than provenance.

`synthetic_ci` contains tiny deterministic fixtures only. It tests plumbing,
not scientific performance.

The existing future SQAM and release holdouts are not v2 partitions. They stay
under the v1 commitments and may not be copied into a v2 manifest.

## Manifest principles

- One PCM master and every derivative share one `source_group`.
- Related performers, sessions, source collections, or recording chains share
  one `partition_group`.
- Every controlled-positive case names a matched PCM reference in the same
  source and evidence partition.
- Codec, encoder lineage and version, rate control, bitrate/quality, encoder
  cutoff behavior, channel mode, sample rate, decoder, and post-transform are
  explicit factors.
- Genuine hard negatives remain negative even when a baseline alerts on them.
- A lossless wrapper records current storage, not historical ground truth.
- Eligible assessment cases decode to PCM from a lossless current container.
  Current lossy originals may be retained only as diagnostic rows.
- Audio hashes, recipes, tool versions, and binary hashes bind construction.
- Private manifests and case output stay outside Git.

The matrix may use a balanced fractional-factorial design. A full Cartesian
product is unnecessary, but label, source domain, encoder, and transform may
not be confounded. Pair completeness and held-out lineage rules are mandatory.

## Validation

Validate structure while assembling a private manifest:

```bash
python3 scripts/validate-audio-integrity-factorial-manifest.py \
  --contract benchmarks/audio-integrity-v2/factorial-contract.json \
  --manifest <PRIVATE_V2_ROOT>/manifest.json \
  --profile structural
```

Before opening a partition, use its freeze profile:

```bash
python3 scripts/validate-audio-integrity-factorial-manifest.py \
  --contract benchmarks/audio-integrity-v2/factorial-contract.json \
  --manifest <PRIVATE_V2_ROOT>/manifest.json \
  --profile mechanism_development_freeze \
  --output <PRIVATE_V2_ROOT>/mechanism-development-validation.json
```

Equivalent profiles exist for `encoder_transfer_freeze` and
`external_transfer_freeze`. The aggregate validation report contains hashes
and counts but no paths, case IDs, audio hashes, or source-group identifiers.

Passing schema validation does not authorize score opening. The active
preregistration and persistent goal decide when a partition may be consumed.

## Planned construction order

1. Preserve the completed already-consumed v1 baseline failure atlas.
2. Inventory encoder/decoder implementations and licences without generating
   audio.
3. Freeze the v2 source collections, factor levels, and fractional assignment.
4. Generate paired mechanism-development cases with one low-priority worker,
   hashes, resumable recipes, and a free-space reserve.
5. Freeze encoder-transfer and external-transfer identities before mechanism
   scores are inspected.
6. Preregister no more than two mechanism representations only after the
   paired data and null analyses are fixed.

No v2 result changes `feature_version: 0` or
`public_verdict_enabled: false` without explicit approval.
