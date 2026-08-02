# v2 source identity audit - RWC Music Database v2 - 2026-08-02

**Status:** all five audio archives acquired and identity-verified; source
allocation and benchmark factors remain unfrozen

**Actions:** exact Zenodo bytes and checksums bound, ZIP CRCs and member paths
verified, all WAVs streamed without archive extraction, audio identities
reconciled to pinned annotations, global PCM duplication checked, two complete
non-timing replays compared byte-for-byte, no benchmark derivative generated,
and no mechanism score opened

The source rules are
[`benchmarks/audio-integrity-v2/rwc-audio-source-group-rules.json`](../../benchmarks/audio-integrity-v2/rwc-audio-source-group-rules.json).
They bind the earlier
[`artist-family rules`](../../benchmarks/audio-integrity-v2/rwc-artist-family-rules.json)
and
[`metadata-only evidence`](../../research/sources/evidence/rwc-metadata-observed-20260802.json).
The full path-free result is
[`research/sources/evidence/rwc-music-v2-2026-observed-20260802.json`](../../research/sources/evidence/rwc-music-v2-2026-observed-20260802.json),
replayed by
[`scripts/audit-audio-integrity-v2-rwc.py`](../../scripts/audit-audio-integrity-v2-rwc.py).

## Decision

Retain the [RWC Music Database v2 release](https://zenodo.org/records/18656623)
as a Tier A external-transfer candidate at the existing conservative boundary
of 85 artist families. The acquired evidence changes RWC from a metadata-only
proposal to an identity-verified PCM source:

- all 13,418,888,925 provider archive bytes are exact;
- all 328 annotation `RWCID` values have exactly one canonical WAV member;
- all 328 PCM payloads are distinct; and
- the 35 known RWC-J instrumentation-variation rows remain excluded, leaving
  293 future-selection-eligible files across 85 declared artist families.

This is still not source allocation. No artist family, work, member, excerpt,
factor cell, or codec derivative has been selected.

## Provider and processing boundary

The dataset record is version `v2`, DOI
[`10.5281/zenodo.18656623`](https://doi.org/10.5281/zenodo.18656623), under
CC BY-NC 4.0. The 2026
[`RWC Revisited`](https://doi.org/10.5334/tismir.326) paper says the distributed
files stem from the original master tracks used for CD production rather than
consumer-ripped copies.

That statement establishes a materially better path than CD ripping, but it
does not establish untouched studio/session masters. The exact 442-byte
provider changelog records only:

- v2 separation into one ZIP per sub-collection; and
- v1 folder and file renaming.

Neither the paper, changelog, nor annotations proves independent studios,
engineers, sessions, or disjoint backing personnel. The audit therefore calls
the bytes confirmed PCM from a documented CD-production-master path and keeps
RWC as one provider stratum.

## Exact artifact bindings

Every provider MD5 matched, every local SHA-256 was independently computed,
and every complete ZIP passed CRC verification.

| Artifact | Bytes | Provider MD5 | Local SHA-256 |
| --- | ---: | --- | --- |
| `RWC-C.zip` | 2,966,354,301 | `2ac9139c...67f8` | `9c3725ec...ba0d` |
| `RWC-G.zip` | 3,933,055,195 | `e78cddfb...cceb` | `39ec9dae...2100` |
| `RWC-J.zip` | 2,127,754,512 | `c5d7d989...0c37` | `6efeedf8...e2c` |
| `RWC-P.zip` | 4,071,840,278 | `960a11a2...d4f0` | `2ecdad82...ad1` |
| `RWC-R.zip` | 319,884,639 | `63e3b626...caa3` | `27e13df7...6d97` |
| `changelog.txt` | 442 | `f4aa8361...c7ad` | `5ea511cf...a0c1` |

The audio total is 13,418,888,925 bytes (12.50 GiB). Exact URLs, complete
digests, central-directory digests, and verification flags are in the rules
and aggregate. No audio or private filesystem path is committed.

## Member and annotation reconciliation

The pinned annotation revision is
`0a1a6c31dbe73a7f5d44f7caef8cd0999402a4c2`; `metadata.csv` is 48,516 bytes
with SHA-256
`eba3fe129f835db58a9c23dad554547201ab02ef3af90c10857ef5b50b8b99da`.

| Collection | Canonical WAVs | Central-directory SHA-256 |
| --- | ---: | --- |
| C | 61 | `6418256d...5188b` |
| G | 102 | `c735dad7...f9e` |
| J | 50 | `cf26fa9b...cc1` |
| P | 100 | `4c198ed6...5d1c` |
| R | 15 | `4532e457...596b` |

The provider's piece counts are not always file counts. The canonical member
grammar must admit the documented suffix identities: 15 C members in the
`C023A-E`, `C024A-C`, `C025A-D`, and `C035A-C` groups, plus `G058A-C`.
Treating IDs as only three digits would silently discard 18 valid files.

Every archive contains exactly its named top-level directory and canonical
`RWC-X/RWC_XNNN[SUFFIX].wav` members. There are no encrypted members, special
members, unexpected regular files, duplicate paths, missing annotation IDs,
or extra annotation IDs. WAV duration agrees with the metadata to a maximum
error of `0.0000000040700` samples, far inside the fixed `0.000001`-sample
tolerance.

## PCM observations

All 328 members have one homogeneous representation:

| Field | Observed |
| --- | --- |
| RIFF format | little-endian PCM, format tag 1 |
| channels | 2 |
| sample rate | 44,100 Hz |
| sample width | 16 bits |
| format chunk | 16 bytes |
| ancillary chunks | none |
| uncompressed member bytes | 14,859,214,204 |

The shortest file is `RWC_C024C`, 2,216,972 frames (50.271474 seconds), and
the longest is `RWC_C009`, 47,606,776 frames (1,079.518730 seconds). Exact PCM
SHA-256 comparison found 328 distinct payloads and zero repeat groups, both
within and across collections. No group reduction is therefore required for
byte-identical audio.

## Conservative reference boundary

The earlier metadata audit found 99 exact artist labels. The fixed boundary:

1. excludes RWC-J pieces 1-35 because they are five compositions repeated
   across seven instrumentations;
2. merges `Kazuo Nishi` with `Nishi feat.T`;
3. merges `Yuriko Furuichi` with `Yuriko Furuichi & Yoshiko Kikuchi`;
4. excludes every member of any exact repeated-PCM group; and
5. groups the remaining rows by the declared artist family.

The audio observation adds no repeated-PCM exclusion, so 293 files and 85
families remain. Future selection must use a separately frozen,
content-independent rule, choose at most one bounded excerpt per family, and
never repeat a normalized work title. Collection, family, work, legacy disc,
track, and provider identity remain private manifest factors.

The 85 families are grouping units, not 85 independently verified recording
chains. External reporting must retain provider/domain strata and
leave-provider sensitivity so RWC cannot hide a reversal in SATP or Lombard
Grid.

## Reproduction and storage

The auditor validates exact sizes, provider MD5s, local SHA-256s, safe ZIP
members, CRCs, RIFF structure, PCM format, metadata duration, exact PCM
duplicates, family exclusions, and all rule/evidence bindings. Six synthetic
tests cover complete replay, suffix identities, duplicate-PCM exclusion,
metadata mismatch, duration mismatch, and provider-checksum rejection.

Two complete private replays were byte-identical. Each produced SHA-256
`c7dfb3d68e440561802fcacc35584314da0514b5aa96269f37e3c38ab192a324`,
which is also the committed aggregate digest. The bound source-rule digest is
`251b1b37cbdd1d154c29793ce7e05e7bc96eea357c530b40a8964bfb013f5fc6`.

After acquisition, reproducible installer caches, the rejected incomplete
Speech Commands download, and Rust build output were cleaned. The data volume
then reported 16,762,748,928 bytes (15.61 GiB) free, 656,621,568 bytes above
the fixed 15 GiB reserve. The five archives remain compressed; they were never
expanded to disk.

## Next gate

The proposed source collection identities are now fully audited. The next
checkpoint is a separate source-allocation freeze that binds collection/group
partitioning and content-independent member selection without exposing private
identities. Factor levels, toolchain bindings, and fractional assignment must
then be frozen in their own records before benchmark audio is generated.

No source selection, benchmark generation, candidate evaluation, public
verdict, future SQAM opening, release-holdout opening, or external-transfer
score opening is authorized by this audit.
