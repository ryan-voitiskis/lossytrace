# Factorial v2 synthetic toolchain probe result - 2026-08-02

**Decision:** retain ten encoder bindings and five decoder implementations for
the pre-freeze matrix; reject Apple AudioToolbox as an MP3 encoder on the bound
OS build; keep all observations as synthetic plumbing evidence only

**Scientific state:** no benchmark audio generated, no mechanism score opened,
no source allocation or factor setting frozen, and no candidate selected

## Reproducibility binding

The public, path-free aggregate is
[`research/toolchains/evidence/observed-20260802-001-aggregate.json`](../../research/toolchains/evidence/observed-20260802-001-aggregate.json).
Its SHA-256 is
`fb497f37ade1a6db5e3d87a0f957f6c2e72433c4091679f098ab6ce07b8b8c8d`.
Two complete invocations of the probe harness produced byte-identical reports.

The harness:

- generates two three-second stereo PCM fixtures using integer-only arithmetic;
- verifies every executable and linked codec component against its declared
  SHA-256 before execution;
- runs every encoder twice and requires a byte-identical bitstream;
- checks codec, profile, sample rate, and channel count with the bound FFprobe;
- crosses every encoded stream with each compatible decoder twice and requires
  deterministic PCM within that path;
- records only sanitized command templates and path-free hashes; and
- marks the result as synthetic plumbing, with benchmark generation, scoring,
  and selection disabled.

The implementation is
[`scripts/probe-audio-integrity-v2-toolchains.py`](../../scripts/probe-audio-integrity-v2-toolchains.py).
Mandatory CI covers its integer PCM golden, command sanitization, path-leak
guard, decoder-disagreement summary, and hash validation.

## Encoder result

| Codec | Mechanism-development lineage | Encoder-transfer lineage | Probe outcome |
| --- | --- | --- | --- |
| MP3 | LAME 4.0; Shine 3.1.1 at `ab5e352` | BladeEnc 0.94.2 at `a2d06ec` | Three conformant 44.1 kHz stereo CBR-128 bitstreams; deterministic |
| AAC-LC | FFmpeg native 8.1.2; Apple AudioToolbox on build 25G72 | FDK AAC 2.0.3 through fdkaac 1.0.8 | Three LC-profile 44.1 kHz stereo CBR-128 bindings; deterministic |
| Opus | libopus 1.6.1 through opusenc 0.2_2 | FFmpeg native 8.1.2 | Two conformant 48 kHz stereo 96-kbit/s bindings; deterministic |
| Vorbis | libvorbis 1.3.7 through oggenc 1.4.3 | FFmpeg native 8.1.2 | Two conformant 44.1 kHz stereo quality-4 bindings; deterministic |

The aggregate contains ten encoder probes. Every retained bitstream was
byte-identical across its two executions. FFmpeg's native Ogg muxing was not
byte-stable with ordinary flags because the stream serial changed. Bitexact
mode plus a fixed serial offset made both native Opus and native Vorbis output
repeatable; those flags are now part of the probe recipe.

### Apple MP3 correction

`afconvert -hf` listed MPEG Layer III formats, but executed CBR-128 probes at
both 44.1 and 48 kHz failed before creating an output. The formal 44.1 kHz
rejection was reproduced twice with the same return code and sanitized error
signature. Capability listings therefore cannot establish an encoder binding.

Apple AudioToolbox remains useful as an AAC encoder and as an independent
decoder for all four scoped codecs. It no longer counts toward MP3 encoder
transfer. BladeEnc replaces it as the third MP3 implementation lineage.

BladeEnc is deliberately bounded: it is a legacy ISO-derived CBR encoder, not
a prevalence proxy, and its unmodified source produces compatibility and
format-security warnings with a current compiler. It may process controlled
private WAV inputs only and is ineligible for the public library or CLI.

## Decoder result

The probe exercised 27 compatible paths:

- FFmpeg native decoding for all ten encoded streams;
- Apple AudioToolbox decoding for all ten;
- mpg123 decoding for the three MP3 streams;
- opusdec/libopus decoding for the two Opus streams; and
- oggdec/libvorbis decoding for the two Vorbis streams.

Every path produced byte-identical WAV and PCM output across its two runs.
However, none of the ten encoded streams produced the same exact PCM hash
across different decoder implementations. Five also produced different frame
counts: all three AAC bindings, Shine MP3, and reference-libvorbis output.

This does not establish a useful codec-history effect. It establishes a
confound that the matrix must control. History-decoder and analysis-decoder
identity, priming/padding treatment, alignment, frame count, and sample
quantization must remain explicit. Paired comparisons must be performed within
a fixed decoder path before any across-decoder stability claim is considered.

## Licence and distribution boundary

Shine and BladeEnc source revisions, trees, licence files, binaries, and linked
libraries are hash-bound in the evidence. Xiph frontends are bound to their
libopus and libvorbis libraries. FDK AAC remains internal-research-only: its
frontend has permissive components, but the Fraunhofer codec licence grants no
patent licence and imposes redistribution conditions. No FDK binary or derived
integration is proposed for LossyTrace distribution.

## Decision and next gate

The codec tool matrix is executable and reproducible enough to carry into a
separate freeze, subject to the stated legacy and licence restrictions. The
tool probe does not freeze rate-control levels beyond the synthetic commands,
authorize benchmark construction, or support any provenance inference.

The remaining pre-freeze blocker is source identity, not codec plumbing. A
subsequent acquired
[Lombard Grid audit](source-identity-audit-20260802.md) added 54 observed talker
groups, moving external transfer from exactly 150 to 204 projected groups.
A subsequent
[RWC metadata audit](rwc-source-identity-audit-20260802.md) then excluded known
repeated arrangements and merged cross-label identities, reducing RWC from 99
strings to 85 artist families; the later SATP coordinate audit reduced the
external total to 188. That preserves a 38-group margin. Verify every remaining
archive identity before the separate freeze; the later
[RAVDESS audit](ravdess-source-identity-audit-20260802.md) bound its two audio
archives at the existing 24-actor count. RWC audio, VCTK, Speech Commands, and
TinySOL remained at that point; TinySOL was subsequently
[bound as one common-collection group](tinysol-source-identity-audit-20260802.md).
RWC audio, VCTK, and Speech Commands remain; do not spend the margin by
weakening grouping.
