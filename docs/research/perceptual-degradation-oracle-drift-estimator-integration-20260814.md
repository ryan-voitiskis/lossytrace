# Oracle drift-estimator integration - 2026-08-14

**Status:** a deterministic score-blind estimator now selects bounded clock
drift on frozen training windows, checks whether correction is worth applying
on disjoint held-out windows, invokes the exact frozen resampler when permitted,
and sends the result through alignment v2 and the score-free oracle. This closes
synthetic plumbing only. Retained-audio behavior, real drift estimation,
perceptual validity and human calibration remain unvalidated.

## Frozen estimator and decision

The fixture contains seven stereo cases: `+75`, `-60`, `0`, `+20`, `-20`,
`+100` and `-100 ppm`. The estimator searches a predeclared `-100` to
`+100 ppm` grid in `5 ppm` steps using five one-second training windows. It
selects by mean cosine correlation across both channels, with a frozen tie
break. The other five windows are not used for candidate selection.

The disjoint windows then gate application. A nonzero selection is applied only
when its selection margin is at least `0.0001`, held-out correlation reaches
`0.99`, and held-out improvement reaches `0.05`. The linear-interpolation proxy
used for selection and the independent observation generator are not the frozen
correction resampler.

## Synthetic result

All thirteen predeclared gates passed. Every selected correction matched its
synthetic drift. Correction was applied to `+75`, `-60`, `+100` and `-100 ppm`;
each channel ended at correlation `>= 0.999` and improved by `>= 0.1`. The
`+20` and `-20 ppm` cases selected correctly but stayed below the application
threshold, so their outputs remained bit-exact observed-PCM passthroughs. Zero
drift used the frozen bit-exact identity bypass.

All seven post-decision alignments were supported with no reason code. Every
oracle record remains `execution_blocked`; both metric families remain
`not_authorized`, and impairment severity and audibility probability remain
null. Two fresh temporary payload replays were byte-identical. Generated PCM
existed only in memory and was not retained.

## Boundary and next gate

This does not demonstrate estimation on retained or real audio. Held-out fixture
windows are an application check within a synthetic technical replay, not a
scientific validation set. No source or condition was selected, no perceptual
metric or human response was accessed, no no-reference model was trained, and
the public CLI remains verdict-free.

Under separate authority, the next technical gate is bounded retained
development-pair validation of the exact estimator, held-out apply rule and
correction path before any perceptual metric execution.

The report binds plan SHA-256
`d3c35d0c2e82b4424657183e14709a3b40ac91b085ea2618d9b9b3bcb9eb3a81`
and implementation SHA-256
`c3479334525a814e25bcc0ee2d5f569d4be07253d927f1e86788881df03bf3bc`.
The committed report SHA-256 is
`3d352e0112e39639b6d3162d5237e0c99f718220c5d527ed93c4b0a75bda5da4`.

Machine-readable artifacts:

- [`integration plan`](../../benchmarks/perceptual-degradation-v1/oracle-drift-estimator-integration-plan.json)
- [`integration report`](../../research/toolchains/evidence/perceptual-degradation-oracle-drift-estimator-integration-20260814-001.json)
- [`deterministic integration`](../../scripts/perceptual_degradation_oracle_drift_estimator_integration.py)
- [`mutation tests`](../../scripts/tests/test_perceptual_degradation_oracle_drift_estimator_integration.py)
