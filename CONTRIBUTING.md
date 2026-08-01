# Contributing

LossyTrace is evidence-first research software. A recall improvement is not a
release improvement if it weakens false-positive safety, transform invariance,
split isolation, or provenance accounting.

Before opening a pull request, run:

```bash
cargo fmt --check
cargo clippy --all-targets -- -D warnings
cargo test --all-targets
python3 -m unittest discover -s scripts/tests -p 'test_audio_integrity*.py'
```

Do not commit real audio, private corpus manifests, model caches, per-case
measurements, or machine-specific paths. New candidate policies must use a new
identifier and must not be tuned against a consumed holdout. A failed gate is
recorded as a failed gate; it is not repaired by changing thresholds against
the same evidence.

Commits use Conventional Commit messages.
