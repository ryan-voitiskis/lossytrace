# Factorial benchmark v2 analysis-manifest correction 003

Date: 2026-08-02

State: validator-vocabulary correction frozen after a complete artifact rehash;
no manifest output, feature, or score opened

## Trigger

The first invocation under correction 002 rehashed all 12,885 retained
artifacts, totalling 13,679,285,412 bytes. Materialization then reached the
structural validator and stopped before writing either the private manifest or
the path-free run report.

The validator rejected 12 encoder settings whose frozen
`encoder_lowpass.mode` is `implementation_fixed_or_default`. That value is
present in the preregistered factor levels and the frozen toolchain bindings;
it distinguishes implementations with a built-in fixed cutoff that cannot be
cleanly represented as either an explicitly requested cutoff or a freely
chosen encoder default. The manifest validator's older four-value vocabulary
had simply omitted it.

No artifact was decoded for analysis. No feature, model output, encoder
transfer score, external transfer score, or public verdict was produced.

## Correction

The manifest validator now accepts the already-frozen
`implementation_fixed_or_default` factor value. It continues to reject
undeclared values and still requires a positive numeric frequency for a
`fixed` cutoff.

Because this replay demonstrated that validation code is part of the evidence
boundary, the plan now also hash-binds the exact manifest validator. The
compositor verifies that binding before reading artifacts and records its hash
in the private manifest and path-free run evidence.

No source, artifact, PCM, setting value, recipe, partition, provenance record,
freeze threshold, or evidence-opening rule changes. Two fresh complete replays
remain required.
