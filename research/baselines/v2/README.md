# Factorial benchmark v2 baselines

This directory contains public, path-free mechanism-development baseline
evidence only. Private case rows, audio hashes, paths, partials, checkpoints,
model weights, and the complete factorial manifest stay outside Git.

The exact protocol and evidence boundaries are in the
[`preregistration`](../../../docs/research/development-baseline-preregistration-20260802.md)
and machine-readable
[`plan`](../../../benchmarks/audio-integrity-v2/development-baseline-plan.json).

The baseline stage compares the published fixed Cannam rule, LossyTrace's
descriptive feature-version-0 measurements, naive and randomly masked
Koops-style CRNN replications, and retained rejected explainable controls.
These are reference systems and failure probes, not candidates. Encoder and
external transfer remain sealed, and no result enables a public verdict.

The fixed Cannam and feature-version-0 runs are complete. Their path-free
aggregates are in [`evidence`](evidence), and the joint interpretation and
hash commitments are in the
[`fixed-baseline result`](../../../docs/research/development-fixed-baseline-result-20260802.md).
Cannam's 91.82% factorial-case recall coexists with a 64.05% false-positive
rate and only 46.68% paired positive direction. No feature-version-0
measurement passes the frozen paired gate. The naive/masked CRNN comparison
and retained explainable controls remain pending; neither transfer partition
has been opened.
