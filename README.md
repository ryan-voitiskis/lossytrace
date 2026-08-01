# LossyTrace

LossyTrace is an experimental Rust library, CLI, and research harness for
measuring traces that may be consistent with prior lossy audio compression.
It emits evidence, not a provenance verdict.

> [!WARNING]
> The current measurement definition is feature version `0`. It has known
> content-dependence and invariance failures. LossyTrace does not currently
> label files as lossless, lossy-derived, authentic, or fraudulent.

## Quick start

Build from source and inspect an audio file:

```bash
cargo run --release -- analyze track.flac --pretty
```

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
- `scripts/`: corpus staging, controlled lossy-to-lossless generation,
  evaluation, safety gates, and research tooling.
- `research/exact-transform/`: source recovered from the final exact-transform
  research cycle, including the exact MP3 hybrid-filterbank probe.
- `docs/research/`: the original Reklawdbox plan and the research disposition.

The 33 research iterations were experiments, not 33 software releases. The
latest candidates remain rejected. See
[`docs/research/status.md`](docs/research/status.md).

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
python3 -m unittest discover -s scripts/tests -p 'test_audio_integrity*.py'
```

Some corpus and benchmark checks are intentionally opt-in because they require
licensed or locally retained audio. They must fail closed when their declared
inputs or fingerprints are missing.

## Relationship to Reklawdbox

This work began as an opt-in `stratum-dsp` prototype inside Reklawdbox. It was
extracted because detector research has a different release cadence and risk
profile. Reklawdbox must not consume a LossyTrace verdict until a fresh,
independent validation gate passes and a stable evidence contract is released.

## License

Licensed under either the Apache License, Version 2.0 or the MIT License, at
your option.
