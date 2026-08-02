# Audio-integrity benchmark v1

This is the opt-in, private-corpus gate for the experimental compression-trace
measurements. The repository contains the harness and non-sensitive contract,
but no source audio. The checked-in baseline and fingerprints explicitly record
that the private release gate has not run. `development-report.json` records a
redacted Tier B, 90-second-window pilot that failed the initial development
gate. `development-research-report.json` records the later explainable,
learned-probe, and unseen-codec-setting experiments. Neither report is evidence
that a classifier is safe.

The prototype feature version is `0`. It measures spectral support, edges,
holes, band ruptures, and opt-in transform-alignment research probes. It does
not classify a file, change the Stratum cache schema, or enable a Library
Health warning.

## Retained observed baseline

The retained corpus may be relocated without rewriting its historical seals.
The verifier accepts an old `exact_cleanup_target` only when a schema-1
same-filesystem relocation record maps the same relative path and the retained
inventory hash in that record still verifies. An unrecorded path change fails
closed.

Verify the retained inventory and create a private, already-observed baseline
without opening either holdout:

```bash
python3 scripts/verify-audio-integrity-retained-inventory.py \
  --inventory <CORPUS_ROOT>/retained-corpora-inventory-20260731-005.json \
  --relocation <CORPUS_ROOT>/relocation-20260801.json \
  --output <PRIVATE_RUN_ROOT>/inventory-verification.json

python3 scripts/compose-audio-integrity-baseline-manifest.py \
  --corpus-root <CORPUS_ROOT> \
  --output <PRIVATE_RUN_ROOT>/manifest.json

python3 scripts/shard-audio-integrity-manifest.py \
  --manifest <PRIVATE_RUN_ROOT>/manifest.json \
  --output-directory <PRIVATE_RUN_ROOT>/shards \
  --shard-count 32

cargo build --release --example audio_integrity_benchmark
caffeinate -is nice -n 15 \
  python3 scripts/run-audio-integrity-shards.py \
  --shard-directory <PRIVATE_RUN_ROOT>/shards \
  --report-directory <PRIVATE_RUN_ROOT>/shard-reports \
  --audio-root <CORPUS_ROOT> \
  --jobs 1

python3 scripts/combine-audio-integrity-measurement-shards.py \
  --manifest <PRIVATE_RUN_ROOT>/manifest.json \
  --shard-directory <PRIVATE_RUN_ROOT>/shards \
  --report-directory <PRIVATE_RUN_ROOT>/shard-reports \
  --output <PRIVATE_RUN_ROOT>/raw-report.json

python3 scripts/analyze-audio-integrity-measurement-baseline.py \
  --manifest <PRIVATE_RUN_ROOT>/manifest.json \
  --report <PRIVATE_RUN_ROOT>/raw-report.json \
  --output <PRIVATE_RUN_ROOT>/aggregate-report.json
```

Source groups are assigned by a stable SHA-256 rule, so each group remains in
one shard and a long run can resume only from complete, validated reports. The
shard driver explicitly disables the benchmark example's legacy full transform
grid; that archived research probe is not part of the current feature and
would distort throughput without changing `compression_trace`. The
composer includes 5,280 cases whose labels or feature scores were previously
observed. It excludes the 280-case codec-only SQAM transfer subset and the
sealed release holdout. The schema-2 aggregate contains no paths or case-level
rows and explicitly states that classification and calibration metrics do not
exist for the verdict-free feature-version-0 baseline.

## Frozen external-detector failure atlas

The exact Cannam published-weight CNN is replayed as a fixed baseline, not
tuned or promoted. Its method and metrics are frozen in
[`baseline-failure-atlas-preregistration-20260802.md`](../../docs/research/baseline-failure-atlas-preregistration-20260802.md).
Build revision `7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b` outside the repository,
bind the plugin and host binaries by hash, and run the complete already-consumed
manifest with one low-priority worker:

```bash
caffeinate -is nice -n 15 \
  python3 scripts/evaluate-vamp-lossy-detector.py \
  --manifest <PRIVATE_BASELINE_ROOT>/manifest.json \
  --expected-manifest-sha256 e19b5b408fedf348fa9b6499d5cdd1b6b734d84b19b895d5b0a528f0c4423b7a \
  --audio-root <CORPUS_ROOT> \
  --host <VAMP_SIMPLE_HOST> \
  --vamp-path <EXACT_CANNAM_BUILD_DIRECTORY> \
  --repository <EXACT_CANNAM_CHECKOUT> \
  --plugin-sdk-repository <PINNED_VAMP_SDK_CHECKOUT> \
  --plugin-binary <EXACT_CANNAM_PLUGIN_BINARY> \
  --partial-directory <PRIVATE_CANNAM_RUN_ROOT>/partials \
  --jobs 1 \
  --output <PRIVATE_CANNAM_RUN_ROOT>/raw-report.json

python3 scripts/analyze-vamp-lossy-detector.py \
  --manifest <PRIVATE_BASELINE_ROOT>/manifest.json \
  --report <PRIVATE_CANNAM_RUN_ROOT>/raw-report.json \
  --preregistration docs/research/baseline-failure-atlas-preregistration-20260802.md \
  --output <PRIVATE_CANNAM_RUN_ROOT>/aggregate-report.json
```

Partials are bound to the manifest, audio, revision, plugin, host, and fixed
0.5-window/25%-file rule. Case IDs are hashed in partial filenames and are not
printed to progress logs. The aggregate is path-free and reports both the
general 5,280-case population and the task-matched 2,261-case MP3-128 view.
Neither is independent validation.

## Preregistered exact-hybrid ablation

The only retained detector direction is the exact MP3 hybrid-transform
measurement described in
`docs/research/exact-hybrid-ablation-preregistration-20260801.md`. Build its
isolated research crate and run it only after the raw observed baseline is
complete:

```bash
cargo test --manifest-path \
  research/exact-transform/ablation-v1/Cargo.toml
cargo build --release --manifest-path \
  research/exact-transform/ablation-v1/Cargo.toml

caffeinate -is nice -n 15 \
  python3 scripts/run-audio-integrity-exact-hybrid-ablation.py \
  --manifest <PRIVATE_RUN_ROOT>/manifest.json \
  --baseline-report <PRIVATE_RUN_ROOT>/raw-report.json \
  --corpus-root <CORPUS_ROOT> \
  --runner research/exact-transform/ablation-v1/target/release/lossytrace-exact-hybrid-ablation \
  --output <PRIVATE_RUN_ROOT>/exact-hybrid-raw.json \
  --jobs 1

python3 scripts/verify-audio-integrity-exact-hybrid-replay.py \
  --archive <CORPUS_ROOT>/private/audio-integrity-exact-transform-research-20260731-001.tar.zst \
  --ablation-report <PRIVATE_RUN_ROOT>/exact-hybrid-raw.json \
  --output <PRIVATE_RUN_ROOT>/exact-hybrid-replay.json

python3 scripts/analyze-audio-integrity-exact-hybrid-ablation.py \
  --manifest <PRIVATE_RUN_ROOT>/manifest.json \
  --baseline-report <PRIVATE_RUN_ROOT>/raw-report.json \
  --ablation-report <PRIVATE_RUN_ROOT>/exact-hybrid-raw.json \
  --replay-report <PRIVATE_RUN_ROOT>/exact-hybrid-replay.json \
  --output <PRIVATE_RUN_ROOT>/exact-hybrid-evaluation.json
```

The runner selects all observed negatives and only the scoped MP3-128
controlled positives. It checkpoints each case, binds audio to the earlier
baseline hash, and keeps paths and case-level features outside Git. The replay
verifier reads the archived v32 evidence directly from its checksum-bound
Zstandard archive. The final evaluator emits a path-free leave-one-source-
domain-out report; it does not open either holdout or create a probability.

## Lossy-original/container equivalence

Lossy originals and their decoded lossless wrappers are staged ephemerally so
decoder/container behavior is measured rather than assumed:

```bash
python3 scripts/stage-audio-integrity-container-equivalence.py stage \
  --manifest <PRIVATE_RUN_ROOT>/manifest.json \
  --corpus-root <CORPUS_ROOT> \
  --destination <PRIVATE_EQUIVALENCE_ROOT> \
  --groups-per-domain 2

python3 scripts/stage-audio-integrity-container-equivalence.py verify \
  --root <PRIVATE_EQUIVALENCE_ROOT>

LOSSYTRACE_RESEARCH_SKIP_TRANSFORM_GRID=1 \
  python3 scripts/benchmark-audio-integrity.py \
  --manifest <PRIVATE_EQUIVALENCE_ROOT>/manifest.json run \
  --audio-root <PRIVATE_EQUIVALENCE_ROOT> \
  --fingerprints <PRIVATE_EQUIVALENCE_ROOT>/fingerprints.json \
  --binary target/release/examples/audio_integrity_benchmark \
  --no-build \
  --jobs 1 \
  --output <PRIVATE_EQUIVALENCE_ROOT>/raw-report.json

python3 scripts/analyze-audio-integrity-container-equivalence.py \
  --manifest <PRIVATE_EQUIVALENCE_ROOT>/manifest.json \
  --report <PRIVATE_EQUIVALENCE_ROOT>/raw-report.json \
  --output <PRIVATE_EQUIVALENCE_ROOT>/aggregate-report.json
```

The deterministic selection takes two eligible PCM source groups per observed
content domain and creates MP3, AAC, Opus, and explicitly named native-FFmpeg
Vorbis intermediates plus FLAC, WAV, and AIFF wrappers. MP3, AAC, and Vorbis
originals are also analyzed. The current Symphonia decoder has no Opus codec,
so the Opus intermediate is checksum-committed and removed after wrapper
generation; its wrappers are compared with one another and the limitation is
explicit in the manifest. The current selection yields 210 analysis cases
from 14 source groups. Generated audio, commands, fingerprints, and private
source commitments remain outside Git and are removed after the path-free
aggregate has been verified.

## Corpus setup

Copy `manifest.example.json` to the ignored `manifest.json`, replace the example
rows with the private corpus, and set:

```bash
export LOSSYTRACE_RESEARCH_ROOT=/private/audio-integrity-v1
python3 scripts/benchmark-audio-integrity.py validate
```

Paths are resolved beneath the audio root. Results use opaque case and source
group IDs; do not put artist, title, release, or other unnecessary identifying
metadata in the manifest.

Every encode or transform of one master must use the same `source_group`.
Use `partition_group` for a broader correlated identity such as performer,
artist, recording session, or source collection. Manifest validation rejects
either group when it crosses from `development` to `held_out`, preventing both
source-master leakage and a superficially disjoint split made from the same
performer/session. A release held-out manifest requires opaque
`partition_group` values; older development-only manifests may omit them and
are conservatively treated as one partition per source group.

Use only documented uncompressed paths as Tier A negative ground truth. Trusted
commercial lossless releases belong in Tier B robustness checks, and unknown
commercial files belong in Tier C blind case studies.

### Approved public Tier A packages

`public-tier-a-sources.json` records the reviewed provider metadata, CC BY 4.0
licence, provider checksum, provenance rationale, partition basis, and
limitations for four expressly recorded or captured WAV datasets. These
packages add guitar, singing, electronic drums, and wind/brass hard negatives;
they do not replace full-mix diversity, and their small number of
performer/session clusters makes them development expansion rather than the
150-partition release set. Preserve attribution and the registry hash with
every derived corpus.

Fetch packages into a private, durable location with a free-space reserve. The
fetcher supports resume through a provider `.partial` file, verifies the
provider checksum and byte count before publishing the final archive, computes
SHA-256, and writes a private immutable fetch record:

```bash
python3 scripts/fetch-audio-integrity-public-sources.py \
  --destination "/private/audio-integrity-public-sources/20260730-001" \
  --fetch-id audio-integrity-public-tier-a-20260730-001 \
  --record "/private/audio-integrity-public-sources/20260730-001/fetch-record.json"
```

Stage a compact negative corpus without expanding the source archives. The
stager re-verifies every archive SHA-256, deterministically selects one released
PCM master per approved performer/instrument partition, streams only those ZIP
members, confirms their codec with FFprobe, and seals the result plus exact
archive-member CRC, attribution, manifest, fingerprints, and cleanup target:

```bash
python3 scripts/stage-audio-integrity-public-negatives.py stage \
  --fetch-record "/private/audio-integrity-public-sources/20260730-001/fetch-record.json" \
  --destination "/private/audio-integrity-public-negatives/20260730-001" \
  --run-id audio-integrity-public-negatives-20260730-001 \
  --corpus-id audio-integrity-public-tier-a-development-negatives-20260730-001

python3 scripts/stage-audio-integrity-public-negatives.py verify \
  --root "/private/audio-integrity-public-negatives/20260730-001"
```

The current selector yields 48 development partitions: 6 GuitarSet players,
20 VocalSet singers, 9 Groove drummers with released audio, and 13
ChoraleBricks instrument/performer codes. This is useful source-group-disjoint
development evidence, but it is deliberately short of the 150-partition blind
release minimum.

Create a compact controlled-positive companion from those sealed PCM masters:

```bash
python3 scripts/stage-audio-integrity-public-transcodes.py stage \
  --parent-root "/private/audio-integrity-public-negatives/20260730-001" \
  --destination "/private/audio-integrity-public-transcodes/20260730-001" \
  --run-id audio-integrity-public-controlled-transcodes-20260730-001 \
  --corpus-id audio-integrity-public-tier-a-controlled-transcodes-20260730-001 \
  --jobs 4

python3 scripts/stage-audio-integrity-public-transcodes.py verify \
  --root "/private/audio-integrity-public-transcodes/20260730-001"
```

For every source partition, the command makes one centred, at-most-90-second
stereo PCM/FLAC reference, one PCM-only 48 kHz resample control, and MP3 128,
AAC-LC 128, Opus 96, and Vorbis quality-3 lossy intermediates decoded back to
16-bit FLAC. It records the intermediate hashes, byte counts, encoder
arguments, and FFmpeg build, then removes only those reproducible
intermediates. The final 288-case corpus, staging scripts, parent seals, and
provenance snapshots are integrity-sealed for reuse. The native experimental
FFmpeg Vorbis encoder is named explicitly in the class; do not conflate it with
`libvorbis`.

### Public Tier B sparse hard negatives

`public-hard-negative-sources.json` records the official NSynth test and
validation archives, provider MD5 values and byte counts, local SHA-256
requirements, CC BY 4.0 attribution, and the limits on their use. NSynth is a
collection of short, monophonic 16 kHz instrument notes from commercial sample
libraries. It is useful for sparse and genuinely bandwidth-limited robustness
checks, but it is not documented original PCM provenance and therefore cannot
count toward the Tier A release minimum.

Fetch both archives into durable private storage:

```bash
python3 scripts/fetch-audio-integrity-public-sources.py \
  --registry benchmarks/audio-integrity-v1/public-hard-negative-sources.json \
  --destination "/private/audio-integrity-nsynth-sources/20260731-001" \
  --fetch-id audio-integrity-nsynth-sources-20260731-001 \
  --record "/private/audio-integrity-nsynth-sources/20260731-001/fetch-record-v2.json"
```

The current corpus deliberately derives only from the test split. The official
dataset makes test and validation independently disjoint from training, but
their 53 numeric instrument IDs overlap each other, so treating both as
independent partitions would leak instrument identity. The validation archive
is retained unchanged for future research rather than used to inflate the
current corpus.

Stage and verify the deterministic test-split corpus:

```bash
python3 scripts/stage-audio-integrity-nsynth-hard-negatives.py stage \
  --registry benchmarks/audio-integrity-v1/public-hard-negative-sources.json \
  --fetch-record "/private/audio-integrity-nsynth-sources/20260731-001/fetch-record-v2.json" \
  --destination "/private/audio-integrity-nsynth-corpus/20260731-001" \
  --pointer .tmp/audio-integrity/nsynth-hard-negatives-active.json \
  --run-id audio-integrity-nsynth-hard-negatives-20260731-001 \
  --corpus-id audio-integrity-nsynth-hard-negatives-20260731-001 \
  --jobs 4

python3 scripts/stage-audio-integrity-nsynth-hard-negatives.py verify \
  --root "/private/audio-integrity-nsynth-corpus/20260731-001"
```

For each of 53 instruments, the stager selects eight evenly rank-spaced notes
and creates a 30-second montage. It preserves the 16 kHz PCM montage and a
48 kHz stereo PCM-only resample as negatives, then creates MP3 128, AAC-LC 128,
Opus 96, and native-FFmpeg-Vorbis quality-3 intermediates decoded back to
FLAC. The retained corpus has 318 cases: 106 negatives and 212 controlled
positives. Manifests, selected note/member hashes, commands, encoder build,
intermediate hashes, source commitments, fingerprints, and the integrity seal
remain reusable; only the reproducible lossy intermediates are removed.

Frozen policies can be applied without threshold fitting, and a grouped OOF
CNN/rule union can be reproduced explicitly:

```bash
python3 scripts/evaluate-audio-integrity-frozen-rules.py \
  --candidate /private/research/nsynth-stable-profile.json \
  --frozen-policy-report /private/research/prior-stable-rules.json \
  --output /private/research/nsynth-frozen-rule-evaluation.json

python3 scripts/analyze-audio-integrity-cnn-rule-ensemble.py \
  --candidate /private/research/nsynth-full-grid.json \
  --stable-rule-report /private/research/nsynth-stable-rule-set.json \
  --cnn-report /private/research/nsynth-cnn-seed-a.json \
  --cnn-report /private/research/nsynth-cnn-seed-b.json \
  --cnn-report /private/research/nsynth-cnn-seed-c.json \
  --output /private/research/nsynth-cnn-rule-ensemble.json
```

The ensemble report marks its size, boundary, and stable-rule choice as
development-observed. It is a candidate generator, never release evidence.
Keep instrument groups intact in every outer and early-stop fold.

The 2026-07-31 run is preserved as
`audio-integrity-nsynth-research-20260731-001.tar.zst` (SHA-256
`e0957543f8ea79e2b7313202151162974ead3dba8031fc058766edb7c6b1a0a2`).
Its three-seed CNN plus stable-rule union reached 193/212 with zero in-domain
development false positives, but the unchanged CNN collapsed to AUC 0.746 on
the earlier 936-case development corpus and detected only 42/512 at the fixed
NSynth boundary while producing two PCM alerts. This is a documented
generalization failure, not a candidate to promote.

### Broad sparse-domain training and frozen transfer

`public-sparse-training-sources.json` registers the official NSynth train
JSON/WAV archive separately from the test/validation robustness material.
Fetch and retain it with the generic resumable fetcher:

```bash
python3 scripts/fetch-audio-integrity-public-sources.py \
  --registry benchmarks/audio-integrity-v1/public-sparse-training-sources.json \
  --source nsynth-train-jsonwav-2017 \
  --destination "/private/audio-integrity-nsynth-train-sources/20260731-001" \
  --fetch-id audio-integrity-public-sparse-training-fetch-20260731-001 \
  --record "/private/audio-integrity-nsynth-train-sources/20260731-001/fetch-record.json"
```

The fetcher resumes a provider partial, retries transport failures, enforces a
15 GiB free-space reserve, and publishes only after exact size and provider
checksum verification. The retained archive is 23,815,298,079 bytes, provider
MD5 `fde6665a93865503ba598b9fac388660`, local SHA-256
`15c5100fc40c3a262f9b42707c15ffed30b8fec58c0d9b88d4136f6cb1fddefe`,
and CC BY 4.0. It is Tier B training material, never release evidence.

Stage and verify the deterministic 200-instrument subset:

```bash
python3 scripts/stage-audio-integrity-nsynth-sparse-training.py stage \
  --fetch-record "/private/audio-integrity-nsynth-train-sources/20260731-001/fetch-record.json" \
  --destination "/private/audio-integrity-nsynth-train-corpus/20260731-001" \
  --pointer .tmp/audio-integrity/nsynth-train-sparse-active.json \
  --run-id audio-integrity-nsynth-sparse-training-20260731-001 \
  --corpus-id audio-integrity-nsynth-sparse-training-20260731-001 \
  --maximum-instruments 200 \
  --jobs 4

python3 scripts/stage-audio-integrity-nsynth-sparse-training.py verify \
  --root "/private/audio-integrity-nsynth-train-corpus/20260731-001"
```

The retained result has 1,200 thirty-second cases in 200 train-only
instrument groups: 400 PCM negatives and 800 controlled lossy-to-FLAC
positives. The source/family-stratified selection, 1,600 exact note members,
commands, encoder build, intermediate hashes, manifests, fingerprints,
integrity file, seal, and explicit `retain_for_future_versions` policy are
preserved. Reproducible lossy intermediates are removed.

`stage-audio-integrity-private-compact-training.py` can independently stream
the verified 40-source private development archive into a retained 520-case,
1.9 GB training corpus without restoring its roughly 45 GB source tree:

```bash
python3 scripts/stage-audio-integrity-private-compact-training.py stage \
  --record "/private/audio-integrity-dev-20260730-001.archive.json" \
  --destination "/private/audio-integrity-private-compact/20260731-001" \
  --pointer .tmp/audio-integrity/private-compact-training-active.json \
  --run-id audio-integrity-private-compact-training-20260731-001 \
  --corpus-id audio-integrity-private-compact-training-20260731-001

python3 scripts/stage-audio-integrity-private-compact-training.py verify \
  --root "/private/audio-integrity-private-compact/20260731-001"
```

The one refrozen broad-transfer CRNN trained on all 1,720 cases/240 groups
from those two corpora. Its selected inner-validation checkpoint detected
5/224 positives at 0/120 PCM alerts. On the unchanged 654-case transfer set it
detected 20/404 positives and alerted on 11/250 PCM negatives. All alerts were
in Groove: four of five alerted drummer groups also alerted PCM, and three
alerted all seven variants. Its final disposition is
`failed_source_group_specificity_check`; do not tune it against those observed
transfer labels.

The durable inventory
`retained-corpora-inventory-20260731-001.json` has SHA-256
`3c70907f2d554dcc311aeccb8bfb4c1bee7be3f05c9a092938148a7d8aadc59f`.
It accounts for 2,374 retained cases and explicitly excludes every corpus,
both source archives, active pointers, prior research archives, and the sealed
release data from cleanup.

### Source-domain holdout evaluation

`development-source-domains.json` maps the retained 1,254-case development set
to six macro domains without changing any case label or release split. The
fail-closed cache merger can reconstruct the 6,270-clip cache directly from
the two verified research archives:

```bash
python3 scripts/merge-audio-integrity-cnn-feature-caches.py \
  --manifest /private/research/prior/manifest-main.json \
  --manifest /private/research/prior/manifest-controls.json \
  --manifest /private/research/prior/public-negative-manifest.json \
  --manifest /private/research/prior/public-transcodes-manifest.json \
  --manifest /private/research/nsynth/manifest.json \
  --source-cache /private/research/prior/features.pt \
  --source-archive-record /private/research/prior.archive.json \
  --source-archive-member rule-search-20260730-001/cnn-expanded-v1/features.pt \
  --source-cache /private/research/nsynth/features.pt \
  --source-archive-record /private/research/nsynth.archive.json \
  --source-archive-member cnn-features.pt \
  --allow-legacy-source-cache /private/research/prior/features.pt \
  --domain-map benchmarks/audio-integrity-v1/development-source-domains.json \
  --output /private/research/combined-features.pt \
  --record /private/research/combined-features-record.json \
  --record-id audio-integrity-combined-feature-cache-20260731-001
```

`train-audio-integrity-cnn-domain-holdout.py` excludes each complete source
domain in turn, stratifies inner early-stop groups across all remaining
domains, and selects a per-fold boundary without reading the excluded labels.
The 2026-07-31 experiments compared the absolute baseline, content-residual
channels, within-source paired ranking, GroupNorm, and equal-domain sampling.
The best false-positive result still produced 24/530 alerts while detecting
383/724 positives; the highest-recall result detected 539/724 but produced 99
alerts. GroupNorm plus balanced sampling reached 495/724 with 34 alerts. These
are development failures, not thresholds to fit further or candidates to
promote.

The run is retained as
`audio-integrity-domain-generalization-research-20260731-001.tar.zst`.
It preserves the cache commitments, case-level reports, 30 checkpoints, exact
research sources, comparison, and retention ledger. The verified 60-file
archive is 6,370,432 bytes with SHA-256
`6fcbed9effdc0bb61bc94fe75f86aac163e3147adaec2e4c390c5e7fc7255253`.
The extracted caches and Python environment are reproducible scratch; the
public/private audio corpora and prior verified archives remain retained.

### Long-block codec-framing research

The research runner has additive long-block fields based on the EUSIPCO 2018
transform/framing approach. `long-block-v16` measures one-second phase energy
differences for the MP3 576-bin sine, 1024-bin Vorbis/slope, and Opus 960-bin
CELT grids. It is a post-timing research probe, not part of feature version
`0`, and its values must not be serialized, cached, or exposed as a verdict.

On the 336-case public Tier A negative/paired set, the strict
maximum-of-grids zero-observed-false-positive boundary detected 180/192
positives (93.75%) with 0/144 alerts. The same rule failed after adding
NSynth: one sparse PCM resample raised the 250-negative boundary to 13.342 and
the combined recall fell to 133/404 (32.9%). A ten-block refinement reproduced
the tonal false peak at 13.551, so accepting only two valid blocks was not the
complete cause.

`analyze-audio-integrity-long-block-hybrid.py` can combine the three v16
reports with the archived leakage-safe CNN score reports:

```bash
python3 scripts/analyze-audio-integrity-long-block-hybrid.py \
  --candidate /private/research/public-negatives-v16.json \
  --candidate /private/research/public-paired-v16.json \
  --candidate /private/research/nsynth-v16.json \
  --nsynth-oof-cnn /private/research/nsynth-oof-cnn.json \
  --unseen-cnn /private/research/unseen-tier-a-cnn.json \
  --maximum-rules 3 \
  --minimum-recall 0.90 \
  --output /private/research/long-block-hybrid.json
```

The analyzer fits strict score boundaries above every guarded training
negative, then refits the same scalar rule templates in source-grouped outer
folds. The 2026-07-31 full-development diagnostic post-selected three rules
that covered 370/404 positives (91.6%) with 0/250 alerts, but none of 262
templates was safe and useful in all five grouped folds. Its disposition is
`failed_development_grouped_gate`; the held-out set must remain sealed.

The complete failed cycle is retained as
`audio-integrity-long-block-research-20260731-001.tar.zst`. It contains 26
files, is 2,223,655 bytes, and has SHA-256
`d85554740d40fbb59d1df243494f0bf484dd19cb82d6f065c684fa105f85575d`.
The archive includes the exact research binary, source/tests, raw reports,
selectively restored CNN evidence, analysis, integrity manifest, and ledger.
Its redundant repository scratch tree was removed only after streamed
verification and a second record/hash/list audit; the reusable corpora remain
in durable storage.

### AAC quantization-error research

The private research cycle independently reproduced the AAC frame-offset
quantization-error method from the 2019 JAES paper. It evaluated all 1,024
offsets, the AAC long/start/stop/eight-short MDCT windows, eight scale factors,
and mono/stereo LR/MS paths. The probe source is deliberately excluded from
this public, permissively licensed repository pending a separate licensing
review. It is not part of feature version `0` or any public surface.

The official companion MATLAB code is preserved privately with its hash and
terms for provenance. Its notice permits personal or research use and
prohibits commercial use. Do not copy it into product code or treat the
independent probe as licensing clearance.

The full public run scored 404 controlled positives and 197 negatives; 53
native 16 kHz NSynth PCM montages were recorded as unsupported. The paper's
fixed `0.031` boundary detected 308/404 positives but alerted on 44/197
negatives, including 43/53 NSynth PCM-only 48 kHz resamples. Moving the score
boundary above every development negative retained only 17/404 positives.

`analyze-audio-integrity-aac-quantization.py` derives ten predeclared scalar
summaries from the retained 1,024-offset curves and fits a single guarded rule
inside source-group folds. The best strict scalar detected 56/404 positives at
0/197 alerts. An optimistic full-development rule fit 80/404 at 0/197, but
five source-group outer folds produced 84/404 positives and 4/197 alerts. Its
disposition is `failed_development_grouped_gate`; the held-out set remains
sealed and this method must not be promoted.

The failed cycle is retained as
`audio-integrity-aac-quantization-research-20260731-001.tar.zst`. It contains
27 files, is 2,491,705 bytes, and has SHA-256
`0ac3cab6c16a10b60a13467330edd6ba6867fd0066f73ea59f8b7dfd54de3a10`.
The exact executable, independent source/tests, official reference source and
terms, raw reports and offset curves, grouped analysis, integrity manifest,
and ledger are retained in that external archive. The redundant repository research tree was removed
only after streamed verification and an independent record/hash/list audit;
the reusable audio corpora remain retained.

### MUSDB18-HQ external-transfer corpus

The retained MUSDB18-HQ cycle adds 150 independently verified 30-second PCM
full-mix source excerpts and 1,770 controlled lossless cases. It covers
untouched, PCM-low-pass, and PCM-resample negatives; FFmpeg and Apple
AudioToolbox AAC-LC 128, MP3 128, and native Vorbis q3 recall classes;
AAC-LC 192, MP3 320, and Opus 96 difficult classes; and AAC wrapper,
gain, and trim invariants. Exact intermediate hashes and commands are retained
in provenance, while the reproducible lossy intermediates were removed.

The frozen `conservative-two-grid-edge-v28` candidate was evaluated once and
rejected. It alerted on 3/600 negative cases: one cascaded steep 16 kHz PCM
low-pass and two 19 kHz PCM low-pass controls. All four scoped recall classes
passed at full support coverage, the 30 AAC invariant groups matched, and the
raw PCM reference plus PCM-only resample classes remained at zero alerts. Do
not retune v28 on this now-observed corpus or describe it as an untouched gate
again.

The final corpus seal is
`0f85343e140d3c0187156c58c9d88a90baa39807fcfd76c1ee50307e68a60318`.
The exact candidate, tool/environment commitments, raw measurements, support
report, evaluation, tests, and checkout input snapshot are preserved in
`audio-integrity-multicodec-explainable-research-20260731-001.tar.zst`
(SHA-256
`09266e16d2574c5df53dc54a2a735ef861e3329d83a430477908b05200e729d1`).
Retained inventory `audio-integrity-retained-corpora-20260731-003` accounts
for 5,124 cases and has SHA-256
`be59d00dbcaea92b8efd719518d07560a95e3836396209d66dbe449a11dc61d3`.
MUSDB18-HQ source and derived audio are local
educational/non-commercial research material; do not ship or redistribute
them.

Do not count modular mixes, excerpts from the same master, or multiple
performances from one recorded session as unrelated partitions. Split by the
registry's `partition_basis` before feature selection, and place every
derivative of a master in its master-level `source_group`.

### Isolated development staging

`stage-audio-integrity-pilot.py` can copy a deterministic, one-track-per-artist
sample into a newly created private run root. It refuses to reuse an existing
root, verifies each copy by SHA-256, and keeps the original-to-opaque-source
mapping in the private run ledger:

```bash
python3 scripts/stage-audio-integrity-pilot.py stage \
  --audio-root /private/tmp/lossytrace-research-dev-YYYYMMDD-001 \
  --run-id audio-integrity-dev-YYYYMMDD-001 \
  --source-dir /private/trusted-lossless-source \
  --count 40 \
  --pointer .tmp/audio-integrity/active-run.json
```

Treat source directories as read-only. Copied audio, generated variants,
private paths, fingerprints, and per-case results stay beneath the single
`cleanup_target` in `run-ledger.json`. The ignored pointer preserves that exact
target outside the corpus root.

For an inexpensive development read, derive a bounded analysis manifest while
preserving the full-track manifest:

```bash
python3 scripts/stage-audio-integrity-pilot.py window \
  --manifest /private/run/manifest.json \
  --output /private/run/manifest-90s.json \
  --ledger /private/run/run-ledger.json \
  --analysis-max-seconds 90
```

The separate `sharp-lowpass` command adds hard PCM negatives with a steep
15.7 kHz FIR cutoff. Keep them separate from the ordinary two-pole control so
an edge-only shortcut remains visible in the report.

## Reproducible variants

The optional `recipes` array creates private controlled positives and PCM hard
negatives with FFmpeg. It refuses to replace outputs unless `--overwrite` is
explicit:

```bash
python3 scripts/benchmark-audio-integrity.py prepare \
  --record /private/audio-integrity-v1/encoder-record.json
```

The record captures the FFmpeg version and commands with the audio root
redacted. Expand the example matrix to cover the codec, bitrate, wrapper,
sample-rate, gain, trim, dither, and encoder holdouts required by the design
plan. For hard low-pass negatives, review the actual filter response; the
example two-pole FFmpeg filter is illustrative and is not a substitute for the
required sharp codec-like cutoff controls.

### Settings-holdout expansion

After a development model or policy has been frozen, create a separate corpus
from lossless excerpts of the same development source groups. This is a codec
setting holdout, not a source or release holdout:

```bash
python3 scripts/stage-audio-integrity-pilot.py codec-holdout \
  --audio-root /private/tmp/lossytrace-research-codec-holdout-YYYYMMDD-001 \
  --run-id audio-integrity-codec-holdout-YYYYMMDD-001 \
  --parent-audio-root /private/tmp/lossytrace-research-dev-YYYYMMDD-001 \
  --parent-manifest /private/tmp/lossytrace-research-dev-YYYYMMDD-001/manifest-90s.json \
  --parent-ledger /private/tmp/lossytrace-research-dev-YYYYMMDD-001/run-ledger.json \
  --parent-run-id audio-integrity-dev-YYYYMMDD-001 \
  --pointer .tmp/audio-integrity/codec-holdout-run.json
```

The command creates one 45-second lossless excerpt per source group plus
controlled MP3, AAC, Opus, and Vorbis settings absent from the initial matrix.
Run `prepare`, `fingerprint`, and `run` exactly as for the primary corpus.
Previously trained fold models can be applied without retraining:

```bash
python3 scripts/score-audio-integrity-cnn.py \
  --manifest /private/codec-holdout/manifest.json \
  --audio-root /private/codec-holdout \
  --feature-cache /private/research/codec-holdout-features.pt \
  --model-report /private/research/cross-validation-a.json \
  --model-dir /private/research/models-a \
  --model-report /private/research/cross-validation-b.json \
  --model-dir /private/research/models-b \
  --output /private/codec-holdout/model-settings-holdout.json
```

Apply the fold-specific conjunctions from an earlier report without fitting a
new threshold:

```bash
python3 scripts/evaluate-audio-integrity-frozen-policy.py \
  --candidate /private/codec-holdout/dsp-settings-holdout.json \
  --model-score-report /private/codec-holdout/model-settings-holdout.json \
  --frozen-policy-report /private/research/frozen-policy.json \
  --output /private/codec-holdout/frozen-policy-settings-holdout.json
```

Any new combination rule selected after reading that output is development
tuning and needs another untouched corpus. The learned probe is a private
second-stage experiment; it is not part of version 1 and must not be serialized
or exposed publicly.

Learned-probe training requires every development manifest to be accompanied
by one or more fingerprint files covering exactly the same cases. It re-hashes
the audio before loading or creating a feature cache, groups outer and
early-stop splits by `partition_group`, and commits the report to the
spectrogram definition and cache hash. A cache created before that contract can
be used only with the explicit `--allow-legacy-feature-cache` exception, which
is recorded in the report; regenerate it for any future release-quality study.

## Fingerprint and run

Freeze the private inputs before a benchmark run:

```bash
python3 scripts/benchmark-audio-integrity.py fingerprint \
  --output /private/audio-integrity-v1/fingerprints.json
python3 scripts/benchmark-audio-integrity.py run \
  --fingerprints /private/audio-integrity-v1/fingerprints.json \
  --output /private/audio-integrity-v1/candidate.json
```

`analysis_max_seconds: 0` means full-track analysis. The example uses one timing
repetition for inexpensive setup checks; use at least three alternating
baseline/prototype repetitions on the benchmark machine before evaluating the
p95 runtime-overhead gate.

The runner decodes each file once, runs the production analysis pipeline with
the prototype off and on in alternating order, and returns raw measurements.
The prototype consumes the shared STFT already held by the pipeline. It does
not decode again, compute another FFT, or clone the spectrogram.

The optional codec-grid/phase probe in the research runner is a separate deep
forensic experiment. It performs additional MDCT searches after the timed
Stratum analysis, so `runtime_overhead_percent` in an ordinary candidate report
does **not** include it. Measure and disclose its actual process cost
separately:

```bash
python3 scripts/measure-audio-integrity-forensic-performance.py \
  --manifest /private/development/manifest-90s.json \
  --fingerprints /private/development/fingerprints.json \
  --audio-root /private/development \
  --binary ./target/release/examples/audio_integrity_benchmark \
  --case-id dev-001-original \
  --case-id dev-001-mp3-128-wav24 \
  --grid-profile stable-v15 \
  --repetitions 3 \
  --output /private/research/forensic-performance.json
```

This alternates isolated grid-disabled and grid-enabled processes, records wall
time and `/usr/bin/time` peak RSS, and commits to the runner, corpus,
benchmark-harness, and measurement-script hashes. A forensic candidate needs
its own version and cache identity; these numbers cannot satisfy the p95 10%
first-pass Stratum gate.

For development-only multi-rule research, the stable-template analyzer can
require the same feature/direction/rate template to be useful and
zero-false-positive in every source-grouped fold, then apply the fitted full
policy to source-group-disjoint candidates without refitting:

```bash
python3 scripts/analyze-audio-integrity-stable-rule-set.py \
  --candidate /private/development/candidate.json \
  --candidate /private/development/sharp-controls.json \
  --candidate /private/development/resample-controls.json \
  --evaluation-candidate /private/public/candidate.json \
  --maximum-rules 2 \
  --output /private/research/stable-rule-set.json
```

Template selection still observes development-fold outcomes. It is not an
untouched held-out evaluation and is intentionally incompatible with enabling
a public verdict.

Run the non-private harness and DSP regression tests independently of the
corpus:

```bash
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
cargo test -p lossytrace compression_trace
```

### Blind release-gate workflow

The release evaluation is deliberately different from the development and
codec-settings holdouts. It requires disjoint Tier A masters and opens the
sealed labels exactly once. The release-gate tool refuses non-Tier-A rows,
non-opaque case/source/partition IDs, label-revealing filenames, fewer than the
frozen minimum negative source groups, or an existing output path.

First generate and fingerprint the complete labelled held-out corpus. Its
manifest may contain private recipes, but every `case_id`, `source_group`, and
filename stem must be opaque. Seal it before giving the benchmark operator the
blind manifest:

```bash
python3 scripts/gate-audio-integrity-release.py seal \
  --manifest /private/heldout/manifest-labelled.json \
  --fingerprints /private/heldout/fingerprints.json \
  --seal-id audio-integrity-heldout-YYYYMMDD-001 \
  --minimum-negative-source-groups 150 \
  --blind-manifest /private/heldout/manifest-blind.json \
  --labels /private/heldout/sealed-labels.json \
  --output /private/heldout/seal.json
```

`manifest-blind.json` contains only the benchmark identity/path fields and the
placeholder class/expectation. Recipes and all additional per-case fields are
omitted. Keep `sealed-labels.json` private and unopened. The seal records hashes
of the blind manifest, labels, and audio fingerprints.

Build the runner once. Regenerate the development candidates with that exact
binary and generate the explainable policy report. Candidate reports and the
policy report now commit to the runner and benchmark-harness hashes:

```bash
cargo build --release -p lossytrace \
  --example audio_integrity_benchmark
python3 scripts/benchmark-audio-integrity.py \
  --manifest /private/development/manifest.json run \
  --audio-root /private/development \
  --fingerprints /private/development/fingerprints.json \
  --binary ./target/release/examples/audio_integrity_benchmark \
  --no-build --jobs 1 \
  --output /private/development/candidate-frozen-runner.json
python3 scripts/analyze-audio-integrity-explainable-policy.py \
  --candidate /private/development/candidate-frozen-runner.json \
  --output /private/development/explainable-policy.json
```

Freeze the policy, class coverage, statistical targets, performance targets,
development manifests/fingerprints, runner, harness, gate code, and unopened
seal. Repeat each class option and each development manifest/fingerprint pair
as needed. Targets are experiment inputs: choose and review them before
freezing, rather than copying values from a held-out result.

```bash
python3 scripts/gate-audio-integrity-release.py freeze \
  --development-report /private/development/explainable-policy.json \
  --development-manifest /private/development/manifest.json \
  --development-fingerprints /private/development/fingerprints.json \
  --development-candidate /private/development/candidate-frozen-runner.json \
  --runner ./target/release/examples/audio_integrity_benchmark \
  --heldout-seal /private/heldout/seal.json \
  --freeze-id audio-integrity-policy-YYYYMMDD-001 \
  --minimum-development-recall 0.90 \
  --minimum-heldout-recall 0.90 \
  --maximum-false-positive-upper-95 0.025 \
  --minimum-negative-source-groups 150 \
  --minimum-invariant-source-groups 40 \
  --maximum-invariant-relative-delta 0.05 \
  --maximum-p95-runtime-overhead-percent 10 \
  --maximum-peak-memory-increase-percent 10 \
  --minimum-timing-repetitions 3 \
  --obvious-positive-class mp3_96 \
  --hard-negative-class lowpass_only_pcm \
  --reference-negative-class untouched_pcm \
  --invariant-control-class gain_only_pcm \
  --output /private/heldout/freeze.json
```

The held-out recall gate requires the lower bound of the Wilson 95% interval to
pass separately for every frozen obvious-positive class, not only for a pooled
point estimate. The false-positive gate uses the upper bound over independent
negative source groups; multiple hard-negative variants from one master do not
inflate the effective sample size. With zero alerted groups across exactly 150
negative masters, that upper bound is just below 2.5%.

Run the blind candidate with the already-frozen binary. Do not rebuild it.
Measure peak RSS in isolated baseline and prototype processes for every case:

```bash
python3 scripts/benchmark-audio-integrity.py \
  --manifest /private/heldout/manifest-blind.json run \
  --audio-root /private/heldout \
  --fingerprints /private/heldout/fingerprints.json \
  --binary ./target/release/examples/audio_integrity_benchmark \
  --no-build --jobs 1 \
  --output /private/heldout/candidate.json
python3 scripts/benchmark-audio-integrity.py \
  --manifest /private/heldout/manifest-blind.json memory \
  --audio-root /private/heldout \
  --fingerprints /private/heldout/fingerprints.json \
  --binary ./target/release/examples/audio_integrity_benchmark \
  --no-build \
  --output /private/heldout/memory.json
```

Only then run the one-shot evaluator. All pre-label checks happen first. The
seal moves to `labels_opening` before the labels are parsed, so a crash or any
subsequent failure burns the held-out set instead of permitting a convenient
rerun. A completed result records class-stratified metrics and confidence
intervals, but still leaves `public_verdict_enabled` false pending explicit
integration review:

```bash
python3 scripts/gate-audio-integrity-release.py evaluate \
  --freeze /private/heldout/freeze.json \
  --seal /private/heldout/seal.json \
  --blind-manifest /private/heldout/manifest-blind.json \
  --labels /private/heldout/sealed-labels.json \
  --fingerprints /private/heldout/fingerprints.json \
  --candidate /private/heldout/candidate.json \
  --memory-report /private/heldout/memory.json \
  --confirm-seal-id audio-integrity-heldout-YYYYMMDD-001 \
  --output /private/heldout/release-evaluation.json
```

Archive and fully verify the complete held-out run—including labels, seal,
freeze, candidate, memory report, and evaluation—whether it passes or fails.
Never retune against a failed release set and call a rerun held out.

Use bounded concurrency only for exploratory feature distributions:

```bash
python3 scripts/benchmark-audio-integrity.py \
  --manifest /private/run/manifest-90s.json run \
  --audio-root /private/run \
  --fingerprints /private/run/fingerprints.json \
  --jobs 4 \
  --output /private/run/candidate.json
```

Runtime release gates require at least three repetitions with `--jobs 1`.
Concurrent single-repetition timing is not release evidence.

Generate a redacted statistical report without paths, hashes, or case-level
results:

```bash
python3 scripts/analyze-audio-integrity-pilot.py \
  --candidate /private/run/candidate.json \
  --candidate /private/run/candidate-sharp-lowpass.json \
  --output /private/run/development-analysis.json
```

Before cleanup, snapshot the union of all retained manifests and require zero
missing planned audio and zero unexpected paths:

```bash
python3 scripts/stage-audio-integrity-pilot.py snapshot \
  --audio-root /private/run \
  --manifest /private/run/manifest.json \
  --manifest /private/run/manifest-sharp-lowpass-90s.json \
  --output /private/run/artifact-inventory.json \
  --ledger /private/run/run-ledger.json \
  --pointer .tmp/audio-integrity/active-run.json \
  --state development_analyzed
```

Do not remove the run during analysis. After review, clean up only the exact
`cleanup_target` from the ledger, preferably by moving it to Trash for
recovery. First verify the originals:

```bash
python3 scripts/stage-audio-integrity-pilot.py verify-sources \
  --ledger /private/run/run-ledger.json
```

Remove the ignored pointer only after source hashes and repository status
remain unchanged.

## Gate discipline

Do not replace `baseline.json` or `fingerprints.json` merely because the
harness ran. First:

1. Complete the development pilot with at least 40 independent source masters.
2. Remove features that do not safely separate controlled positives from hard
   negatives.
3. Freeze feature definitions, policy thresholds, source/encoder/bitrate
   holdouts, and release targets before opening the held-out labels.
4. Run the untouched held-out evaluation with at least 150 independent negative
   masters and report class-stratified metrics and confidence intervals.
5. Confirm zero `likely_lossy_derived` outcomes for Tier A low-pass-only and
   sparse hard negatives, two independent reason families for every positive,
   and p95 runtime overhead no greater than 10%.

Until those gates pass, feature version `0`, cache schema `21`, and
`likely_lossy_derived_enabled: false` are intentional. Do not add a domain
verdict, MCP scan, Library Health warning, or schema-22 cache field.

The expanded 2026-07-31 development evidence keeps this stop gate closed:

- 48 public Tier A development partitions plus the original Tier B pilot and
  PCM controls produced 88 grouped partitions, 424 negatives, and 512
  controlled positives;
- the strongest stable two-rule explainable candidate detected 230/512 with
  0/424 grouped development false positives;
- a two-seed, leakage-safe CNN ensemble plus explainable features detected
  342/512 at its most useful setting but alerted on three PCM controls; its
  zero-false-positive setting detected only 138/512;
- the reduced two-grid profile stayed within the provisional performance
  budget on a six-case sample, but that does not repair the recall failure; and
- a paper-aligned independent implementation of the ISMIR 2024 CNN plus
  bidirectional-LSTM method detected 46/404 controlled positives while
  alerting on 27/250 PCM negatives across five held-out source domains; 14 of
  its 15 alerted source groups also contained a PCM false alert, so the
  grouped disposition is `failed_source_group_specificity_check`; and
- a frozen within-source paired-ranking CRNN improved Tier A rank ordering but
  detected only 86/404 positives with 48/250 PCM false alerts overall; its
  NSynth within-source ordering inverted to AUC 0.288, and all 28 alerted
  NSynth groups included a PCM alert, so its grouped disposition is also
  `failed_source_group_specificity_check`; and
- a refrozen broad-training paired CRNN added 200 officially disjoint NSynth
  train instruments and 40 private full-mix groups, but detected only 20/404
  transfer positives while alerting on 11/250 PCM negatives; four of five
  alerted groups also alerted PCM, so it too failed the source-group
  specificity check; and
- no disjoint 150-partition Tier A held-out release corpus has run.

The CRNN cycle is retained as the verified 31-file private archive
`audio-integrity-ismir2024-crnn-research-20260731-001.tar.zst` (89,482,692
bytes, SHA-256
`1537bd44e6667ced3dba649713e834baacd485567ad64d375e65cb159cc703c7`).
Its exact paper, environment lock, source and test snapshots, input
manifest/fingerprint snapshots, five checkpoints, case-level predictions,
source-group diagnosis, and retention ledger remain available for future
versions. The archived research root was removed only after independent hash,
stream, and member-list checks; its isolated environment and package cache
were moved to Trash. The three reusable audio corpora were not cleaned.

The paired-objective cycle is separately retained as the verified 29-file
private archive
`audio-integrity-source-paired-crnn-research-20260731-001.tar.zst`
(88,572,167 bytes, SHA-256
`6035bad31d7bb4b2318a3383ba3c4b4ff0234ca4977d965519d6b615eacb9a93`).
It includes the exact paired runner and tests, five checkpoints, case-level
and grouped reports, corpus metadata snapshots, environment lock, predecessor
commitment, and retention ledger. Its 94 MB working root was guarded-pruned
only after four-way archive verification; the recovered 466 MB environment
was returned to Trash. The reusable audio corpora remain directly available.

The broad sparse-training cycle is retained as the verified 58-file private
archive
`audio-integrity-broad-sparse-training-research-20260731-001.tar.zst`
(18,235,323 bytes, SHA-256
`58117eb89a4a41901ed92e07316e339f8a245ba6f23edb02143087e586bc87c7`).
It includes both frozen commitments, the failed pre-transfer attempt, exact
source/test/documentation snapshots, environment lock, checkpoint,
case-level and grouped reports, verification record, and retention ledger.
The 27 MB research root was guarded-pruned only after helper, independent
hash, zstd-stream, and regular-file member checks passed; the 466 MB
cycle-specific environment was moved to Trash. The durable inventory keeps
all 2,374 reusable cases and both source artifacts outside cleanup scope.

Private corpora are retained as verified `tar.zst` archives with a JSON archive
record and per-file integrity manifest. Use `verify-archive` before restoration
or deletion, and `prune-archived-source` only with the exact run ID recorded in
the ignored pointer. Research outputs can be preserved separately with
`archive-research`; `prune-archived-research` refuses to remove the exact
repository scratch tree until the archive passes a full streamed verification.
