# Perceptual-degradation objective audit: source-trait and drift refresh - 2026-08-14

## Outcome

The full objective remains incomplete. Four of fourteen completion requirements
are satisfied and ten remain unproven. This refresh binds two later technical
and source-provenance checkpoints without promoting them beyond their evidence:

- the bounded-clock-drift oracle resampler is selected after passing all nine
  synthetic gates, but it is not integrated after a held-out apply decision or
  validated on retained development pairs; and
- the seven required natural source-trait proof obligations are frozen, but
  only five have candidate records. Quiet has a provider-level audit route and
  no exact candidate; naturally clipped has no candidate.

No exact-member manifest, source or metric successor, human calibration,
metric result, grouped transfer result, no-reference model or final
recommendation exists.

## Current requirement audit

| Requirement | Current evidence state |
| --- | --- |
| Degradation-not-history estimand | satisfied contract boundary |
| Declared playback chain | satisfied prerequisite |
| Truth-bearing source manifest | arithmetic feasible; trait candidates incomplete; exact manifest unfrozen |
| Controlled human calibration | not authorized or collected |
| Perceptual metric gate | ViSQOL-only successor preregisterable; unselected; execution closed |
| Human-calibrated full-reference oracle | technical drift resampler frozen; integration and scientific validation closed |
| Transparent lossy treated as non-degraded | policy frozen; truth absent |
| Difficult natural and production negatives | proof contract ready; candidate coverage incomplete; not evaluated |
| Source/domain/codec/encoder grouped transfer | not evaluated |
| No-reference estimator | not started by design |
| Severity/audibility/artifact/support/uncertainty outputs | schema ready; values unavailable |
| Public CLI verdict-free | satisfied current boundary |
| Rigorous negative accepted | satisfied success criterion |
| Final research recommendation | absent |

## Drift-correction boundary

The frozen
[`oracle drift resampler`](perceptual-degradation-oracle-drift-resampler-20260814.md)
passed all predeclared preservation and response gates and is the selected
technical correction algorithm. Selection does not establish integration,
retained-audio behavior, perceptual validity or full-reference accuracy.

The older score-free audio-view replay used a fixed 44.1-to-48 kHz FFmpeg
conversion to provide the input rate expected by a metric. That fixed-rate view
is not bounded clock-drift correction and cannot satisfy the new integration
gate. A responsible integration must occur only after the held-out drift apply
decision and must use the exact frozen resampler. Current authority excludes
that operation and retained development-pair validation.

## Source-trait boundary

The frozen
[`source-trait identifiability contract`](perceptual-degradation-source-trait-identifiability-20260814.md)
requires provenance as well as PCM descriptors. Five of seven traits have
candidate records. Quiet and naturally clipped remain missing from that count,
and sparse versus tonal still needs independent contrasts.

The later
[`provider-capability screen`](perceptual-degradation-source-trait-provider-capability-screen-20260814.md)
found a plausible SONYC route for a later quiet audit, not a quiet member. It
found only a Freesound search mechanism for clipped material, not a naturally
clipped candidate. Provider capability is not exact-member provenance, and a
bounded search failure is not proof of global absence.

## Preserved sequence

1. Under separate authority, perform a bounded exact-member metadata and
   provenance audit; require exact quiet and naturally clipped candidates plus
   independent sparse and tonal contrasts before freezing a source-trait
   manifest.
2. Select or reject the preregisterable ViSQOL-only successor under an
   independent score-blind amendment; selection still would not authorize
   execution.
3. Under separate authority, integrate the exact drift resampler after the
   held-out apply decision and validate it on retained development pairs before
   metric execution.
4. Complete stimulus, privacy, power and allocation gates and collect
   controlled human calibration.
5. Execute the selected metric only under a later exact gate, then pass the
   human-calibrated full-reference and grouped-transfer gates.
6. Only then freeze, train and independently validate a no-reference estimator.
7. Freeze exactly one final research recommendation.

Transparent lossy controls remain non-degraded by policy unless controlled
human truth supports material impairment. All twenty difficult natural and
production negative classes remain required. Explicit abstention remains
mandatory where support is absent. A rigorous rejection or full-reference-only
result remains successful, and the public CLI remains verdict-free.

## Determinism and authority

Two fresh report generations were byte-identical at SHA-256
`169b5f8c832c5c754b61d15f73750fca5389221c1bb94ff09de8050a34dd7c4b`.
The report binds plan SHA-256
`d90b5586a9f23eb36a95cb1481aec278c2460e221a0539116b167034b16b135e`
and implementation SHA-256
`e9da0e08a4c57e899d8850a7a5fd0e9dc685543e59de577ab22d1b972fbb99ea`.

This audit read only committed metadata and source text. It accessed no audio,
opened no score or sealed evidence, executed no perceptual metric, integrated
no correction, trained no model and enabled no public verdict.

Machine-readable artifacts:

- [`refreshed audit plan`](../../benchmarks/perceptual-degradation-v1/objective-completion-audit-plan-20260814-003.json)
- [`refreshed audit report`](../../research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260814-003.json)
- [`refreshed audit implementation`](../../scripts/perceptual_degradation_objective_completion_audit_v3.py)
- [`mutation tests`](../../scripts/tests/test_perceptual_degradation_objective_completion_audit_v3.py)
