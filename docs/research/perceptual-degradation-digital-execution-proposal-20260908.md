# ODAQ16 digital execution proposal — 2026-09-08

The first digital technical study is now specified and implemented, but **real
execution still needs approval**. Nothing has been recorded, played, newly
encoded, measured with a perceptual metric or collected from listeners in this
checkpoint. The retained audio and private manifests have not been reopened.

The [exact machine-readable proposal](../../benchmarks/perceptual-degradation-v1/digital-development-execution-proposal-20260908.json)
implements the approved digital-first amendment. It does not resume the older
capture-first sequence or rewrite its findings.

## Exact proposed work

Use one existing canonical delivery of all 16 retained ODAQ references, stereo
at 48 kHz. Keep the complete cohort development-only and colocated. Reverify its
exact inventory, every file, PCM geometry and attached attribution before each
private replay. A mismatch stops that replay; it never triggers substitution.

| Family | Encoder | Selected operating points |
|---|---|---|
| MP3 | LAME 4.0 through FFmpeg | 96 and 128 kbps CBR |
| AAC-LC | FFmpeg 9.0.1 native AAC | 96 and 128 kbps target bitrate |
| Opus | libopus 1.6.1 through FFmpeg | 64 and 128 kbps hard CBR, 20 ms frames |
| Vorbis | libVorbis 1.3.7 through oggenc 1.4.3 | Quality 2 and 6 |

There are eight codec conditions plus two controls per source: **160 comparisons
per replay, 320 across two replays**. This means 128 encode/decode operations per
replay, not 160 different encodes. These settings span development interventions;
they are not labels for severity, audibility or transparency.

All four codec lineages are used for technical development here. No family is
reserved as an unseen-codec validation set by this proposal. Later transfer
design must explicitly account for prior exposure; holding out different files
does not make a previously used family unseen. The FFmpeg **libopus** wrapper is
also distinct from the earlier **native FFmpeg Opus** transfer candidate.

## Keep the comparison interpretable

The retained 24/32-bit integer samples are represented exactly in float64, then
converted to a common float32 encoder-input view. The two controls are:

1. Retained reference versus itself.
2. Retained reference versus its float32 input view.

Every decoded codec condition is compared against the exact float32 view sent
to its encoder. Binary32 rounding can alter a 32-bit input, including rounding a
value just below full scale to 1.0; the adapter control exposes this. No clipping,
normalization, dither, resampling or gain/polarity correction is added.

Each decoder is explicit and exports float64 without integer-output clipping.
The runner records selected packet timestamps, skip/discard metadata, stream
geometry and decoded length. The bound decoder handles its container semantics;
the runner adds no manual trim or delay correction. The existing validity-aware
alignment implementation supplies diagnostics without changing samples.

The four/eight-active-second requirements are unchanged. Quality-duration
eligibility adds the eight-second requirement to the same supported alignment;
it does not execute or validate a metric. The older block-based activity
diagnostic can round a partial block upward, so the study caps its eligibility
duration at the actual aligned frame count. It preserves the raw diagnostic and
records whether that cap applied. One frame below either duration limit cannot
pass by block rounding. Every failed, short, silent, ambiguous
or otherwise unsupported case remains in the accounting. A correlation-based
support failure may itself depend on degradation, so coverage is not ignorable.

## Bounded execution and provenance

The [native binding](../../research/toolchains/evidence/perceptual-degradation-digital-native-tools-20260908-001.json)
records 107 executable/shared-library nodes from 20 installed packages, their
dependency relationships, package licence declarations and available licence
notice hashes. It also binds 798 Python standard-library source/extension files.
System-cache libraries are bound to macOS 26.6.2 build 25G83 arm64, not represented
as individually file-hashed or cross-platform-equivalent components.

The [runner](../../scripts/perceptual_degradation_digital_development.py) uses one
worker and a controlled subprocess environment. Before each case it requires
15 GiB free plus a 384 MiB scratch allowance. Subprocess outputs are capped at
32 MiB each; codec/probe commands have at most 60 seconds within a 180-second
case deadline. It stops starting cases after one hour per replay and records
the remaining cases as `not_run`. An in-flight case and preflight/runtime
overhead are additional to that one-hour cutoff.

Only fresh private temporary case directories are cleaned up. Encoded audio,
input adapters and decoded PCM are not retained. Two private JSON replay reports,
execution binding, attribution and a path-free aggregate projection remain in a
new unique private directory. Sources are never rewritten. No tool installation,
redistribution, outreach, spending or listening-delivery retention is included.

The two reports compare actual encoded/decoded hashes, selected packet metadata
and comparison evidence. Byte mismatch, unsupported cases or time/resource
limits remain visible. Bitexact flags and mocked tests do not guarantee a real
codec run will succeed or reproduce; that is what the proposed study will test.

## What has been tested, and what needs approval

Constructed 24/32-bit PCM fixtures test parsing, conversion, corruption, symlink
and extra-file rejection, protected writes, deadlines and complete accounting.
Two complete mocked codec-boundary replays cover all 320 planned cases without
invoking a codec. A small actual numerical alignment test abstains on insufficient
support. These are software tests, not observations about the retained audio.

The live command first requires a separately committed user-approval record
binding this exact proposal and runner. It then checks a clean checkout,
successful push CI for that exact HEAD, isolated Python mode and exact native
tool/runtime equality **before inspecting private paths**. No approval record
has been created by this preparation checkpoint.

The requested next approval is only: **run these two private 160-case technical
replays on the existing retained delivery cohort**. Metric execution, playback,
listener collection, source-trait assignment, training and public verdicts remain
closed. The broader research objective is still incomplete.

Command design was checked against installed tool help and the primary
[FFmpeg codec documentation](https://ffmpeg.org/ffmpeg-codecs.html),
[format documentation](https://ffmpeg.org/ffmpeg-formats.html) and
[Xiph oggenc manual](https://github.com/xiph/vorbis-tools/blob/main/oggenc/man/oggenc.1).
