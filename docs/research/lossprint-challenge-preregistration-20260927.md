# Fixed Lossprint challenge execution — 2026-09-27

This prospectively binds execution of the existing
[first-challenge design](lossprint-first-challenge-design-20260927.md), not a
change to its selection or continuation rules. The user has authorized the
codec-history release-candidate goal, including this bounded development
challenge and the verdict-free fallback if detection is not defensible.

## Bound selection

The metadata-only selector retained five source groups in each of six domains:
717 cases, 693 exact-artifact representatives and 556 unique analysis PCM
identities. All matched negative references remain in the selected population.
Each artifact is scored twice, in fixed representative order: 1,386 slots.
All selected files satisfy documented rate/channel/duration support. Durations
are 3.0–12.505 seconds. No sealed partition, waveform or score was opened in
selection. Existing historical population limitations remain applicable.

The [public selection aggregate](../../research/baselines/lossprint/evidence/challenge-selection-20260927-001.json)
binds the private selection, historical manifests, selector, common module and
consumed design. Only file existence, containment and byte counts were checked
at selection; full artifact hashes must pass after the execution gates and
before inference. Exact aliasing follows the historical PCM/wrapper rule.

The first metadata-only invocation failed while constructing public counts
because some negative records omit codec fields. Its partial private selection
is retained. A regression-tested successor handles those absent fields and
produces the bound selection without changing ranking or membership. This was
not a scoring attempt or an observed-performance protocol amendment.

## Execution closure and limits

The machine-readable execution plan binds the runner/analyzer, qualified CLI
normalizer, selector, common module, all three prospective documents, saved
qualification and selection aggregates, and the local Python runtime. The
qualified source/model hashes and binary checksum are enforced again. The
exact execution commit and a successful completed run of this repository's
CI workflow are required before any waveform bytes are read, and are recorded
in private and sanitized public execution evidence. The checkout must be
clean, with unchanged bindings after execution.

Use the qualified native binary at threshold 0.5, one worker, one input per
invocation, JSONL output and two ordered replays. No decoding transformations,
model changes, retraining, retries, threshold changes or playback are allowed.
Keep all slots in the record, including failures and not-started slots. Each
call has a ten-second deadline; the batch has 45 minutes including input
identity preflight. Preserve 15 GiB free on the output volume and limit new
logs/scratch to 1 GiB. No derived audio is written. The verified binary emits
one bounded-size JSON record per input; cumulative scratch is checked before
each call. A technical failure stops further inference, leaving remaining
slots accounted as not started. Statistical failures do not stop the batch
early or change its fixed composition.

## Analysis and decision

Apply the original design's support, zero-negative-group-alert and
positive-group continuation rules unchanged. Report all-case counts, source
group counts and support separately, per domain and processing class. Exact
wrappers are consistency checks, not independent sources. Record family
accuracy conditional on detection and joint detection/family coverage, with
AAC interpreted as a family rather than a particular encoder. The fixed
binary-continuation rule does not approve family or bitrate claims.

The selected manifests contain codec settings but no measured comparable
source bitrates. Consequently bitrate accuracy is unavailable (zero eligible
cases); do not substitute nominal settings or infer truth from predictions.
Pair comparisons use exact matched references, deduplicate PCM pairs within
source groups, and report group-median score direction. They cannot promote
a failed binary screen. Timing and machine-generated metadata are separate
from exact repeated prediction records.

A pass supports only preparation of independently sourced validation, not
release of a detector. A failure is preserved without retuning or rescue
selection. Under the user's release-candidate goal, it leads to the explicitly
verdict-free inspector-and-benchmark RC unless an independent technical audit
shows that execution, rather than the model, prevented an interpretable screen.
Any such execution correction requires a new prospective record; a consumed
failed run is never replaced. No codec-history accuracy claim follows from
this development population, unknown external training overlap, or software
qualification alone.
