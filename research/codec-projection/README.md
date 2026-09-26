# Codec-projection research subsystem

This isolated subsystem evaluates the two codec-conditioned residual summaries
frozen in
[`codec-projection-preregistration-20260802.md`](../../docs/research/codec-projection-preregistration-20260802.md).
It is research-only: it does not change the public Rust library, CLI evidence
schema, `feature_version`, or verdict boundary.

## Components

- `oracle-v1/config.json` is the checked-in measurement and gate contract.
- `oracle-v1/src/main.rs` canonicalizes PCM, performs two fixed FFmpeg/LAME
  projection cycles, and emits deterministic case measurements. Runtime and
  peak resident memory go to a separate timing file.
- `scripts/run-audio-integrity-codec-projection.py` selects the frozen observed
  population, verifies audio and tool commitments, checkpoints every case
  atomically, and composes a deterministic private raw report.
- `scripts/analyze-audio-integrity-codec-projection.py` applies the frozen
  leave-one-source-domain-out thresholds and emits a path-free aggregate.

Raw reports, case identities, paths, timings, and scores stay under the private
retained corpus. Only a path-free aggregate and a human-readable disposition
may be committed after evaluation.

## Outcome

The 2026-08-02 observed evaluation rejected both representations: each alerted
on one supported negative group and neither alerted on any of 471 supported
MP3-128 groups. The frozen stop rule therefore prohibited the conditional
robustness stage, candidate freezing, external-transfer evaluation, and public
integration. See the
[`result`](../../docs/research/codec-projection-result-20260802.md) and committed
[`path-free aggregate`](evidence/observed-20260802-002-aggregate.json). The
subsystem remains research-only negative-result infrastructure.

## Build and test

```sh
cargo fmt --manifest-path research/codec-projection/oracle-v1/Cargo.toml --check
cargo test --manifest-path research/codec-projection/oracle-v1/Cargo.toml
cargo clippy --manifest-path research/codec-projection/oracle-v1/Cargo.toml --all-targets -- -D warnings
cargo build --release --manifest-path research/codec-projection/oracle-v1/Cargo.toml
python3 -m unittest \
  scripts.tests.test_audio_integrity_codec_projection \
  scripts.tests.test_audio_integrity_codec_projection_analysis
```

The main repository checks remain mandatory as a separate gate.

## Bound observed run

Run only from a clean, pushed `codex/codec-projection-feasibility` checkout.
The harness rejects any other branch, dirty tree, changed audio hash, changed
manifest, changed tool binary/library, changed implementation, or mismatched
partial.

```sh
export LOSSYTRACE_CORPUS_ROOT="$HOME/Library/Application Support/lossytrace/benchmarks/audio-integrity-v1"
export LOSSYTRACE_CODEC_RUN="$LOSSYTRACE_CORPUS_ROOT/research-runs/codec-projection-observed-20260802-001"
mkdir -p "$LOSSYTRACE_CODEC_RUN"

caffeinate -is nice -n 15 python3 scripts/run-audio-integrity-codec-projection.py \
  --manifest "$LOSSYTRACE_CORPUS_ROOT/research-runs/observed-baseline-20260801-001/manifest.json" \
  --baseline-report "$LOSSYTRACE_CORPUS_ROOT/research-runs/observed-baseline-20260801-001/raw-report.json" \
  --corpus-root "$LOSSYTRACE_CORPUS_ROOT" \
  --oracle research/codec-projection/oracle-v1/target/release/lossytrace-codec-projection-oracle \
  --config research/codec-projection/oracle-v1/config.json \
  --preregistration docs/research/codec-projection-preregistration-20260802.md \
  --partial-root "$LOSSYTRACE_CODEC_RUN/partials" \
  --output "$LOSSYTRACE_CODEC_RUN/raw-report.json" \
  --timing-output "$LOSSYTRACE_CODEC_RUN/timing-report.json" \
  --ffmpeg /opt/homebrew/bin/ffmpeg \
  --lame /opt/homebrew/bin/lame \
  --jobs 1

python3 scripts/analyze-audio-integrity-codec-projection.py \
  --raw-report "$LOSSYTRACE_CODEC_RUN/raw-report.json" \
  --config research/codec-projection/oracle-v1/config.json \
  --preregistration docs/research/codec-projection-preregistration-20260802.md \
  --output "$LOSSYTRACE_CODEC_RUN/aggregate-report.json"
```

`--jobs 1` is mandatory. The run is resumable: repeat the command with the same
partial root and new output filenames. Every partial commitment is rechecked,
and the regenerated non-timing raw report must have the same SHA-256. The
aggregate is also deterministic. Timing evidence intentionally contains a
timestamp and is excluded from reproducibility hashes.

If neither representation passes, stop. If a representation passes, the only
authorized next step is the separately staged robustness set from the
preregistration; external transfer and public integration remain unauthorized.
