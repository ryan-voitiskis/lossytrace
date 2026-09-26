# Contributing

LossyTrace is evidence-first research software. A recall improvement is not a
release improvement if it weakens false-positive safety, transform invariance,
split isolation, or provenance accounting.

Before opening a pull request, run:

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --all-targets
python3 scripts/run_regression_tests.py
```

The Python runner tests current software and separately replays 23 byte-bound
historical audit modules at checkpoint `48f0f63f5f87b0afa816ef0ee869c157e7f232b3`.
It checks preservation of existing research files before execution, permits
only append-only additions to the historical status log, and does not skip
those tests or update their consumed hashes. All new test modules run against
the current tree. Full Git history, Git worktree support and Rust 1.94.0 are
required for the historical decoder audit. Use an external `TMPDIR` for local
research testing. Direct discovery remains useful for focused tests, but the
historical audits intentionally reject a newer CLI's different source bytes.

Do not commit real audio, private corpus manifests, model caches, per-case
measurements, or machine-specific paths. New candidate policies must use a new
identifier and must not be tuned against a consumed holdout. A failed gate is
recorded as a failed gate; it is not repaired by changing thresholds against
the same evidence.

Commits use Conventional Commit messages.
