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
- [`inventory.json`](inventory.json)
- [`source-allocation-rules.json`](source-allocation-rules.json)
- [`factor-levels.json`](factor-levels.json)
- [`factor-level-correction-20260802-001.md`](../../docs/research/factor-level-correction-20260802-001.md)
- [`toolchain-bindings.json`](toolchain-bindings.json)
- [`toolchain-probe-result-20260802.md`](../../docs/research/toolchain-probe-result-20260802.md)
- [`toolchain-freeze-preregistration-20260802.md`](../../docs/research/toolchain-freeze-preregistration-20260802.md)
- [`toolchain-factor-correction-20260802-001.md`](../../docs/research/toolchain-factor-correction-20260802-001.md)
- [`toolchain-factor-correction-20260802-002.md`](../../docs/research/toolchain-factor-correction-20260802-002.md)
- [`toolchain-factor-correction-20260802-003.md`](../../docs/research/toolchain-factor-correction-20260802-003.md)
- [`toolchain-freeze-result-20260802.md`](../../docs/research/toolchain-freeze-result-20260802.md)
- [`public-decoder-equivalence-plan.json`](public-decoder-equivalence-plan.json)
- [`public-decoder-equivalence-preregistration-20260802.md`](../../docs/research/public-decoder-equivalence-preregistration-20260802.md)
- [`public-decoder-binary-binding.json`](public-decoder-binary-binding.json)
- [`public-decoder-binary-binding-20260802.md`](../../docs/research/public-decoder-binary-binding-20260802.md)
- [`public-decoder-equivalence-result-20260802.md`](../../docs/research/public-decoder-equivalence-result-20260802.md)
- [`fractional-assignment-rules.json`](fractional-assignment-rules.json)
- [`fractional-assignment-preregistration-20260802.md`](../../docs/research/fractional-assignment-preregistration-20260802.md)
- [`fractional-assignment-correction-20260802-001.md`](../../docs/research/fractional-assignment-correction-20260802-001.md)
- [`fractional-assignment-correction-20260802-002.md`](../../docs/research/fractional-assignment-correction-20260802-002.md)
- [`fractional-assignment-correction-20260802-003.md`](../../docs/research/fractional-assignment-correction-20260802-003.md)
- [rejected recipe-001 result](../../docs/research/fractional-assignment-result-20260802.md)
- [rejected recipe-001 aggregate](../../research/sources/evidence/fractional-assignment-observed-20260802.json)
- [rejected recipe-002 result](../../docs/research/fractional-assignment-result-20260802-002.md)
- [rejected recipe-002 aggregate](../../research/sources/evidence/fractional-assignment-observed-20260802-002.json)
- [`fractional-assignment-result-20260802-003.md`](../../docs/research/fractional-assignment-result-20260802-003.md)
- [`fractional-assignment-observed-20260802-003.json`](../../research/sources/evidence/fractional-assignment-observed-20260802-003.json)
- [`construction-feasibility-plan.json`](construction-feasibility-plan.json)
- [`construction-feasibility-preregistration-20260802.md`](../../docs/research/construction-feasibility-preregistration-20260802.md)
- [`construction-feasibility-correction-20260802-001.md`](../../docs/research/construction-feasibility-correction-20260802-001.md)
- [`construction-feasibility-correction-20260802-002.md`](../../docs/research/construction-feasibility-correction-20260802-002.md)
- [`construction-feasibility-result-20260802-003.md`](../../docs/research/construction-feasibility-result-20260802-003.md)
- [`construction-feasibility-observed-20260802-003.json`](../../research/sources/evidence/construction-feasibility-observed-20260802-003.json)
- [`rwc-source-identity-audit-20260802.md`](../../docs/research/rwc-source-identity-audit-20260802.md)

The pre-freeze source/tool inventory and its remaining gates are described
in
[`factorial-benchmark-inventory-20260802.md`](../../docs/research/factorial-benchmark-inventory-20260802.md).
Every proposed new source identity is audited. The inventory itself remains a
historical pre-freeze record; the separately replayed
[`source-allocation result`](../../docs/research/source-allocation-result-20260802.md)
now freezes 793 exact private identities without generating benchmark audio.

The identity-only selection procedure was separately preregistered in
[`source-allocation-preregistration-20260802.md`](../../docs/research/source-allocation-preregistration-20260802.md).
Its two complete applications produced byte-identical private outputs. Those
outputs contain exact member identities and stay outside Git; only the
path-free aggregate is committed. The subsequent
[`factor-level freeze`](../../docs/research/factor-level-freeze-20260802.md)
fixes excerpt, codec-setting, decoder, channel, transform, wrapper, coverage,
and storage levels without assigning source groups to cells. The subsequent
[`exact-toolchain preregistration`](../../docs/research/toolchain-freeze-preregistration-20260802.md)
binds 48 expanded settings, 132 compatible history-decoder paths, transform
algorithms, and wrapper commands before executing the new settings. Its first
replay stopped when LAME CBR-96 stereo selected 32 kHz; the separately frozen
[`correction`](../../docs/research/toolchain-factor-correction-20260802-001.md)
binds 44.1 kHz explicitly without changing the scientific factor.
The next replay exposed a native-FFmpeg Vorbis capability boundary. The
separately committed
[`factor correction`](../../docs/research/factor-level-correction-20260802-001.md)
makes only those two transfer templates stereo-only and forbids a mono Vorbis
encoder-transfer claim; it does not disguise dual-mono as mono or reuse the
development lineage. Corrected
[`toolchain recipe 003`](../../docs/research/toolchain-factor-correction-20260802-002.md)
therefore contains 46 settings and 126 compatible decoder paths, frozen before
execution. Its first complete replay exposed only a transform-count
double-count; corrected
[`recipe 004`](../../docs/research/toolchain-factor-correction-20260802-003.md)
separates 36 ordinary transform paths from 12 wrapper paths without changing
an algorithm. Its two fresh complete replays are byte-identical; see the
[`exact-toolchain result`](../../docs/research/toolchain-freeze-result-20260802.md).
All 46 settings and 126 decoder paths are deterministic within path. Fresh
public-decoder wrapper equivalence is separately
[`preregistered`](../../docs/research/public-decoder-equivalence-preregistration-20260802.md)
and its public binary was separately
[`hash-bound`](../../docs/research/public-decoder-binary-binding-20260802.md).
The two required replays are byte-identical, and all 12 paths have exact public
wrapper projections; see the
[`public-decoder result`](../../docs/research/public-decoder-equivalence-result-20260802.md).
This completes toolchain binding, not detector validation.
The first source-blind
[`fractional-assignment result`](../../docs/research/fractional-assignment-result-20260802.md)
was byte-identical, but construction review found that target sample rate was
missing from its matched-reference identity. The separately frozen
[`correction`](../../docs/research/fractional-assignment-correction-20260802-001.md)
adds that factor before any assigned audio or score is opened. Recipe `001`
must not enter a benchmark denominator. Corrected
[`recipe-002 evidence`](../../docs/research/fractional-assignment-result-20260802-002.md)
is byte-identical across two fresh replays and fixes target sample rate, but a
second construction audit found that generated cells did not explicitly name
their identity recipe source. The separately frozen
[`lineage correction`](../../docs/research/fractional-assignment-correction-20260802-002.md)
adds that relation before audio or scores; recipe `003` requires two fresh
replays. Those
[`recipe-003 replays`](../../docs/research/fractional-assignment-result-20260802-003.md)
are byte-identical and freeze 12,884 sample-rate-aware, lineage-complete cells.
The next separately preregistered gate is a two-replay, header-only
[`construction-feasibility audit`](../../docs/research/construction-feasibility-preregistration-20260802.md).
It may expose duration and channel support but cannot inspect waveform samples,
reassign a group, or open a score.
Recipe `001` stopped before source inspection because its plan omitted the
FFprobe tool ID; the separately frozen correction adds that binding without
changing the audit design.
Recipe `002` then stopped on uncompressed floating-point PCM because its
lossless whitelist was too narrow. The second correction accepts `flac` or
`pcm_*` without admitting compressed lossy codecs; recipe `003` still requires
two complete replays. Those replays are byte-identical, but the
[`result`](../../docs/research/construction-feasibility-result-20260802-003.md)
finds 11 assigned groups below a frozen transform minimum. Construction stays
stopped. Fractional-assignment recipe `004` is now frozen to apply those
minimums only as per-transform eligibility predicates before the unchanged
recipe-`003` ranking; it must pass two complete replays before construction.

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

Validate the public path-free source/tool inventory independently:

```bash
python3 scripts/validate-audio-integrity-v2-inventory.py \
  --inventory benchmarks/audio-integrity-v2/inventory.json
```

Validate the separately frozen factor levels and their source-allocation
binding:

```bash
python3 scripts/validate-audio-integrity-v2-factor-levels.py \
  --factors benchmarks/audio-integrity-v2/factor-levels.json
```

Validate the exact path-free toolchain recipe independently:

```bash
python3 scripts/freeze-audio-integrity-v2-toolchains.py validate \
  --factor benchmarks/audio-integrity-v2/factor-levels.json \
  --manifest benchmarks/audio-integrity-v2/toolchain-bindings.json
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
2. Preserve the completed encoder/decoder/source inventory without treating it
   as a freeze.
3. Preserve the completed source-identity audits, external-transfer margin,
   replayed source allocation, factor-level freeze, and exact-toolchain
   preregistration, replayed toolchain, and public-decoder equivalence, then
   preserve rejected recipes `001` and `002` plus the separately replayed
   recipe `003` before construction.
4. Generate paired mechanism-development cases with one low-priority worker,
   hashes, resumable recipes, and a free-space reserve.
5. Freeze encoder-transfer and external-transfer identities before mechanism
   scores are inspected.
6. Preregister no more than two mechanism representations only after the
   paired data and null analyses are fixed.

No v2 result changes `feature_version: 0` or
`public_verdict_enabled: false` without explicit approval.
