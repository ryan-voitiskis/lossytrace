# v2 source identity audit - Lombard Grid - 2026-08-02

**Status:** acquired source identity evidence; candidate added to the inventory,
but no source allocation or benchmark factor is frozen

**Actions:** official audio and metadata archives acquired, SHA-256-bound, ZIP
CRCs checked, every WAV header inspected, filenames reconciled to metadata, no
benchmark derivative generated, and no mechanism score opened

The path-free aggregate is
[`research/sources/evidence/lombard-grid-2018-observed-20260802.json`](../../research/sources/evidence/lombard-grid-2018-observed-20260802.json).
It is reproducible with
[`scripts/audit-audio-integrity-v2-lombard-grid.py`](../../scripts/audit-audio-integrity-v2-lombard-grid.py).

## Decision

Retain the
[Audio-Visual Lombard Grid Speech corpus](https://spandh.dcs.shef.ac.uk/avlombard/)
as a Tier A external-transfer candidate, grouped into 54 talker identities. It
adds a ninth source domain and moves the projected external-transfer count from
exactly 150 to 204 groups. The resulting 54-group margin means that discovering
RWC artist aliases no longer forces us to weaken the preregistered 150-group
minimum.

This is a source-inventory decision, not the external-transfer allocation. RWC
artist families and recording relationships still require an explicit audit,
and all remaining provider archives still require identity verification before
the allocation can be frozen.

## Why the provenance is suitable

The primary corpus paper reports a dedicated high-quality audio path: speech
was recorded in an acoustically isolated booth at 48 kHz and 24 bits using an
AKG C414 B-XLS microphone and MOTU 8-pre interface. The paper separately
describes AAC and WMA audio embedded in the two webcam streams. For utterance
extraction, the authors used the high-quality desk-microphone recording, with
the webcam audio serving only for temporal alignment, then downsampled the
desk-microphone stream to 16 kHz through FFmpeg. See
[Alghamdi et al. (2018)](https://doi.org/10.1121/1.5042758).

That distinction is decisive: the distributed WAVs are processed PCM excerpts
from a documented direct microphone path, not WAV wrappers converted from the
lossy webcam streams. Downsampling and excerpting remain declared source
processing. No assertion is made that the distributed files are bit-identical
to the 48 kHz/24-bit capture.

[CREMA-D](https://cheyneycomputerscience.github.io/CREMA-D/) was considered and
rejected for this role. Although it offers 91 actor identities, its own
documentation says the computational WAV files were converted from the
original video. Without a lossless original-video audio binding, it cannot
serve as a known-never-lossy reference for this experiment. This rejection
concerns this benchmark role, not the corpus's usefulness for emotion research.

## Remote and local binding

The provider does not publish a checksum. We therefore preserve both a local
SHA-256 and the server's strong ETag, Content-Length, Last-Modified value, and
HTTPS URL. The ETag is treated as provider identity metadata, not mislabeled as
a cryptographic checksum.

| Archive | Bytes | Local SHA-256 | Strong ETag | Last-Modified |
| --- | ---: | --- | --- | --- |
| `lombardgrid_audio.zip` | 652,614,041 | `e3670760...5e10` | `"26e61999-568649ce7ab80"` | 2018-03-27 13:10:22 GMT |
| `lombardgrid_json.zip` | 64,938 | `1de3299b...8a6` | `"fdaa-56864bb4da700"` | 2018-03-27 13:18:52 GMT |

Both ZIP archives passed complete CRC verification. Private filesystem paths
are absent from the inventory and aggregate.

## Provider claims versus acquired bytes

The official page and paper describe 5,400 utterances: 100 per talker for 54
talkers. The acquired artifacts do not exactly implement that description.

| Quantity | Observed | Difference from 5,400 |
| --- | ---: | ---: |
| WAV files | 5,390 | -10 |
| JSON rows | 5,340 | -60 |
| metadata rows marked `CORRECT` | 5,271 | -129 |
| conservative eligible WAVs | 5,268 | -132 |

The discrepancies are structured rather than fatal:

- all 54 talker IDs are present in both archives;
- talker `s51` has 90 WAVs and 90 metadata rows;
- talker `s31` has 100 WAVs but only 50 metadata rows;
- the audio has 50 key occurrences not represented in metadata;
- the metadata has one duplicate key and one excess key occurrence;
- 70 audio filenames carry a wrong-utterance suffix, while 69 metadata rows are
  marked `WRONG`; and
- the provider notes that talker pairs 6/29 and 25/26 share sentence lists.
  They remain distinct human identities, but talker—not sentence—is the group.

The headline count must therefore never be used as an archive assertion.

## Conservative reference boundary

A WAV is eligible for future selection only if all three conditions hold:

1. its name is exactly `sNN_{l|p}_{six-character-grid-code}.wav`;
2. exactly one metadata row has the same talker, condition, and utterance key;
3. that row is marked `CORRECT`.

This leaves 5,268 eligible WAVs. Every one of the 54 talkers retains at least
49 eligible files, so the talker-group lower bound of 54 is observed rather
than inferred. The rule excludes 71 noncanonical names and 51 canonical names
with ambiguous or absent metadata. Selection from the eligible set remains
unauthorized until the source-allocation freeze.

## PCM representation caveat

Every file is mono at 16 kHz, but the archive is not representation-homogeneous:

| RIFF representation | Files |
| --- | ---: |
| 16-bit signed integer PCM | 250 |
| 32-bit IEEE float PCM | 5,140 |

The integer representation appears for four talkers and the float
representation for 53: 50 talkers are float-only, one is integer-only, and
three contain both. Representation is therefore clustered by talker rather
than randomly distributed.

The published collection procedure says 48 kHz/24-bit capture followed by
16 kHz downsampling; a
[related corpus analysis](https://doi.org/10.1016/j.specom.2018.04.006) says
the distributed audio is 16-bit. The actual aggregate contains mostly float
WAVs. This is not evidence of lossy encoding, but it is evidence that source
sample representation cannot be assumed from the paper. Future staging must
decode both representations, check finite/range constraints, normalize through
one frozen conversion path, and retain original representation as a source
factor.

## Storage and next gate

Adding the 652,614,041-byte audio archive raises planned source archives to
23,237,282,258 bytes (21.64 GiB). After acquisition the data volume still had
about 45 GiB free, so the 15 GiB reserve remains intact. The prior streaming,
bounded-excerpt, one-worker rules remain mandatory.

The subsequent
[RWC metadata audit](rwc-source-identity-audit-20260802.md) reduced its planning
count from 99 strings to 85 artist families. The later SATP coordinate audit
reduced its 27 recordings to 25 groups, preserving 38 groups of total
external-transfer margin. The next source gate is not more corpus shopping: it
is to verify exact identities for RWC audio, RAVDESS, VCTK, Speech
Commands, and TinySOL, then separately freeze source allocation, factor
levels, and toolchain bindings.

No benchmark audio generation, candidate evaluation, or external-transfer
score opening is authorized by this audit.
