# Factorial benchmark v2 construction-feasibility correction 001

Date: 2026-08-02

State: corrected audit recipe frozen before source-header inspection

The first recipe stopped during argument/configuration validation because the
public plan did not declare the `ffprobe_tool_id` required by the bound audit
generator. The stop occurred before a source artifact was hashed, a member was
extracted, a header or duration was inspected, audio was generated, or a score
was opened.

Recipe `lossytrace-v2-construction-feasibility-20260802-002` adds the exact
already-bound `ffprobe_8_1_2_1` identifier and changes no source, assignment,
window, duration, transform, reporting, or stopping rule. Its plan SHA-256 is
`b4ef7edc0e2e0f9b55834adc9dca399ef3ca157e3922d4520fdfdfaa387fc25f`.
Its generator SHA-256 is
`b239f287b94cdcd2278045271859060764e34bb8a251ed295fbd62f07d440930`.
The correction binds upstream checkpoint
`32c444d2ed3a54a184bf0ddeccb5de0bfc5c2687`.

Commit this correction before either complete audit replay. The same
byte-identical two-replay gate remains mandatory.
