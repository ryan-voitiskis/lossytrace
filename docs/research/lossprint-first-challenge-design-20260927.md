# Lossprint first challenge design — 2026-09-27

Status: prospective selection and analysis design after the
[software qualification](lossprint-qualification-result-20260927.md).
No source selection has yet been executed and no real-audio scores exist for
this successor. This is not an executable frozen run: private identities,
case counts, duration checks and runner bindings remain to be established.

## Question and population

Does the fixed published Lossprint baseline avoid the content/processing
shortcuts that defeated earlier detectors on our consumed development
population, while detecting a useful fraction of its controlled positives?

This is a falsification-oriented external-baseline screen, not independent
validation, not a rerun of a rejected LossyTrace model, and not an estimate of
error prevalence in music libraries. All old results and gates remain intact.
The private training set of the external model creates unresolved overlap
risk; we cannot claim independent source or encoder transfer.

Use only `mechanism_development` cases from the existing v2 analysis manifest
and its matching constructor manifest. The public baseline plan binds them as:

- Analysis manifest SHA-256:
  `0937dfec3f9d5d203ec3d8c1700a3ae947226999e72a379b226c4c825fab96f9`.
- Constructor manifest SHA-256:
  `0fe9bde6eed57a61d3c721d5bfd8cd36031b9981442c39dc502162aeeab3a1b1`.

No new metric/human labels, provider downloads, codec generation or sealed
partition access is part of this first screen. Existing analysis artifacts
are the evaluated inputs; any historical downmixing or canonicalization is
part of that declared population, not a native-stereo validation of Lossprint.

## Metadata-only selection, before waveform access

Use all six domain identifiers from the frozen development baseline plan.
Within each domain rank the canonical source-group strings by the hexadecimal
SHA-256 of UTF-8 `lossprint-first-challenge-20260927:` followed by that string,
breaking a hash tie lexicographically. Select the first five groups per domain.
If any domain has fewer than five eligible groups, stop rather than substitute
groups or change the rule. Selection is 30 group/domain entries, not a claim
that historical domain labels alone establish independent recording lineages.

Retain every mechanism-development case in those groups, both labels, every
post-processing variant and every wrapper. Use the existing exact-artifact
deduplication rule for execution and retain aliases in accounting. Retain
matched references for paired comparisons; stop at metadata preflight if one
falls outside the selected group population or cannot be resolved. Never
discard a case for a previous detector's score or because Lossprint may fail.

Resolve relocated artifact paths against the verified external-volume mapping;
validate containment and stored identity before scoring, rather than rewriting
the historical manifests. Persist private exact identities and the sanitized
domain/label/transform counts before any model output. Freeze their hashes.

The first-run cap is 1,200 unique artifact files. If this selection exceeds
that cap, stop for a separately documented pre-observation design amendment;
do not truncate within groups. Check that declared input support and codec
labels can be represented without changing model or decoder behaviour.

## Execution and accounting to bind

Use the software-qualified model and binary unchanged, one worker, exact input
files, two ordered replays, the upstream threshold of 0.5, and no retries.
Keep decoded samples in process; retain no new derived audio. Proposed resource
limits are 10 seconds per file, 45 minutes total scoring time, at most 1 GiB of
new logs/scratch, and 15 GiB free reserve. A tested successor runner must enforce
these limits and preserve failed and not-started slots before the proposal is
ready. Synthetic qualification timings are not a throughput guarantee.

Before waveform access require a prospectively bound selection, runner,
analyzer, exact external binary/model, tool/runtime closure and successful
CI for the exact LossyTrace execution head. A failure stops this batch; it
does not authorize a new threshold or a different external model.

## Fixed analysis and continuation rule

Report binary detection separately for each source domain, label and declared
processing class. Include case-level and source-group false alerts, supported
recall, unconditional detected/total-positive coverage, technical failures,
abstentions, exact-wrapper consistency and non-timing replay equality.
Include paired score changes relative to each exact reference, deduplicating
equal PCM pairs rather than treating wrappers as independent observations.

A positive source group is supported only when all its selected positive
artifacts and matched references produce valid outputs. A negative source
group is supported only when all its selected negative artifacts produce
valid outputs. Report partially supported groups separately, retaining every
case in unconditional denominators. Any observed negative alert counts toward
the false-alert stopping rule, including alerts in partially supported groups.

At this small first-screen size, the conservative continuation rule is:

- every planned execution is either a supported result or a prospectively
  declared unsupported state; no crash, timeout or unexplained missing case;
- exact replay and wrapper-consistency checks pass;
- zero negative source groups receive any observed alert in every domain;
- at least 75% of positive source groups in every domain are supported; and
- at least 80% of supported positive source groups in every domain have at
  least one detected controlled positive. Report this group-any measure
  explicitly alongside all positive case and recipe results; it is not
  per-codec recall, a substitute for weak-recipe results, or a release gate.

A domain with no positive or negative groups makes the screen insufficient,
not passed. If the screen fails, preserve the failure and its scope without
retuning. If it passes, only a larger, independently sourced validation design
becomes worth considering. Zero alerts among so few groups cannot establish a
low population false-positive rate or calibrated probabilities.

Normalize `ffmpeg_aac` to the AAC family for comparison, preserving the raw
field privately. Do not score it as identification of the FFmpeg encoder.
Report family accuracy conditional on detection and joint detection-plus-
correct-family coverage over all supported positives. Unknown codec truth
remains unknown rather than inferred from the model.

Report bitrate error only when matching metadata supplies an actual comparable
bitrate; do not translate Vorbis quality values or nominal VBR settings into
measured bitrates. State the fraction eligible and detected, conditional error
and misses. The upstream CLI's rounding and conditional suppression stay
visible. This first screen does not certify encoder identification, bitrate
recovery, full-track coverage, audibility, quality or never-lossy provenance.
