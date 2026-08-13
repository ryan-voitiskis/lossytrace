# Stable speech-provider screen - 2026-08-14

**Status:** a bounded official-record search found one stable CC BY 4.0
direct-speech candidate. VibraVox removes the stable-only arithmetic dependence
on the mutable ICSI page for both three-domain coverage and four 120-group
partitions. This is a metadata-level capacity repair, not source selection or
scientific eligibility. No repository data object, Parquet content, audio
member, metric, score, listener response or sealed evidence was opened.

## Retained candidate

[VibraVox](https://vibravox.cnam.fr/) contains speech and physiological-sound
recordings from 188 participants. Its official paper documents simultaneous
capture through six sensors into a Zoom F8n at 48 kHz and 32 bits, with a
20 Hz acquisition high-pass filter. The airborne reference is a cardioid
headset microphone aimed toward the speaker's mouth and described as producing
a dry reference. The [dataset card](https://huggingface.co/datasets/Cnam-LMSSC/vibravox)
states that the six synchronized channels are mono PCM32 WAV and identifies
the clean speech field as `audio.headset_microphone`.

The dataset is CC BY 4.0. DOI `10.57967/hf/2727` cites revision `7990b7d`,
which resolves to the full content-addressed repository commit
[`7990b7df7153f5ba543ee89d9bbb65579c21d330`](https://huggingface.co/datasets/Cnam-LMSSC/vibravox/tree/7990b7df7153f5ba543ee89d9bbb65579c21d330).
That revision exposes content-addressed Parquet data objects, but none was
opened.

The conservative pre-audit grouping is one participant across every utterance,
subset, sensor and session, for a metadata-level ceiling of 188 groups. Only
the `speech_clean` subset and `audio.headset_microphone` field are candidate
material. The body-conduction fields and the `speech_noisy`,
`speechless_clean` and `speechless_noisy` subsets are excluded. Exact
participants, utterances, repository data objects, origin relationships and
delivered member integrity remain unaudited. Qualified and allocated counts
remain zero.

## Arithmetic consequence

The stable-only pool now has 17 providers and 2,238 candidate groups at
DataSTORRE's 67-recording ceiling, or 2,179 at its conservative eight-group
floor. Its non-Slakh capacity rises from 340 to 528 groups. The deterministic
provider-pure solver can therefore:

- place at least eight music, eight speech and eight natural-sound groups in
  each of development, calibration, transfer and final validation using only
  stable records; and
- fill all four partitions to 120 groups using only stable records, including
  at the conservative DataSTORRE floor.

The broader public-record pool now has 21 providers and 2,328 groups at the
recording ceiling, or 2,269 at the conservative floor. ICSI and the mutable
Bandcamp records may remain visible in that sensitivity, but they are no
longer required for the count or three-domain repairs.

This does not repair mastered music. AlbumDB remains the only stable
mastered-music candidate, so stable-only mastered-release coverage still
cannot span four provider-pure partitions. Public-record arithmetic can do so
only with the three mutable Bandcamp release records.

That was the state at this speech-screen checkpoint. The later
[`stable mastered-music provider screen`](perceptual-degradation-stable-mastered-music-provider-screen-20260814.md)
adds Solar Flux, the Lotte Lehmann historical album and Remnant Tamil Worship,
making stable-only mastered-release arithmetic feasible while leaving all
scientific and exact-member gates closed.

## Boundary and next decision

The repository commit makes VibraVox a stable exact-member metadata-audit
candidate; it does not prove that any exact member is eligible, independent,
lossless at origin, or suitable for the final truth-source design. Arithmetic
feasibility is not scientific feasibility.

No source or metric successor is selected. The screen does not authorize
preservation, exact-member inspection, repository data-object access, audio
acquisition, audio-member access, retained ODAQ access or projection, stimulus
generation, metric execution, scores, listener collection, sealed evidence,
no-reference training, or a public verdict. The responsible-human source
decision remains: authorize the bounded preservation and exact-member metadata
audit, or reject the current truth-source design.

Machine-readable artifacts:

- [`stable-speech observation`](../../research/toolchains/evidence/perceptual-degradation-stable-speech-provider-public-record-observation-20260814-001.json)
- [`validator`](../../scripts/validate_perceptual_degradation_stable_speech_provider_screen.py)
- updated [`breadth-repair plan`](../../benchmarks/perceptual-degradation-v1/breadth-repair-provider-allocation-feasibility-plan.json)
- updated [`deterministic report`](../../research/toolchains/evidence/perceptual-degradation-breadth-repair-provider-allocation-feasibility-20260814-001.json)
