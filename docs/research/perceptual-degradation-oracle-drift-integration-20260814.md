# Oracle drift integration - 2026-08-14

**Status:** the already-frozen held-out apply decisions now drive the exact
frozen bounded-clock-drift resampler through the score-free oracle on synthetic
stereo PCM. This closes synthetic correction plumbing only. Retained-audio
behavior, real drift estimation, perceptual validity and human calibration
remain unvalidated.

## Bound integration

The integration binds three previously separate artifacts:

- the `+75`, `-60` and `0 ppm` decisions selected on training windows and
  checked on disjoint held-out windows;
- `oracle-bounded-drift-kaiser-sinc128-q30-v1`, including its exact 128-tap,
  2,048-phase Q30 table; and
- the topology-aware alignment plus score-free full-reference oracle envelope.

The observation generator remains the independent binary64 linear-interpolation
fixture. It is not the frozen correction resampler. The synthetic source is
rounded to signed Q20 before drift generation so its PCM hashes do not inherit
platform `libm` differences; reported floating-point diagnostics are rounded
to 12 decimal places. Corrected PCM exists only in memory, applied cases
discard 64 frames at each edge, and zero drift uses the bit-exact identity
bypass.

## Synthetic result

All twelve predeclared integration gates passed across three cases. The two
applied cases produced:

| Drift | Minimum correlation before | Minimum correlation after | Minimum improvement |
| --- | ---: | ---: | ---: |
| `+75 ppm` | 0.841636 | 0.999155 | 0.155757 |
| `-60 ppm` | 0.893406 | 0.999231 | 0.104641 |

Both post-correction stereo alignments were supported with no reason code and
reported `0 ppm` residual drift in the synthetic fixture. The zero-drift case
was bit-exact, used no edge discard and retained correlation `1.0` in both
channels.

The resulting oracle records remain `execution_blocked`. ViSQOL and GstPEAQ
states remain `not_authorized`; impairment severity and audibility probability
remain null. No audio payload, path, timing, metric result or human outcome is
present in the report. Two fresh temporary payload replays were byte-identical.

## Boundary and next gate

This is not retained-audio validation and does not show that the drift estimator
works on real audio. It does not validate a perceptual metric, a human-calibrated
oracle, a negative class or a no-reference target.

Under separate authority, the next technical gate is to validate the exact
integrated correction and drift-estimation behavior on retained development
pairs before any perceptual metric execution.

The report binds plan SHA-256
`3fc4595e9d7e65201aca6d305e29bd627ae49ab46a570bd03fc2e4935053d8bf`
and implementation SHA-256
`86435d0775bbd142b452e350bb0ff9010405bb3366d91e2bd34e11d34f3d2668`.
The committed report SHA-256 is
`494e09bd8d728573bdb285889affb8aca4e2d068b134b7b88f96172505de9289`.

Machine-readable artifacts:

- [`integration plan`](../../benchmarks/perceptual-degradation-v1/oracle-drift-integration-plan.json)
- [`integration report`](../../research/toolchains/evidence/perceptual-degradation-oracle-drift-integration-20260814-001.json)
- [`deterministic integration`](../../scripts/perceptual_degradation_oracle_drift_integration.py)
- [`mutation tests`](../../scripts/tests/test_perceptual_degradation_oracle_drift_integration.py)
