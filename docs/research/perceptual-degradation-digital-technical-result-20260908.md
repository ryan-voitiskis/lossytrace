# Digital technical replay result: reproducible runtime failure

Date: 2026-09-08. This is an engineering result, not a perceptual result or a
final disposition of the LossyTrace research objective.

The [approved proposal](perceptual-degradation-digital-execution-proposal-20260908.md)
ran once, producing its two authorized replay reports. Each replay retained all
160 planned cases in its accounting. The reports are byte-identical, but no
alignment comparison completed. The [aggregate evidence](../../research/toolchains/evidence/perceptual-degradation-digital-technical-20260908-001.json)
preserves the full denominator and unavailable perceptual fields.

| Outcome | Replay 1 | Replay 2 |
| --- | ---: | ---: |
| Planned cases | 160 | 160 |
| Attempted, timed out during alignment | 20 | 20 |
| Not started after the one-hour cutoff | 140 | 140 |
| Complete comparisons | 0 | 0 |
| Codec encode/decode pairs reaching alignment | 16 | 16 |
| Controls reaching alignment, then timing out | 4 | 4 |

The fixed source-major order attempted two of the sixteen sources, with all ten
conditions for each. These are repeated attempts on the same two sources, not
forty independent observations. Across both replays, 40 attempted slots timed
out and 280 slots were not started. No cases were substituted or resumed.

## What the result establishes

The observed failure code is `alignment_timeout`: the 180-second case deadline
expired inside alignment. It does not identify the exact internal hotspot.
Even the identity and float32-adapter controls timed out. This cannot be read
as evidence that the source audio, codec conditions or perceptual-estimation
objective failed a scientific quality gate.

The sixteen attempted codec/source pairs completed encoding, probing and decoding
in each replay. Their retained hashes and packet records match across the actual
report bytes. That is limited evidence of repeatable codec processing on the
attempted subset, not validation of all 128 planned codec/source pairs or their
perceptual quality. No completed alignment, gain, duration-support or oracle
comparison can be recovered from these timeout records.

Zero support/eligibility counters and empty alignment-reason maps mean there
were no completed comparisons to populate them. They are not zero impairment
scores or measured scientific rejections. Severity, audibility, artifact profile
and transparency remain unavailable. The runner's zero exit code means it
successfully wrote the bounded result, not that comparisons passed.

## Runtime assumption that failed

The preparation suite established many correctness and fail-closed boundaries,
but did not establish full-duration 48 kHz throughput. Its real native-rate PCM
fixtures contain only 32-47 frames; the complete replay tests mock codecs and
alignment. The longer alignment-validity regression uses 2 kHz. Successful CI
therefore did not answer the runtime question this experiment needed answered.

Static inspection of the unchanged alignment v3 implementation suggests a
computational bottleneck. Its structural audit searches every integer lag in
seven windows per channel. At 48 kHz, a full half-second window and a +/-0.10-second
radius imply 9,601 candidate lags and 24,000 sample pairs per correlation. For
stereo, that is 134,414 correlations, or about 3.23 billion sample-pair evaluations
for this audit alone, conditional on evaluating all full windows and lags.

This is a code-derived work estimate, not profiling evidence or a claim about
how many operations these timed-out cases actually completed. No internal
timing instrumentation or extra real-data experiment was added after observation.

## Integrity, privacy and publication boundary

Execution used commit `804e10a455c4facf0c5f85cc6a2ece371f98b343`, after its
[exact-head push CI](https://github.com/ryan-voitiskis/lossytrace/actions/runs/34138056332)
passed: 1,502 Python tests with 14 skips, plus Rust checks. This is the execution
head, not the later report-publication head.

A separate read-only audit reconstructed the allowlisted aggregate from the
private case records without invoking the runner's summarizer. It verified
the bound source/recipe identities and order, unique case IDs, complete
denominators, source hashes and input geometry, unavailable comparisons,
control/codec stage fields, actual replay-byte equality and unchanged first
report bytes. The reconstructed public projection matched exactly.

All sixteen retained source files still match the frozen delivery inventory
(54,631,346 bytes). The new private run directory contains exactly the five
planned JSON files, with 0600 file and 0700 directory permissions. No case
scratch, encoded condition, input adapter or decoded PCM remains there. Only
the runner's own temporary case data was removed; retained sources and reports
were preserved. No private paths, case/source identities, per-member hashes or
packet records are published here.

The exact native binary/dependency/runtime binding matched before and after the
run. Those are edge checks, not continuous attestation; system-cache libraries
remain bound to the recorded OS build rather than individual file hashes.
Execution used one worker and the frozen disk-reserve and time limits. There
was no playback, sound-card change, room test, capture, metric execution,
listener collection, training, outreach or spending.

## Next research step

Qualify full-duration, native-48-kHz alignment runtime on constructed signals
before proposing another real replay. A separately versioned synthetic-only
successor should preserve invalid-correlation nulls, topology checks, full
candidate coverage and frozen thresholds, and test runtime at the actual
intended shape. Any optimization must demonstrate semantic equivalence;
raising deadlines or silently narrowing searches is not a repair of this result.

This engineering bottleneck is not evidence against perceptual estimation.
The retained cohort remains consumed, one-provider development evidence;
unstarted cases are not promoted to fresh validation. Missing source traits,
controlled human truth, metric approval, full-reference calibration and
independent transfer remain necessary for the broader objective. The public
CLI stays verdict-free.

The two-replay authorization is consumed. The historical authorization, proposal,
runner, thresholds and prior negative reports remain unchanged. No third real
replay, automatic repair or automatic rerun is authorized by this checkpoint.
