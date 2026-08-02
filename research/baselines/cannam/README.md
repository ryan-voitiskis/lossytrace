# Cannam fixed-rule baseline

This directory preserves the path-free result of the exact published-weight
Cannam Vamp detector replay. It is a rejected research baseline, not part of
the public LossyTrace library, CLI, feature schema, or verdict surface.

The fixed method, populations, and interpretation rules are in the
[`preregistration`](../../../docs/research/baseline-failure-atlas-preregistration-20260802.md).
The duration-sensitive pilot correction is in
[`amendment 001`](../../../docs/research/baseline-failure-atlas-amendment-20260802-001.md).
The observed result and disposition are in the
[`result`](../../../docs/research/cannam-fixed-rule-failure-atlas-result-20260802.md).

`evidence/observed-20260802-001-aggregate.json` is the deterministic path-free
aggregate. Private manifests, case rows, paths, audio hashes, audio, and
partials remain in the retained corpus outside Git.

The baseline is frozen and rejected. Do not tune its model or thresholds,
derive a support filter from its failures, or expose it as a prior-history,
authenticity, codec-identification, or provenance verdict.
