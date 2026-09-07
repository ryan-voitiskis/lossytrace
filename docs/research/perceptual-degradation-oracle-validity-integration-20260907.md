# Score-free oracle validity integration — 2026-09-07

The separate full-reference oracle v2 consumes validity-aware alignment v3
without converting unavailable diagnostics into scores. It checks record
consistency and preserves the original alignment payload. It does not verify
waveform provenance, clean-reference eligibility or perceptual quality.

## Development contract

The [integration plan](../../benchmarks/perceptual-degradation-v1/oracle-validity-integration-plan.json)
binds the unchanged alignment implementation, prior synthetic report, legacy
oracle, research contract and probability-target contract. The plan was declared
before these executions but is published with development results; this is not
independent preregistered validation. Old implementations and evidence remain
unchanged. The new Python semantic validator is the record contract; no separate
JSON Schema or public CLI integration is introduced.

The caller must declare `subtle` (four active seconds) or `quality_metric`
(eight active seconds). The runner passes that setting explicitly to the bound
producer. The assembler recomputes support predicates under the declared mode,
because raw alignment records do not record the producer's configuration.
Consistency is not proof that a caller actually used that configuration. The
nominal two-second search parameter includes the producer's additional coarse
rounding and one-envelope-block sample refinement; it is not represented as a
hard two-second bound on the selected lag.

Validation covers explicit signed/magnitude correlation validity, candidate and
window counts, delay/overlap/trim arithmetic, gain sign and numeric consistency,
channel-level rejection reasons and all-required-channel aggregates. A missing
channel cannot disappear from a minimum or average. Opposite channel drift
rejections cannot cancel through their mean. Gain consistency admits ordinary
floating-point rounding, including subnormal values; this is not a new acoustic
threshold. No sample correction or gain normalization is performed.

The prototype representation accepts mono/stereo records with the existing
`M`, `L`, `R` labels. Other channel representations are rejected, not assessed.
Ragged original channel lengths cannot be reconstructed from the input summary;
their producer-declared rejection is retained, never promoted into a pass.
These limitations preclude claiming a general waveform or provenance validator.

## Declared synthetic cases

| Construction | Alignment | Oracle state |
|---|---|---|
| Six-second stereo identity, subtle mode | Supported | Execution blocked |
| Right-channel polarity inversion, subtle mode | Supported | Execution blocked |
| Right-channel dropout | Unsupported | Unsupported alignment |
| Mono identity with a central silent interval | Unsupported | Unsupported alignment |
| Six-second identity, quality-metric mode | Unsupported: insufficient active audio | Unsupported alignment |
| Twelve-second identity, quality-metric mode | Supported | Execution blocked |
| Stereo reference versus mono test | Unsupported: channel/map mismatch | Unsupported alignment |

The twelve-second construction concatenates an already consumed numeric fixture.
It is not a new natural source, independent group, perceptual stimulus or way to
make sparse real material eligible. The central-silence case retains four of
five valid drift windows and six of seven structural windows; both local models
remain unavailable. Polarity inversion remaining alignable does not establish
fidelity or authorize its correction.

The [synthetic report](../../research/toolchains/evidence/perceptual-degradation-oracle-validity-integration-synthetic-20260907-001.json)
retains every declared case and projects the common alignment diagnostics.
Only this runner declares its own in-memory synthetic origin. The generic
assembler explicitly leaves input provenance and clean-reference eligibility
unverified. Tests exercise contradictory records as validation mutations; the
opposing-drift mutation is not a new PCM drift experiment.

Two complete final synthetic replays are byte-identical (11,642 bytes each).
Their seven state transitions match explicit fixture expectations. The report
binds the exact implementation; focused tests compare its projection with live
producer records. This is deterministic integration evidence, not independent
scientific validation or evidence of generalization.

## Scientific boundary

All seven records have oracle support `false`. Severity, artifact components,
correct-response probability, audible-condition probability and their intervals
remain `null`. Correct-response probability is not silently renamed audibility;
prediction unit and population averaging remain unselected. Unavailable values
are not evidence of transparency or absence of impairment.

No metric suite or execution gate is selected, including the prepared ViSQOL-only
option. Human calibration remains unavailable. This integration supplies neither
listening evidence nor validation of perceptual estimation. It opens no source
assignment, capture execution, metric, human collection, training or public-verdict
gate. The authorized capture still requires its exact physical setup and separate
execution checkpoint. The overall objective remains active and incomplete.
