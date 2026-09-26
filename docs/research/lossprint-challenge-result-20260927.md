# Lossprint challenge result — 2026-09-27

**Decision: the fixed external baseline failed the preregistered continuation
gate. Ship the authorized verdict-free inspector-and-benchmark RC, not a
codec-history detector. The original detection objective remains unmet.**

This is a bounded result on consumed development material, not an estimate of
the error rate in a music library and not a claim that Lossprint never works.
The small selected population, historical negative-label provenance and
unresolved overlap with the external model's private training corpus limit
interpretation. No human listening or quality inference was involved.

## Execution and integrity

The [preregistered challenge](lossprint-challenge-preregistration-20260927.md)
ran once at commit `15dcffc24269dd1277d69d9fbf3e160a7b4c71a3`, after
[exact-commit CI passed](https://github.com/ryan-voitiskis/lossytrace/actions/runs/36256688958).
The qualified model and binary, upstream threshold 0.5, selection, budgets,
and analysis were unchanged. All 1,386 slots completed: 693 artifacts in two
ordered replays, representing 717 cases and 556 unique analysis PCM identities.
There were no unsupported cases, retries, crashes, timeouts or missing calls.
Replay and equal-PCM wrapper outputs matched exactly. Input, source, model,
tool and repository bindings remained intact. Total execution was 269.670
seconds. No new derived audio or playback was produced.

The separate auditor re-read saved outputs and artifact hashes without new
inference, verified all slots and independently reproduced the primary counts
and continuation decision. The [saved aggregate](../../research/baselines/lossprint/evidence/challenge-result-20260927-001.json)
and [audit](../../research/baselines/lossprint/evidence/challenge-audit-20260927-001.json)
are exact copies of their execution outputs. The audited aggregate SHA-256 is
`ad0e17f0429095748cd07906119958b6f16a7894c0671b18a7948f458a7787bf`.
Private paths, source identities, audio and per-case outputs remain outside Git.

## Fixed-threshold findings

| Development domain | Detected positives | Negative alerts | Negative groups alerted |
| --- | ---: | ---: | ---: |
| DEMAND/MAESTRO consumed transfer | 96/99 | 18/78 | 1/5 |
| MUSDB18-HQ consumed transfer | 41/41 | 1/42 | 1/5 |
| NSynth test sparse | 33/65 | 17/55 | 1/5 |
| NSynth train sparse | 25/31 | 17/33 | 3/5 |
| Private full-mix training | 60/71 | 0/63 | 0/5 |
| Public Tier A controlled | 62/74 | 0/65 | 0/5 |
| Total | 317/381 | 53/336 | 6/30 |

The case-level detection fraction was 83.2%; the benchmark-negative alert
fraction was 15.8%. Cases include related transformations and wrappers, so
these are not independent observations or population prevalence estimates.
All 30 positive groups had at least one detection, but that group-any result
does not erase missed recipes: only 2/24 requantized positives were detected.
Every domain had a positive median paired-score direction in all five groups.
This supports the presence of a signal, not a safe classification boundary.

The zero-negative-group-alert requirement failed in four of six domains.
Negative alerts included 35/215 reference cases and 18/121 processed hard
negatives. They were not confined to newly applied processing. In this small
selection, low-pass negatives had zero alerts (0/8); do not attribute all
failures to spectral cutoffs. Sparse-content failures and recipe sensitivity
remain visible rather than excluded to improve a headline result.

Codec-family classification was correct for 281/317 detected positives (88.6%),
or 281/381 across all positives (73.8% joint detection/family coverage). AAC is
a family label, not identification of a particular encoder implementation.
Bitrate accuracy remains unavailable: zero cases had measured comparable
source-bitrate truth. Neither family nor bitrate estimates are approved for
the public CLI by this result.

## Disposition

No threshold adjustment, source exclusion, retraining, rescue selection,
sealed-partition access or new independent-validation acquisition follows.
The two domains with no observed alerts are not promoted into a new product
population after seeing the results. Five groups per domain cannot establish
a low deployment false-positive rate even where no alerts occurred.

LossyTrace's release candidate will therefore provide documented, verdict-free
measurements and the preserved benchmark/research record. It will not ship
Lossprint weights or code, label files as lossy-derived or clean, estimate
historical codec/bitrate, certify never-lossy provenance, or judge audibility.
This completes the selected external-baseline screen, not the original
detector ambition and not the former perceptual-degradation research goal.
