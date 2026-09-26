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

The fixed Cannam, feature-version-0, and naive/masked CRNN runs are complete.
Their path-free aggregates are in [`evidence`](evidence). The fixed-system
interpretation and hash commitments are in the
[`fixed-baseline result`](../../../docs/research/development-fixed-baseline-result-20260802.md),
and the learned comparison is in the
[`CRNN result`](../../../docs/research/development-crnn-baseline-result-20260803.md).
Cannam's 91.82% factorial-case recall coexists with a 64.05% false-positive
rate and only 46.68% paired positive direction. No feature-version-0
measurement passes the frozen paired gate. Naive CRNN alerts on 518/527
negative source groups and reaches only 70.59% paired direction; the masked
condition alerts on all 527 negative groups and falls to 59.20% paired
direction. The retained explainable controls were frozen under the separate
[`adapter preregistration`](../../../docs/research/explainable-control-v2-adapter-preregistration-20260803.md)
and
[`adapter plan`](../../../benchmarks/audio-integrity-v2/explainable-control-adapter-plan.json).
The stage then stopped because A0-A4 could not represent all fixed-duration
inputs without a prohibited support change. R1/R2 completed and replayed
byte-identically, but remain uninterpreted because the frozen combined analyzer
could not run. See the
[`protocol-stop report`](../../../docs/research/development-explainable-control-protocol-failure-20260803.md)
and path-free
[`failure record`](evidence/explainable-controls-observed-20260803-001-protocol-failure.json).
Neither transfer partition has been opened.

The final gate decision and recommended next boundary are in the
[`decoded-PCM identifiability result`](../../../docs/research/decoded-pcm-identifiability-result-20260803.md)
and machine-readable
[`decision record`](evidence/identifiability-decision-20260803.json). No
completed interpreted representation passed the paired discovery gate, so no
new representation or transfer opening is authorized.
