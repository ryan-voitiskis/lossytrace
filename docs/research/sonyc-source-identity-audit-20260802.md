# SONYC-Backgrounds source-identity audit

Date: 2026-08-02

State: source-identity evidence only; no source allocation or factor freeze

## Outcome

The retained SONYC-Backgrounds 1.0.0 archive supports 15 conservative sensor
groups, not the one-group pre-acquisition placeholder. The archive contains
550 canonical WAV members with 550 distinct PCM digests. Its train, validation,
and test sensor sets are disjoint. This raises the proposed encoder-transfer
population from 158 to 172 groups while preserving four source domains at that
checkpoint. After the later
[source-partition correction](source-partition-correction-20260802.md), the
current encoder-transfer projection is 102 groups across six domains.

The provider documentation is internally inconsistent: the archive README
says that selection produced 441 background clips, while the bound archive
contains 550. The benchmark therefore uses the archive-observed count and does
not silently reconcile or discard the extra 109 files.

The path-free evidence is
[`research/sources/evidence/sonyc-backgrounds-1.0.0-observed-20260802.json`](../../research/sources/evidence/sonyc-backgrounds-1.0.0-observed-20260802.json).
It was produced by
[`scripts/audit-audio-integrity-v2-sonyc-backgrounds.py`](../../scripts/audit-audio-integrity-v2-sonyc-backgrounds.py).

## Provenance boundary

The [official SONYC-Backgrounds record](https://zenodo.org/records/5129078)
identifies the release as version 1.0.0, describes 10-second recordings from
the SONYC acoustic sensor network, documents identical microphones and gain
settings, publishes the filename grammar, and assigns sensors—not clips—to
train, validation, and test splits.

The primary [SONYC system paper](https://arxiv.org/abs/1805.00889) reports that
sensor nodes sampled 10-second snippets and compressed them with lossless FLAC
before encrypted upload. Combined with the archive-observed uncompressed PCM
WAV representation, this is sufficient for the proposed Tier A PCM boundary:
the documented acquisition path contains lossless compression, not a known
lossy distribution step. The benchmark still records SONYC as one provider
stratum because common hardware, gain, preprocessing, collection software, and
network operations remain shared confounds.

## Bound artifact

| Check | Observed value |
| --- | --- |
| Provider record | Zenodo 5129078, version 1.0.0 |
| Archive | `SONYC-Backgrounds.tar.gz` |
| Bytes | 307,235,372 |
| Provider MD5 | `62f9f8549134afb1b831aae08eb19a4b` |
| Local SHA-256 | `cafd6ef96834d98d3381522253f0c22c4d5cbca1b02c81dc13b8cf37fdcfcb0a` |
| Container verification | complete gzip and tar stream read |
| Evidence SHA-256 | `624f8ecd06b6f2d2fa78819cf8f0a0378a831bf47d88ccc860438bce0b1a2eae` |

The audit streamed the archive without expanding it. It validated the provider
byte count and MD5, computed an independent SHA-256, read every regular member,
parsed every RIFF/WAVE structure, and hashed every PCM payload. No local source
path appears in the evidence.

## Archive observations

| Property | Observed value |
| --- | ---: |
| Regular members | 551: one README and 550 WAVs |
| Unexpected regular members | 0 |
| PCM files | 550 |
| Distinct PCM digests | 550 |
| Sensor IDs | 15 |
| Train | 330 files, 4 sensors |
| Validation | 110 files, 5 sensors |
| Test | 110 files, 6 sensors |
| Files per sensor | minimum 1, maximum 213 |
| Date range encoded in filenames | 2017-01-02 through 2017-12-31 |
| Audio representation | mono, 48 kHz, signed 16-bit integer PCM |
| Frames per file | 480,000 exactly |
| PCM bytes per file | 960,000 exactly |
| Duplicate observation keys | 0 |
| Duplicate PCM groups | 0 |
| Sensors crossing provider splits | 0 |

The 15 sensor identities are stronger than treating 550 recordings as
independent, but they are not 15 independent providers. The 1-to-213 imbalance
also means file-level random sampling would be particularly misleading.

## Conservative boundary

A SONYC reference remains eligible only when all of the following hold:

1. Its member uses the provider's canonical sensor/date/hour/instance grammar,
   with a valid date and hour.
2. Its sensor belongs to exactly one provider split.
3. Its PCM digest occurs exactly once in the archive.
4. Future allocation selects at most one excerpt per sensor across all factor
   cells and preserves split, sensor, date, hour, and instance identifiers.
5. Evaluation retains SONYC as one provider stratum and includes
   leave-provider/domain sensitivity.

All 550 WAVs satisfy the first three archive-level rules and all 15 sensors
retain at least one eligible file. This audit does not select which file will
represent a sensor.

## Interpretation of the count mismatch

The README's 441 is a provider claim, not an observed archive invariant. The
109-file surplus could reflect a documentation error or a release change that
was not propagated into the prose; the archive alone cannot distinguish those
explanations. It does not justify exclusion, nor does it increase the source
group count beyond the 15 sensor IDs. The mismatch is therefore retained as a
factorial-benchmark provenance caveat rather than resolved by assumption.

## Next gate

The subsequent
[RAVDESS source-identity audit](ravdess-source-identity-audit-20260802.md)
bound its two audio-only archives at 24 actor groups. TinySOL was subsequently
[bound as one common-collection group](tinysol-source-identity-audit-20260802.md).
The later
[source-partition correction](source-partition-correction-20260802.md) rejected
Speech Commands from Tier A, moved RAVDESS to encoder transfer, and added six
audited FSDD speaker groups. VCTK was subsequently
[identity-verified](vctk-source-identity-audit-20260802.md). The remaining
source gate is RWC audio. Only after it is bound may source allocation, factor
levels, and toolchain versions be frozen in separate records.

No benchmark derivative, mechanism score, candidate decision, or external
transfer evidence was opened by this audit.
