# LossyTrace

LossyTrace is an experimental Rust library, CLI, and research harness for
measuring traces that may be consistent with prior lossy audio compression.
It emits evidence, not a provenance verdict.

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

## Current direction

The [September 27 direction review](docs/research/codec-history-direction-20260927.md)
returns the practical focus to codec-history investigation: an understandable
verdict-free inspector and a source-grouped challenge benchmark. Human
recruitment and physical capture are not prerequisites for that work. The
perceptual programme's results remain preserved, without a completion claim.

No rejected detector is revived. The external Lossprint baseline has passed a
[bounded software qualification](docs/research/lossprint-qualification-result-20260927.md),
but [failed the fixed development challenge](docs/research/lossprint-challenge-result-20260927.md):
317/381 controlled positives were detected, alongside 53/336 benchmark-negative
alerts across six source groups. These selected, related cases are not a
real-library error-rate estimate. No model or threshold was retuned.

The release candidate is therefore an **inspector and benchmark, not a lossy
history detector**. It does not fulfill the original detection objective.
Lossprint is not bundled; historical codec-family and bitrate estimates are
not exposed. The perceptual-degradation objective also remains unresolved.

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
