# ViSQOL-only successor readiness - 2026-08-14

**Status:** a score-blind ViSQOL-only full-reference successor is technically
preregisterable, but it is not selected, scientifically ready, or authorized
to execute. This checkpoint opened no audio or metric/listening outcome.

## Outcome

ViSQOL is the only currently preregisterable metric successor among the three
frozen choices after the GstPEAQ proxy stop. The official repository remains
active under Apache-2.0, and the frozen `v3.3.3` tag still resolves to commit
`c3aa2e498e0f7f14202643594335a0b9ee40bdd9`. The project has moved 18 commits
beyond that release, so the successor must preserve the exact release and
model rather than silently following `master`.

The existing synthetic evidence is sufficient for a technical preparation
gate: four fixtures replayed with zero numeric delta in two different Linux,
compiler, Python, and NumPy environments. The binaries differ by environment,
but the exact frozen model and outputs agree. That is evidence of deterministic
synthetic behavior, not evidence of perceptual validity.

## Scientific boundary

The official ViSQOL guidance materially narrows the claim:

- audio mode expects 48 kHz input and downmixes multi-channel input to mono;
- a raw MOS-LQO or similarity output is not a LossyTrace audibility
  probability, materiality label, or severity scale;
- single scores are not meaningful treatment conclusions; aggregation across
  samples with the same treatment is recommended;
- model training requires subjective scores;
- the supplied audio model was trained on full-band material down to 24 kbps,
  may behave poorly below that, and can perform poorly outside codec/VoIP
  degradations; and
- per-patch and per-frequency similarities are diagnostics, not
  human-calibrated artifact truth.

The mono downmix makes a ViSQOL-only stereo-image or phase conclusion
impossible. Every artifact-profile component therefore remains `null` until a
separate feature-to-human-artifact calibration passes; stereo remains `null`
from ViSQOL by construction.

## Required successor amendment

A responsible-human selection would authorize preparation of a new score-blind
plan and schema, not metric execution. That amendment must be committed before
retained or human metric outcomes are opened and must:

1. preserve ViSQOL `v3.3.3`, its exact commit, model hash, audio mode, and
   48 kHz view;
2. report mono downmix and forbid ViSQOL-only stereo conclusions;
3. treat MOS-LQO and similarity values as unmapped features until controlled
   human calibration establishes severity, audibility, and materiality;
4. aggregate by treatment and source group and preregister strata or abstention
   for below-24-kbps, excessive-silence, out-of-domain, alignment, and stereo
   cases;
5. replace the predecessor schema's exactly-two-family contract rather than
   silently editing it;
6. remove the GstPEAQ family while retaining raw ViSQOL and deterministic
   signal-distance baselines for added-value evaluation;
7. preserve transparent-lossy negatives, hard natural/production negatives,
   grouped source/domain/codec/encoder holdouts, and explicit uncertainty and
   abstention; and
8. leave the public CLI verdict-free.

## Rights and execution boundary

The official source and model are supplied under Apache-2.0, and no separate
BS.1387-style consent gate was observed in the official ViSQOL record. That is
enough to keep an internal-research candidate available; it is not legal
advice, does not complete dependency/SBOM or redistribution review, and does
not authorize execution.

No metric successor or source successor is selected. The current two-family
gate remains closed. Retained ODAQ access, any new source acquisition, metric
execution, scores, listener collection, sealed evidence, no-reference work,
and public verdicts remain closed.

Machine-readable artifacts:

- [`current official-record observation`](../../research/toolchains/evidence/perceptual-degradation-visqol-current-public-readiness-observation-20260814-001.json)
- [`successor-readiness disposition`](../../benchmarks/perceptual-degradation-v1/visqol-only-successor-readiness-disposition.json)
- [`validator`](../../scripts/validate-perceptual-degradation-visqol-only-successor-readiness.py)
