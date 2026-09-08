# Bounded native digital canary proposal

State: prepared for explicit execution approval, not executed and not real-audio
execution authorization.

The [machine-readable proposal](../../benchmarks/perceptual-degradation-v1/digital-canary-proposal-20260908.json)
binds the [new runner](../../scripts/perceptual_degradation_digital_canary.py),
its constructed-only tests, the unchanged digital recipes and the qualified v4
native alignment implementation. Consumed studies, code and negative results
remain unchanged. This is a plumbing and feasibility test, not an experiment
measuring perceived degradation.

## Why this next step

The [native synthetic qualification](perceptual-degradation-alignment-native-qualification-20260908.md)
completed a full-size identity in approximately 118 seconds. It did not execute
a codec or establish real-source throughput. Repeating the old 160-case replay
would conditionally cost about 5.2 hours before codec work; the old one-hour
cutoff is unsuitable. First test the complete pipeline at a small fixed scope.

The canary selects one full-length reference from the existing hash-bound
16-member delivery metadata: largest declared frame count, breaking ties by
ascending opaque delivery ID. This selects the declared maximum 576,008-frame
geometry at stereo 48 kHz, without inspecting waveforms to choose an easy case.
The complete metadata inventory and attribution are checked, but only the
selected waveform is opened, hashed and parsed. The other 15 waveforms are not
opened, encoded or claimed to have passed fresh waveform-integrity validation.
There is no crop, substitution, listening-based selection or new acquisition.

This is intentionally a duration stress case, not a representative sample.
Its bit depth, source traits, difficulty and independence are not inferred from
its duration. It cannot validate the full cohort, both integer bit depths,
domain transfer, transparent coding or an unseen encoder lineage. All four
codec families were already allocated to development.

## Exact case inventory

Each of two replays executes these six conditions in this order:

| Condition | Bound operating point |
| --- | --- |
| Identity | Original signed-integer PCM versus itself |
| Input adapter | Original PCM versus its explicit float32 adapter |
| MP3 | FFmpeg libmp3lame, 128 kbit/s |
| AAC-LC | Native FFmpeg AAC, 128 kbit/s |
| Opus | FFmpeg libopus, 128 kbit/s hard CBR, 20 ms frames |
| Vorbis | oggenc, quality 6 |

The exact recipe IDs, argument arrays, decoder choices and packet inspection
fields are inherited byte-for-byte from the frozen digital proposal. Codec
comparisons use the adapted input as reference, keeping adapter error separate.
Decoded values above full scale are preserved. Packet timestamps and skip/discard
metadata are observations, not manually applied alignment corrections.

There are 12 planned comparisons and at most eight encode/decode pairs, using
one worker and one invocation of this successor. The two prescribed replays
are the complete authorization request, not permission for subsequent reruns.
Failed, unsupported and not-started cases remain visible in the denominator.

## Runtime and stop conditions

The conditional estimate is 1,416 seconds, about 24 minutes, if every comparison
costs the observed synthetic 118 seconds. This is not measured codec throughput
or a completion guarantee. Source content can change alignment runtime/support.

The existing 60-second command and 180-second case budgets are unchanged. Each
replay stops starting cases after 1,200 seconds. The current case, preflight,
filesystem and report-writing overhead are additional; there is no claimed hard
40-minute whole-process deadline. A resource/time stop ends further case starts
and prevents the second replay from restarting the study. Individual failed
cases are retained; later fixed cases may still execute within the same budget.

Execution requires 15 GiB free plus 384 MiB bounded scratch allowance. No cleanup,
reserve reduction, extra worker, automatic retry or threshold change is allowed.
Disk availability must be checked live, not inferred from this preparation date.

## Evidence and native binding

The v4 backend retains the qualified exhaustive lag inventory, numerical method,
four/eight-second duration rules, aligned-frame geometry cap, channel checks and
two-second maximum delay. It is explicitly activated for each comparison, with
its counters reset and the global backend restored even after an alignment
timeout. Ordinary tests do not execute the full-size case or a real codec.

Before private path inspection, the runner requires isolated Python, the exact
new authorization, a clean committed checkout and successful push CI for that
exact execution head. The consumed old authorization is not accepted. Installed
codec/dependency/runtime bindings and the qualified compiler/source/flags/platform
must match. A newly built native binary is hashed and checked on activation.
Its binary hash need not equal the prior binary: the platform embeds the private
build location in the library identity. Compiler dependency closure and binary
reproducibility across build directories are not claimed.

Bindings, attribution, selected-source metadata, selected waveform integrity,
native binary and free-space reserve are checked before and after each replay.
A failed edge check preserves observed evidence, marks the run incomplete and
prevents further replays; it does not authorize repair or replacement.

Private reports retain exact source/adapter/encoded/decoded hashes, input and
packet geometry, complete alignment records, native candidate/search counts,
failures and timing. Deterministic repeatability compares canonical replay bytes
after excluding exactly each case's `timing_seconds` field. It does not exclude
hashes, reasons, support/nulls, numerical alignment or native counters. Whole
private reports containing measured timing need not be byte-identical. Timeout
progress counts may legitimately fail the deterministic-repeatability check;
that result is retained, not rerun until it matches.

The path-free aggregate separates computational completion, repeatability,
edge-check success, control support, codec support and native fallback. An
observed but unsupported alignment is not a usable perceptual comparison.
Computational completion is not a scientific validation verdict.

Only a unique private directory is retained: execution binding, attribution,
two replay reports, a path-free projection and the native library in its own
subdirectory. Owned temporary codec/decoded scratch is removed after each case;
no derived PCM is retained. An independent saved-artifact audit is required
before any observed aggregate is published. No private paths, member IDs,
per-member hashes, packet records or real audio enter the public repository.

## Remaining authority and scientific gates

Local preparation checks: 29 focused tests pass, as do Rust formatting, Clippy
and all-target tests. The complete Python suite passes with 1,599 tests and
14 skips. The publication audit found no new private paths, media, credentials
or binaries; two generated SBOMs are identical.

The first local suite encountered existing 15 GiB reserve guards. Validation
then moved to a byte-verified external-volume checkout, with temporary and build
files on that volume. An initially shallow public checkout lacked two required
historical Git bindings; fetching the complete public history resolved those
errors. The complete suite was rerun successfully. No research implementation,
threshold, consumed result or reserve guard was changed to obtain that pass.

The new fixed `digital-canary-authorization.json` is absent at this preparation
checkpoint. A fresh responsible-user approval of this exact scope is required,
followed by a committed hash-bound authorization and exact-execution-head CI.
No sound card, microphone, loopback, room qualification, playback, spending,
outreach or installation is required by this canary.

Perceptual metrics, listening, human collection, trait assignment, source-group
independence, training and public verdicts remain closed. Severity, audibility,
artifact profile and transparency stay null. The broader research objective is
incomplete, regardless of this canary's eventual technical outcome.
