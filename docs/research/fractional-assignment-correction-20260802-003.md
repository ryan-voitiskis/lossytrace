# Factorial benchmark v2 fractional-assignment correction 003

Date: 2026-08-02

State: recipe `003` is superseded for construction before audio generation;
recipe `004` is frozen before its private assignment; no waveform sample,
benchmark audio, feature, score, or unopened label was read

## Trigger

The two byte-identical header-only construction-feasibility audits bound by
[`construction-feasibility-result-20260802-003.md`](construction-feasibility-result-20260802-003.md)
found 11 recipe-`003` groups whose assigned trim or duration-prefix transform
could not meet its already-frozen minimum input duration. The public recipe
`003` result has SHA-256
`31573d8ee523d6572d89b884ca5cbb1d815596c37d47831a31cb51d130bebe90`.
It remains evidence of the stopped assignment and is not deleted or rewritten.

The private feasibility audit has SHA-256
`9a4bbfcaa3742b1d665e2738547fd1ffaf74b2a0c245ed063610e8414f271a6c`.
It inspected lossless-stream headers for all 793 already-selected source groups,
not waveform samples. That complete header evidence is sufficient to derive
eligibility for every transform, including groups to which recipe `003` did
not assign that transform.

## Corrected information boundary

Recipe `004` keeps the recipe-`003` ranking prefix, purpose strings, source
allocation, quotas, codec settings, transforms, channel treatments, wrappers,
decoders, external reserve, and score boundary unchanged.

For each group and nonidentity transform, it now derives exactly one Boolean:

```text
excerpt_frame_count * 1000
    >= native_sample_rate_hz * minimum_input_milliseconds
```

`minimum_input_milliseconds` comes from the frozen transform factor and
defaults to zero. The raw frame count and sample rate may serve only this
predicate. They cannot enter the ranking hash, choose a categorical level,
alter an identity/anchor/nonanchor/reserve assignment, or appear in private or
public assignment output. Domain-balanced selection then runs with its
unchanged purpose string only within the groups eligible for that transform.

The generator must reproduce the unsupported findings recorded for recipe
`003`, reject unsupported native channel counts, and reject any cell whose
transform is ineligible for its group. The public aggregate may report only
path-free exclusion counts by partition, public source domain, and transform.

## Disposition

Recipe `004` must be committed before private execution, run twice from the
same frozen inputs, and produce byte-identical private assignments and
path-free aggregates. Construction, features, scores, and external positive
encoder selection remain unauthorized.
