# Perceptual-degradation listening protocol - 2026-08-03

**Status:** protocol draft frozen for software and power-analysis preparation;
recruitment, real-listener sessions, and collection of responses are not
authorized

This is a controlled research protocol for calibrating the full-reference
LossyTrace oracle. It is not a diagnostic or public-product test. It follows
the structure of BS.1116-style testing for subtle impairments and MUSHRA-style
testing for intermediate or severe impairments without claiming formal
laboratory compliance with either Recommendation.

## Research questions and boundaries

The study asks whether trained listeners, under declared playback conditions,
can hear a difference between a trusted clean reference and a controlled test
condition, and whether any audible difference is materially degrading. A test
condition may be an actual codec encode, a transparent encode, an artificial
artifact, or a matched non-codec control. Its recipe is hidden during rating.

The listening response is evidence about audibility and severity. It is never
evidence that an unknown waveform has a particular codec history. Transparent
lossy encodes remain non-degraded controls. ODAQ stimuli are development-only
simulated artifacts, not codec examples or final validation evidence.

## Participants

The target population is adults with critical-listening experience or a
documented training phase sufficient to use the scales consistently. Before a
main session, each participant must:

1. read the information and consent text;
2. self-report any hearing condition or temporary illness relevant to safe
   participation, without providing a diagnosis;
3. complete playback-chain, channel, lossless-delivery, and ambient-noise
   checks;
4. set a comfortable calibrated listening level that cannot be increased
   during scored trials; and
5. pass a training block covering hidden references, anchors, subtle codec
   artifacts, natural difficult negatives, and use of both scales.

No hearing-screen result is used as a medical conclusion. Failure of a
technical or training check leads to rescheduling or an unscored practice
session, not an adverse label on the participant.

## Playback requirements

The session manifest records a coarse playback class, not serial numbers or a
home address. The declared chain includes source device and operating system,
playback software version, DAC/interface class, amplifier if present,
headphone or loudspeaker model class, room/noise class, channel check, sample
rate, and level-calibration method.

Lossless stimuli are delivered at one frozen session sample rate and bit depth.
The player must decode locally, disable loudness normalization, spatial audio,
equalization, crossfade, communications ducking, and automatic gain control,
and verify byte-bound stimulus IDs before a scored block. Resampling by an
unbound operating-system path is unsupported. Loudspeaker sessions require a
documented quiet room and fixed listening position; otherwise headphones are
required.

Calibration uses a band-limited calibration signal and conservative level.
The listener is instructed never to raise the level to expose quiet artifacts.
They may lower it or stop at any time. The session stops for discomfort,
tinnitus, headache, fatigue that prevents careful judgment, playback faults,
or an uncontrolled interruption.

## Training

Training is separate from scored data and uses sources disjoint from final
validation. It explains that:

- the hidden reference may be presented among test candidates;
- a lossy condition can be indistinguishable from the reference;
- non-codec processing can be audible and should be rated on sound alone;
- the full scale should be used, without trying to identify a codec; and
- replay and switching are encouraged within the trial time limit.

Demonstration trials may provide correctness feedback for the forced choice.
The qualifying practice block does not identify anchor recipes or condition
families and provides no feedback that could carry into scored trials.

## Subtle block: BS.1116-style with pre-rating forced choice

Each trial contains a visible reference and two randomized candidates. One
candidate is a hidden copy of the reference and one is the controlled test.
The player uses instantaneous, click-free switching over the same loop and
level. Candidate labels and order are deterministically randomized per
pseudonymous assignment.

The listener first selects the candidate that differs more from the visible
reference. This response is locked before any grade can be entered. The
listener then assigns the selected test candidate a subjective difference
grade on the continuous scale from `0` (imperceptible) to `-4` (very annoying).
The interface does not reveal which candidate was the test, whether the choice
was correct, the condition recipe, or any metric score.

Trials use 4-12 second active excerpts. A session contains at most 15 scored
subtle trials, with a prompted break after at most eight. Trial order is
balanced across source group, condition family, severity stratum, and A/B
position. Every transparent or null condition receives the same replay budget
as an expected audible condition.

## Intermediate/severe block: MUSHRA-style

Each trial contains one visible reference, one hidden reference, required
low- and mid-quality anchors, and no more than eight additional randomized
conditions (12 signals total). The listener rates basic audio quality from
`0` (bad) to `100` (excellent). The hidden reference is rated like every other
candidate; the interface neither pins it to 100 nor reveals anchors.

Excerpts contain at least eight active seconds and are loopable without an
audible boundary. A session contains at most six scored MUSHRA-style trials,
with a break after at most three. Conditions are blocked so that derivatives
of a source do not leak across development, calibration, transfer, or final
validation partitions.

## Timing and response capture

A session targets 20-30 minutes including training and breaks. Each response
record contains only an opaque participant ID, opaque assignment and stimulus
IDs, randomized position, response, replay/switch counts, coarse client and
playback checks, and monotonic timing. It contains no filename, path, source
title, codec label, metric result, free-text identity, IP address, or precise
location.

The player must save a trial atomically and prevent post-submission edits.
Network retry may resend the same idempotency key but may not create a second
response. A participant may pause between trials. Incomplete sessions are
retained only under the consented policy and are never silently imputed.

## Prespecified exclusions and quality flags

Exclusions are applied without inspecting the participant's condition effects:

- consent absent or withdrawn;
- age or jurisdictional eligibility not satisfied;
- stimulus binding, channel, delivery, or fixed-level check failed;
- session software or manifest binding differs;
- the participant did not complete training;
- a session exceeded the frozen interruption or timing rule;
- duplicate participant/session evidence under the privacy-preserving rule;
- hidden-reference or anchor performance fails the threshold frozen by the
  power report; or
- response data are incomplete beyond the frozen per-method allowance.

The main analysis includes all non-excluded trials and models listener and
source effects. Sensitivity analyses report conclusions with and without
quality-flagged but technically valid listeners. Raw means are not ground
truth. Exclusion thresholds cannot be changed after condition outcomes are
opened.

## Analysis and stopping boundary

Audibility, equivalence, severity, bridge mapping, multiplicity, bootstrap,
coverage, and oracle pass criteria are those frozen in the main research
contract and machine plan. The power report must freeze participant counts,
repetitions, and quality thresholds before collection authorization.

Collection stops for a safety issue, privacy failure, stimulus or player hash
mismatch, broken randomization concealment, loss of the minimum disk reserve,
or any opening of sealed final evidence. Operational stoppage does not permit
threshold repair using observed outcomes.

## Authorization gate

This document alone does not authorize recruitment or data collection. A
later score-blind gate must bind the final protocol, participant information
and consent text, stimulus manifest, licences, player implementation and
synthetic dry run, playback qualification, power simulation, analysis code,
privacy controls, retention location, compensation plan, and responsible
human approval. Until then, every real-listener and recruitment flag remains
false.
