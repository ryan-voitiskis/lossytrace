# LossyTrace

LossyTrace is an experimental Rust library, CLI, and research harness for
measuring traces that may be consistent with prior lossy audio compression.

**Project parked on 24 November 2026.** The release candidate provides a local
audio inspector and a reproducible benchmark. This checkout also compares the
decoded audio in two files. The original question of whether a single finished
track passed through a lossy codec remains open. [Research closeout](#research-closeout)

> [!WARNING]
> The current measurement definition is feature version `0`. It has known
> content-dependence and invariance failures. LossyTrace does not currently
> label files as lossless, lossy-derived, authentic, or fraudulent.

## Quick start

Release-candidate binaries and verification records are published on the
[releases page](https://github.com/ryan-voitiskis/lossytrace/releases).
The declared native targets are Apple Silicon macOS and Linux x86-64; see
[release notes](docs/release-notes.md) for tested OS versions and limitations,
and the [release process](docs/release-process.md) for reproducibility scope.

Build from source and inspect an audio file:

```bash
cargo run --locked --release -- analyze track.flac --pretty
```

Explain the fields and their limitations without opening audio:

```bash
cargo run --release -- explain
```

The [inspection guide](docs/inspection-guide.md) separates observed signal
properties from processing-history claims. Missing evidence does not certify
lossless history, and values between zero and one are not calibrated
probabilities. No automatic deletion or retagging policy is supported.

The JSON contract makes the experimental status explicit:

```json
{
  "schema_version": 1,
  "state": "experimental_measurements_only",
  "public_verdict_enabled": false,
  "compression_trace": {
    "feature_version": 0
  }
}
```

By default the CLI inspects at most 120 seconds. Pass `--max-seconds 0` to
inspect the complete file. The report includes a SHA-256 input fingerprint but
does not include the input path.

### Compare two copies of a recording

The current source tree adds an exact comparison for two local WAV or FLAC
files. Build from this checkout to use it. The published RC predates this command.

```bash
cargo run --locked --release -- compare first.wav second.flac --pretty
```

Look for `same_decoded_audio`. A value of `true` means the sample rate, channel
count, length and ordered sample values match across the complete files.
Retagging, lossless rewrapping, and exact 16-to-24-bit promotion can all give
a match. A value of `false` tells you the audio differs. Either result can
occur with recordings that share a lossy ancestor. See the
[comparison details and supported inputs](docs/inspection-guide.md#compare-two-copies).

## What is here

- `src/`: the verdict-free compression-trace measurements and CLI.
- `benchmarks/audio-integrity-v1/`: reproducible benchmark contracts,
  manifests, fingerprints, and aggregate development reports.
- `benchmarks/audio-integrity-v2/`: the source-grouped factorial challenge
  benchmark, sealed evidence partitions, and frozen baseline plans.
- `scripts/`: corpus staging, controlled lossy-to-lossless generation,
  evaluation, safety gates, and research tooling.
- `research/exact-transform/`: source recovered from the final exact-transform
  research cycle, including the exact MP3 hybrid-filterbank probe.
- `docs/research/`: the original Reklawdbox plan and the research disposition.

The 33 research iterations were experiments, not 33 software releases. The
latest candidates remain rejected. See
[`docs/research/status.md`](docs/research/status.md) and the
[`decoded-PCM identifiability result`](docs/research/decoded-pcm-identifiability-result-20260803.md).

## Research closeout

The clearest result came from testing the same model with and without access
to a reference. On 64 synthetic compositions, the model scored an encoded
copy above its own original in 378 of 384 comparisons. Given each file on its
own, it flagged zero of those 384 copies at the preset threshold. All three
tested pipelines missed the pilot’s detection and coverage targets.
[Single-file pilot](research/music-library-pilot-v1/single-file-comparator-20261124.md)

The external Lossprint detector caught 317 of 381 controlled encodes on a
separate challenge and also flagged 53 of 336 benchmark negatives. The
finished-music study stopped before training because the available recordings
could not supply the 540 independent groups with documented histories that
its design requires. Accuracy on a music library remains unknown.
[Lossprint challenge](docs/research/lossprint-challenge-result-20260927.md) ·
[Finished-music study disposition](research/music-verdict-v1/offline-study-disposition-20261124.md)

**Reopen the research if** a documented collection offers a credible path to
the frozen study’s source requirements, or a new detection method predicts a
specific result that the existing benchmark can test. In the meantime,
`analyze` and `explain` are available in `v0.1.0-rc.1`. For exact WAV/FLAC
comparison, build from commit `a329951` or this checkout.
[Study design](docs/research/music-verdict-successor-20260927.md) ·
[Release notes](docs/release-notes.md)

## Data policy

No copyrighted or privately supplied audio belongs in this repository.
LossyTrace keeps only generators, provenance manifests, hashes, and aggregate
reports in Git. Real-audio corpora live in an external data directory and are
ignored. Research code with unresolved redistribution boundaries is also kept
outside the public repository. See
[`docs/data-governance.md`](docs/data-governance.md) and
[`docs/research/licensing-boundary.md`](docs/research/licensing-boundary.md).

## Verification

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --all-targets
python3 scripts/run_regression_tests.py
```

Some corpus and benchmark checks are intentionally opt-in because they require
licensed or locally retained audio. They must fail closed when their declared
inputs or fingerprints are missing.

The Python runner preserves and replays byte-bound historical audits at their
recorded checkpoint while testing current software separately; see
[Contributing](CONTRIBUTING.md) for runtime and Git-history requirements.

## Relationship to Reklawdbox

This work began as an opt-in `stratum-dsp` prototype inside Reklawdbox. It was
extracted because detector research has a different release cadence and risk
profile. Reklawdbox must not consume a LossyTrace verdict until a fresh,
independent validation gate passes and a stable evidence contract is released.

## License

Licensed under either the Apache License, Version 2.0 or the MIT License, at
your option.
