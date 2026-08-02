# Factorial benchmark source and toolchain inventory - 2026-08-02

**Status:** inventory only; no source allocation, encoder, version, setting, or
identity is frozen

**Actions so far:** local tools inspected and synthetically probed, provider
metadata reviewed, Lombard Grid source identity acquired and audited, no
benchmark audio generated, no score opened, and no candidate selected

The machine-readable inventory is
[`benchmarks/audio-integrity-v2/inventory.json`](../../benchmarks/audio-integrity-v2/inventory.json).
Its validator checks encoder-lineage disjointness and recomputes conservative
partition/domain totals. Passing it means that the proposal is internally
consistent; it does not turn provider descriptions into verified local source
counts or authorize acquisition, generation, or score opening.

## Lineage accounting

The important unit is the codec implementation, not the command used to call
it. The following aliases therefore count once:

- LAME CLI and FFmpeg `libmp3lame` are one LAME lineage;
- FFmpeg `aac_at` and `afconvert` are frontends to one Apple AudioToolbox AAC
  lineage;
- FFmpeg `libopus` and `opusenc` use the Xiph libopus reference lineage; and
- FFmpeg `libvorbis` and `oggenc` use the Xiph libvorbis reference lineage.

A historical LAME build can be a useful version challenge, but it is not an
encoder-lineage holdout. The same distinction applies to libopus and
libvorbis versions.

### Observed local environment

| Component | Observed version | Binding | Role |
| --- | --- | --- | --- |
| FFmpeg / libavcodec | 8.1.2_1 / 62.28.102 | CLI `1332dc...3327`; libavcodec `a49174...853` | native AAC, Opus, Vorbis; codec wrappers and native decoders |
| LAME / libmp3lame | 4.0 | CLI `11095c...851`; library `463453...934` | development MP3 lineage |
| Apple AudioToolbox | macOS 26.6 build 25G72; afconvert 2.0 | afconvert `7b31d9...14f`; OS build required | development AAC and independent decoder; MP3 encode rejected |
| Shine | 3.1.1 at `ab5e352` | CLI `78db87...95d4`; library `4fdb41...579a` | development MP3 lineage |
| BladeEnc | 0.94.2 at mirror revision `a2d06ec` | CLI `304c26...c8cb` | proposed transfer MP3 lineage |
| FDK AAC / fdkaac | 2.0.3 / 1.0.8 | CLI `5313c0...f9c5`; library `b5f112...41b4` | proposed transfer AAC lineage |
| libopus / opus-tools | 1.6.1 / 0.2_2 | opusenc `41935f...fda`; library `98dcd3...68b` | development Opus lineage and independent decoder frontend |
| libvorbis / vorbis-tools | 1.3.7 / 1.4.3 | oggenc `920e29...7566`; library `38df24...d795` | development Vorbis lineage and independent decoder frontend |
| mpg123 | 1.33.6 | CLI `da6ff8...05b`; library `7212b7...138` | independent MP3 history decoder |

Full SHA-256 values and source bindings are retained in the JSON inventory and
the path-free
[`synthetic probe result`](toolchain-probe-result-20260802.md). The FFmpeg build has
native AAC, native experimental CELT-only Opus, native experimental Vorbis,
libmp3lame, libopus, and Apple AAC support. It does not currently have
libshine, libfdk-aac, or libvorbis encoder wrappers.

The official [FFmpeg codec documentation](https://ffmpeg.org/ffmpeg-codecs.html)
confirms that native AAC is implemented in FFmpeg, native Opus currently
implements only CELT, `libopus` is a wrapper, and `libshine` is a fixed-point
CBR-only wrapper. Xiph documents
[libopus](https://opus-codec.org/docs/) and
[libvorbis](https://xiph.org/vorbis/doc/libvorbis/overview.html) as their
respective reference implementations. This is why native FFmpeg and Xiph
rows are distinct lineages, but two frontends to one Xiph library are not.

## Proposed encoder separation

The smallest viable design is:

| Codec | Mechanism development | Encoder transfer | Why it is disjoint |
| --- | --- | --- | --- |
| MP3 | LAME 4.0; Shine revision `ab5e352` | BladeEnc 0.94.2 revision `a2d06ec` | three implementation lineages |
| AAC-LC | FFmpeg native; Apple AudioToolbox | Fraunhofer FDK AAC 2.0.3 | three implementation lineages |
| Opus | libopus 1.6.1 | FFmpeg native Opus | reference versus native FFmpeg implementation |
| Vorbis | libvorbis 1.3.7 | FFmpeg native Vorbis | reference versus native FFmpeg implementation |

This is a challenge design, not an estimate of encoder prevalence. Shine's
own [project documentation](https://github.com/toots/shine) says its simple
encoder has no psychoacoustic model, while FFmpeg calls native Opus and Vorbis
experimental. They are useful precisely because a representation that claims
codec-history mechanism should not silently depend on one production
encoder's habitual cutoff. They must be reported as atypical lineages.

Those pre-freeze tool checks are now complete. Shine and BladeEnc were built
from exact source revisions, and the Xiph and FDK frontends were bound to exact
binary and library hashes. Two complete probe replays produced byte-identical
path-free reports: all ten retained encoders emitted conformant,
byte-deterministic bitstreams, and all 27 compatible decoder paths emitted
deterministic PCM within path.

The executed Apple MP3 check corrected the proposal. `afconvert` advertised
MPEG Layer III in its format inventory but twice failed before producing a
file. It remains a decoder and AAC encoder binding, not an MP3 encoder. The
replacement is BladeEnc: a distinct, legacy ISO-derived implementation held
for encoder transfer. Like Shine and FFmpeg's experimental encoders, it is an
atypical challenge rather than a prevalence proxy. Its unmodified source also
emits legacy compiler and format-security warnings, so it is private-only and
may process only internally controlled WAV inputs.

Exact decoded PCM was different across decoder implementations for all ten
encoded probes; five also differed in decoded frame count. These are plumbing
observations, not mechanism scores, but they make decoder identity and
alignment mandatory crossed factors. Native FFmpeg Ogg output also required
bitexact mode plus a fixed serial offset for byte reproducibility; those flags
are part of the recipe rather than tunable settings.

FDK requires special care. The primary Android source carries the
[Fraunhofer FDK AAC licence](https://android.googlesource.com/platform/external/aac/),
which permits source and binary redistribution subject to conditions but
explicitly grants no patent licence. It is acceptable for an internal research
challenge only; no binary or FDK-derived public integration is proposed.

## Proposed source separation

### Mechanism development

Reuse only already-consumed v1 sources, excluding all 280 future-only SQAM
cases and every release-held-out case. After excluding the consumed SQAM
domain, the retained population has 527 source groups across seven broad
domains. Its purpose is discovery and paired null analysis, not independent
validation.

### Encoder transfer

The compact proposal uses four previously unused provider collections:

| Collection | Domains | Conservative partition basis/count | Provider evidence |
| --- | --- | ---: | --- |
| clean VCTK subset | studio speech | 56 speakers | Edinburgh documents clean 48 kHz WAV from 56 VCTK speakers; CC BY 4.0 |
| Google Speech Commands v0.02 | crowdsourced 16 kHz command speech | 100-speaker planning cap | [Google's release](https://research.google/blog/launching-the-speech-commands-dataset/) describes thousands of microphone contributors and one-second WAV; CC BY 4.0 |
| TinySOL 6.0 | isolated acoustic instruments | 1 until session metadata is verified | [official record](https://zenodo.org/records/3685367), expressly recorded 44.1 kHz WAV, CC BY 4.0 |
| SONYC-Backgrounds | urban sensor soundscapes | 15 sensor IDs observed in the bound archive | [official record](https://zenodo.org/records/5129078), directly acquired sensor WAV, CC BY 4.0 |

The conservative total is 172 partition groups and four source domains, above
the v2 encoder-transfer minimums of 100 and four. Speech Commands is capped at
100 for planning even though the provider describes thousands of people; the
archive must group every word and utterance by anonymous speaker. Its 16 kHz
bandwidth is an explicit factor, not an excuse to exclude a failure. TinySOL
rows marked `R` for digital pitch transposition cannot be references; they may
be declared PCM-transform hard negatives after their parent relation is
verified. SONYC's
[source-identity audit](sonyc-source-identity-audit-20260802.md) found 550
canonical, distinct-PCM clips from 15 sensor IDs, with provider splits disjoint
by sensor. The planning unit is the sensor, not the clip.

### External transfer

The proposed fresh external set combines:

- the [RWC Music Database 2026 v2 re-release](https://zenodo.org/records/18656623),
  whose five WAV subsets cover classical, genre, jazz, popular, and
  royalty-free music under CC BY-NC 4.0; and
- [RAVDESS audio-only](https://zenodo.org/records/1188976), with 24 actors
  crossing acted speech and song under CC BY-NC-SA 4.0; and
- the current [SATP v1.5 soundscapes](https://zenodo.org/records/18715282),
  with 27 24-bit binaural WAV recordings under CC BY 4.0; and
- the [Audio-Visual Lombard Grid Speech corpus](https://spandh.dcs.shef.ac.uk/avlombard/),
  with 54 directly recorded talkers under CC BY 4.0.

RWC's pinned annotation metadata has 328 piece rows and 99 globally unique
nonempty artist strings, but its
[identity audit](rwc-source-identity-audit-20260802.md) does not mistake those
strings for independent sources. It excludes 35 jazz rows that the provider
identifies as five compositions repeated across seven instrumentations, then
merges two cross-label identities. The planning count is therefore 85 artist
families, not 99 strings or 328 rows. The 2026 RWC release paper states that
these are the original master tracks used for CD production rather than
consumer-ripped copies, and the original project states that the pieces were
performed and recorded for the database.
RAVDESS actor grouping contributes 24, SATP exact-coordinate grouping
contributes 25, and Lombard Grid talker grouping contributes 54. Together they
project to 188 independent partitions across nine domains, 38 above the
minimum.

The Lombard Grid contribution is archive-observed, not copied from its
headline: the acquired audio has 5,390 WAVs, metadata has 5,340 rows, and a
strict filename/metadata/status reconciliation leaves 5,268 eligible WAVs
while preserving all 54 talkers. Its detailed
[source identity audit](source-identity-audit-20260802.md) also records a mix
of 16-bit integer and 32-bit float PCM that must be normalized explicitly.
SATP is likewise archive-observed: its
[source-identity audit](satp-source-identity-audit-20260802.md) reconciles all
27 reference IDs, excludes the calibration signal, and merges two pairs that
share exact provider coordinates. The current record is v1.5 even though the
bound README's dataset-count prose still says v1.2.

This margin is deliberately not treated as permission to weaken identity.
The RWC metadata audit binds its known aliases and dependencies, while
retaining RWC as one provider stratum because metadata cannot prove disjoint
recording sessions or backing personnel. The audio member identities still
require verification. Separately, the encoder-transfer audit found 15—not the
one-group placeholder or the 26 sensors seen in a related wider 2017
analysis—inside the bound SONYC archive. Its README says 441 clips, but the
archive contains 550 canonical WAVs; that mismatch is retained without
inflating the 15 sensor groups. If the external total falls below 150,
add an entirely new provider collection; do not weaken grouping.

## Storage and acquisition boundary

All proposed source archives now total 23,237,282,258 bytes (21.64 GiB). After
the Lombard Grid, SONYC, and 198,110,877-byte SATP acquisitions, the data volume
reported about 42 GiB free. Retaining a 15 GiB reserve leaves roughly 6 GiB for
compact references, derived cases, partials, and temporary intermediates after
the remaining source acquisition. That is viable only if the stager:

- streams selected members without full archive expansion;
- retains at most one bounded reference excerpt per source group;
- processes one low-priority worker;
- checkpoints atomically and removes only reproducible intermediates after
  their hashes and recipes are sealed; and
- rechecks projected and actual free space before each archive and generation
  phase.

The resumable SONYC and SATP audit downloads were completed, matched their
provider byte counts and MD5 values, and were independently bound by SHA-256.
Lombard Grid, SONYC, and SATP are the three sources currently treated as
acquired and identity-verified; no other provider audio archive is.

## Decision and next gate

The tool and source proposal satisfies the v2 minima under its documented lower
bounds, and the external-transfer proposal now has observed margin. The tool
plumbing is verified but not frozen. The next checkpoint must verify every
remaining archive identity, including RWC audio members. Only then may separate
source-allocation, factor-level, and toolchain freezes be committed.

No factor setting, fractional assignment, audio derivative, mechanism score,
candidate, support rule, or public output is authorized by this inventory.
