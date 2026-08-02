# Factorial benchmark v2 factor-level freeze

Date: 2026-08-02

State: factor levels frozen before toolchain binding and cell assignment; no
benchmark audio, mechanism score, or unopened label inspected

## Purpose

This checkpoint fixes what the v2 benchmark may vary without yet deciding
which source group receives each fractional-factorial cell. It binds the
replayed 793-group source allocation at commit
`7f73bbb0c04e5930a2539b0eac75f9d42daac64a` and separates three decisions:

1. this record fixes scientific factor levels and coverage;
2. the next record must bind exact binaries, commands, linked libraries, and
   golden outputs; and
3. a later record must assign private source groups to cells without using
   waveform statistics or scores.

The machine-readable freeze is
[`factor-levels.json`](../../benchmarks/audio-integrity-v2/factor-levels.json),
SHA-256
`c64f74ee48cbf9d626cba00cb55b139ecc1e4d206daa2e0fc94ec0af45991fab`.
It is checked by
`scripts/validate-audio-integrity-v2-factor-levels.py` and mandatory synthetic
tests.

## Reference excerpts and matched pairs

Every selected member contributes at most 12 seconds. A source shorter than
12 seconds remains complete: it is not looped, padded, stretched, silence
trimmed, or rejected. For longer sources, a domain-separated hash of the
already-frozen private group and member IDs chooses an integer native-frame
offset. RWC's bound provider start/end window takes precedence over the full
file. No waveform content chooses the crop.

Every H1 codec case has an H0 reference with the same source member, crop,
target sample rate, channel treatment, signed-16-bit conversion, and any
declared robustness transform. This is essential: a resampled or gain-shifted
positive cannot be compared only with an untransformed negative.

The two channel treatments are defined for every mono or stereo source:

- mono is identity for mono input and the arithmetic mean of stereo channels;
- stereo is identity for stereo input and exact dual-mono duplication for mono
  input.

No loudness or peak normalization, silence removal, or data-dependent channel
choice is permitted. Inputs outside one or two channels stop construction.

Natural duration remains a support factor. The frozen strata are under 1
second, 1–3 seconds, 3–6 seconds, and 6–12 seconds. A short or sparse negative
may be unsupported by a later representation, but any alert on it still counts
in safety reporting.

## Codec and encoder levels

Each setting template expands deterministically to mono and stereo concrete
settings. The freeze contains 16 development templates (32 expanded settings)
and 8 encoder-transfer templates (16 expanded settings):

| Codec | Mechanism development | Encoder transfer |
| --- | --- | --- |
| MP3 | LAME CBR 96/128, explicit 16 kHz low-pass at CBR 128, VBR V2; Shine CBR 128 | BladeEnc CBR 96/128 |
| AAC-LC | FFmpeg native CBR 96/128 and explicit 16 kHz cutoff; Apple AudioToolbox CBR 128 | Fraunhofer FDK CBR 96/128 |
| Opus | libopus hard-CBR 64/96/128 at 20 ms and 96 at 10 ms | FFmpeg native 64/96 |
| Vorbis | libvorbis q2/q4/q6 | FFmpeg native q2/q4 |

Each codec has exactly one anchor per observed partition: MP3 128 kbit/s,
AAC-LC 128 kbit/s, Opus 96 kbit/s at 20 ms, and Vorbis q4. Development and
encoder-transfer lineages are disjoint by construction. Encoder defaults and
explicit cutoff settings are distinct factors; an observed cutoff must be
recorded later rather than inferred from the nominal command.

The exact external-transfer encoder is deliberately not selected. If a
mechanism survives both observed gates, external transfer requires a newly
bound MP3 lineage disjoint from LAME, Shine, and BladeEnc, with an obvious
128-kbit/s setting. Failure to obtain one is a stop-and-ask boundary, not
permission to reuse a seen lineage or silently substitute a codec.

## Decoder and transform levels

History decoding crosses a common FFmpeg path, Apple AudioToolbox, and the
available codec-specific paths: mpg123 for MP3, opusdec for Opus, and oggdec
for Vorbis. The exact final lossless-wrapper analysis decoder is named but left
for the toolchain freeze, which must also show equivalence with the public
decoder before baseline scoring.

Nine non-codec PCM hard-negative classes are frozen, one at a time:

1. fixed-point −6 dB gain;
2. 250 ms head trim;
3. 500 ms prepended digital silence;
4. a 3-second duration prefix;
5. cascaded 16 kHz low-pass filtering;
6. a 32 kHz resampling round trip;
7. deterministic 12-bit TPDF requantization;
8. alternate mono/stereo topology; and
9. exact-PCM lossless-wrapper rewriting.

Each transform is also eligible as a matched H0/H1 robustness pair. No case may
combine two nonidentity PCM transforms. FLAC is the primary wrapper; WAV and
AIFF are exact-decoded-PCM invariance levels.

## Coverage before opening a partition

All 527 development groups and 102 encoder-transfer groups receive reference
cases and one anchor positive per codec. Every nonanchor development setting
must cover at least 120 groups across at least five source domains; the
encoder-transfer requirement is 60 groups across at least four domains.

Each hard-negative transform covers at least 40 development groups and 20
encoder-transfer groups and must appear in matched positive pairs for all four
codec families. Every setting template crosses both channel treatments, while
each compatible history decoder crosses at least two templates per codec.
The external partition retains 164 references, at least 150 Tier A negative
groups, at least 20 groups per hard-negative class, and—only after a
survivor—at least 100 controlled MP3-positive groups.

The later assignment must show that expectation is not confounded with source
domain, encoder, setting, decoder, channel treatment, or transform. It may use
only frozen identities and categorical factors, never audio statistics or
candidate scores.

## Storage and reproducibility boundary

Construction remains single-worker and low-priority. The 15 GiB free-space
reserve is a hard stop, with no more than two uncompressed case files live at
once and no source-archive duplication. Lossy bitstreams and lossless
derivatives may be deleted after recipes, hashes, required measurements, and
partition state are sealed; every deleted derivative must be reproducible from
the retained provider archive and private allocation.

This ephemeral design is necessary because retaining a conventional Cartesian
audio corpus would violate the reserve. It does not authorize scoring a sealed
partition during construction. Encoder-transfer and external-transfer
measurements remain unopened until their respective gates.

## Next gate

Probe every frozen setting and transform on deterministic synthetic fixtures,
then freeze exact commands, binary and linked-library hashes, observed
bitstream properties, decoder alignment, resampler/filter behavior, and golden
output hashes. An unsupported factor requires a dated correction before any
benchmark generation. Silent substitution is prohibited.
