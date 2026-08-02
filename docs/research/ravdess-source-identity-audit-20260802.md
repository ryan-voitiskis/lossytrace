# RAVDESS v1.0.0 source-identity audit

Date: 2026-08-02

State: source-identity evidence only; no source allocation or factor freeze

## Outcome

The two official RAVDESS audio-only archives contain the documented factorial
population: 1,440 speech WAVs and 1,012 song WAVs from 24 actors, with actor 18
absent from song. The actor identifier is consistent between every member
directory and seven-field filename, and all factorial keys are unique.

Actor identity across speech and song remains the conservative grouping unit,
so RAVDESS contributes 24 source groups. A subsequent
[source-partition correction](source-partition-correction-20260802.md) moved
those groups from external transfer to encoder transfer after Speech Commands
was rejected on provenance grounds. The audit result and grouping did not
change. RAVDESS remains one provider stratum; its actors are not treated as
independent recording or export pipelines.

The path-free evidence is
[`research/sources/evidence/ravdess-1.0.0-observed-20260802.json`](../../research/sources/evidence/ravdess-1.0.0-observed-20260802.json).
It was produced by
[`scripts/audit-audio-integrity-v2-ravdess.py`](../../scripts/audit-audio-integrity-v2-ravdess.py)
under the hash-bound
[`benchmarks/audio-integrity-v2/ravdess-source-group-rules.json`](../../benchmarks/audio-integrity-v2/ravdess-source-group-rules.json).

## Provider claims versus acquired bytes

The [official Zenodo record](https://zenodo.org/records/1188976) describes 24
actors, 60 spoken trials per actor, 44 sung trials for 23 actors, no song files
for actor 18, and audio-only 16-bit, 48 kHz WAV. The primary
[construction paper](https://doi.org/10.1371/journal.pone.0196391) states that
the audio-only channel was exported as lossless wave format at 48 kHz.

The record's prose has a small size-label inconsistency: it calls the speech
archive about 215 MB and the song archive about 198 MB, while its file table
and acquired bytes show the opposite ordering. The audit binds the exact file
table bytes and MD5 values rather than either rounded prose label.

## Provenance boundary

All 2,452 acquired members are signed 16-bit integer PCM at 48 kHz. They also
carry the same `bext`, `FLLR`, `LIST`, and `_PMX` ancillary-chunk pattern. This
is consistent with the paper's reported lossless audio-only export and
supports the proposed Tier A distribution boundary.

It does not establish independent raw-session masters, untouched microphone
feeds, or independent post-production chains for each actor. RAVDESS is an
acted and edited corpus whose members share a production pipeline. The
benchmark may treat the acquired WAVs as confirmed current PCM references,
but it may not infer a stronger pre-export history from their container or
metadata.

## Bound artifacts

| Check | Speech archive | Song archive |
| --- | --- | --- |
| Provider record | Zenodo 1188976, v1.0.0 | Zenodo 1188976, v1.0.0 |
| Filename | `Audio_Speech_Actors_01-24.zip` | `Audio_Song_Actors_01-24.zip` |
| Bytes | 208,468,073 | 225,505,317 |
| Provider MD5 | `bc696df654c87fed845eb13823edef8a` | `5411230427d67a21e18aa4d466e6d1b9` |
| Local SHA-256 | `5d208e01632cc3e5242106fa2af3273e6dc5239fb8143131979ac74c4aa40657` | `89f3df66cc67ebb70c8af6f72f3f359bee497f6f763a9d863b6477619716d428` |

Additional bindings:

- source-group rules SHA-256:
  `01c289969480f37c4758e79825867a280663ab63e4962f2aa5dcf67b039f7e42`;
- evidence SHA-256:
  `22e14a9d008677a38067ec5387d08a96e9799944014274307a4904359ac1f3d2`;
- both ZIP CRC checks passed; and
- no private source path appears in the evidence.

## Archive observations

| Property | Observed value |
| --- | ---: |
| Speech WAVs | 1,440; exactly 60 per actor |
| Song WAVs | 1,012; exactly 44 for each actor except actor 18 |
| Total audio WAVs | 2,452 |
| Actor groups | 24 |
| Distinct PCM digests | 2,451 |
| Repeated PCM groups | 1 group containing 2 files, within actor 7 |
| Selection-eligible unique-PCM WAVs | 2,450 |
| Mono WAVs | 2,446 |
| Stereo WAVs | 6: five speech and one song |
| Speech frame range | 140,941 to 253,053, about 2.94 to 5.27 seconds |
| Song frame range | 168,168 to 305,906, about 3.50 to 6.37 seconds |
| Unexpected regular ZIP members | 0 |

The same-actor repeated-PCM pair is:

- `Actor_07/03-01-03-01-02-01-07.wav`; and
- `Actor_07/03-01-03-01-02-02-07.wav`.

The filenames differ only in their repetition field, so neither member may be
selected as a reference without making an arbitrary choice between identical
PCM. Excluding both still leaves unique eligible audio for every actor.

The six stereo outliers are:

- `Actor_01/03-01-02-01-01-02-01.wav`;
- `Actor_01/03-01-08-01-02-02-01.wav`;
- `Actor_05/03-01-02-01-02-02-05.wav`;
- `Actor_20/03-01-03-01-02-01-20.wav`;
- `Actor_20/03-01-06-01-01-02-20.wav`; and
- `Actor_24/03-02-01-01-01-01-24.wav`.

Stereo is not treated as evidence of a different actor or provenance class.
It is an observed source-format factor. A later source freeze must decide and
declare whether references are restricted to the common mono representation;
the stager may not silently downmix or let these six files create an accidental
channel/source confound.

## Grouping decision

The actor field defines source identity across emotion, intensity, statement,
repetition, and vocal channel. Directory actor and filename actor must match.
The future selection boundary is therefore:

- at most one reference excerpt per actor across speech and song;
- exclude every member of a repeated-PCM group;
- preserve all seven filename factors and original channel count;
- retain RAVDESS as one provider stratum; and
- include leave-provider/domain sensitivity in transfer reporting.

The audit verifies identity and eligibility, not allocation. It does not choose
which actor utterances, channel representation, or durations enter the future
manifest.

## Storage and next gate

The two retained archives add 433,973,390 bytes. After the later Speech
Commands rejection and FSDD replacement, the remaining VCTK and RWC archives
total 18,189,508,204 bytes (16.94 GiB). At the correction checkpoint,
preserving the 15 GiB reserve left about 4.15 GiB for bounded references,
partials, and derived cases. Streaming, one-worker operation, and a free-space
check before every remaining archive are therefore mandatory rather than
advisory.

The subsequent
[TinySOL source-identity audit](tinysol-source-identity-audit-20260802.md)
kept its conservative common-collection count at one. Speech Commands was
subsequently
[rejected from Tier A](speech-commands-provenance-rejection-20260802.md), and
the audited six-group FSDD corpus replaced its clean transfer role. The
remaining source gate is VCTK and RWC audio identity verification. Only after
those archives are bound may source allocation, factor levels, and toolchain
versions be frozen separately.

No benchmark derivative, mechanism score, candidate decision, or external
transfer score was opened by this audit.
