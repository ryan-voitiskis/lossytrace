# SATP v1.5 source-identity audit

Date: 2026-08-02

State: source-identity evidence only; no source allocation or factor freeze

## Outcome

The current SATP v1.5 audio archive contains the 27 documented binaural urban
recordings plus one calibration signal. All 27 reference recordings have
unique PCM payloads and reconcile exactly to the bound README table. Two pairs
share identical provider coordinates, so the defensible planning count is 25
source groups rather than 27 files.

This lowered the proposed external-transfer population from 190 to 188 groups
across nine domains at that checkpoint. The later
[source-partition correction](source-partition-correction-20260802.md) moved
RAVDESS to encoder transfer, so the current projection is 164 groups across
seven domains, 14 above the preregistered floor of 150. SATP remains one
provider stratum; the 25 coordinate groups are not treated as independent
hardware or operator lineages.

The path-free evidence is
[`research/sources/evidence/satp-1.5-observed-20260802.json`](../../research/sources/evidence/satp-1.5-observed-20260802.json).
It was produced by
[`scripts/audit-audio-integrity-v2-satp.py`](../../scripts/audit-audio-integrity-v2-satp.py)
under the hash-bound
[`benchmarks/audio-integrity-v2/satp-source-group-rules.json`](../../benchmarks/audio-integrity-v2/satp-source-group-rules.json).

## Current-version correction

The inventory originally referenced Zenodo record 10159673, whose page header
identifies it as v1.3 even though its files and description mention v1.4. The
provider has since published the current
[SATP v1.5 record](https://zenodo.org/records/18715282). The audio ZIP in v1.5
has the same byte count and provider MD5 as the older record, so this is a
metadata-version correction, not an audio substitution.

The v1.5 documentation is itself inconsistent:

- the record and README changelog identify v1.5;
- the README's overview paragraph still says `SATP Dataset v1.2`; and
- the calibration ID has one spacing difference between the README and ZIP.

The audit binds the current record, README, and archive separately and records
those discrepancies. It does not rewrite provider identifiers or infer that
the stale prose changes the audio.

## Provenance boundary

The [current official record](https://zenodo.org/records/18715282) states that
the 27 urban recordings were captured in London with a worn BHS II binaural
microphone kit and SQobold device, then exported from HDF to WAV with ArtemiS
SUITE using the original dynamic range. It describes the references as 24-bit,
48 kHz stereo WAV and the additional 60-second item as a generated calibration
signal.

The documented chain and archive-observed PCM representation contain no known
lossy distribution step, which supports the proposed Tier A boundary. The
original HDF material is not retained here, however, so the benchmark must not
claim to have independently reconstructed the proprietary export path.

## Bound artifacts

| Check | Audio ZIP | README |
| --- | --- | --- |
| Provider record | Zenodo 18715282, v1.5 | Zenodo 18715282, v1.5 |
| Filename | `SATP WAV.zip` | `README.md` |
| Bytes | 198,110,877 | 16,608 |
| Provider MD5 | `1592b4ac667b2944ad3d412212dc669a` | `2c60286df75d1da4eb921d274e5a923e` |
| Local SHA-256 | `7b1c85b4c734e971c5a088f6b23843930012b002213471087dafd8e1f6aa604f` | `b7c0a1497d873be59c4135dfa24590e8e04c93b5b0a1bb03f2a3ba3f1f867fac` |

Additional bindings:

- source-group rules SHA-256:
  `6dc5e17f24d8741ec3ffe00e66b13aacf443fa7a2f0a541fafe92af1d3d0fa05`;
- evidence SHA-256:
  `e0afaebb0f8333940f29c0ad95599d08fc65e8e68a3a87f57ef2d2581b2e01ca`;
- all ZIP CRC checks passed; and
- no private source path appears in the evidence.

## Archive observations

| Property | Observed value |
| --- | ---: |
| Regular ZIP members | 28 |
| README reference rows | 27 |
| Archive reference WAVs | 27 |
| Calibration WAVs | 1 |
| Unexpected members | 0 |
| Distinct reference PCM digests | 27 |
| Duplicate reference PCM groups | 0 |
| Reference format | stereo, 48 kHz, signed 24-bit integer PCM |
| Reference frame range | 1,439,978 to 1,441,904 |
| Nominal reference duration | about 30 seconds |
| Calibration format | stereo, 48 kHz, signed 16-bit integer PCM |
| Calibration frames | 2,880,000, exactly 60 seconds |

The small reference-length spread is retained as an observed source property;
it is not normalized during identity audit. Future case generation must use a
common, declared excerpt duration and retain original frame count as a source
factor.

## Grouping decision

The provider table gives a recording ID, location label, latitude, longitude,
and date. Exact non-missing coordinate pairs define the source grouping; a row
with missing coordinates remains its own group. This merges:

- `OS01c` with `OS01d`; and
- `VP01b` with `W01`.

The remaining 23 recordings are singletons, yielding 25 groups. The second
pair also has different location labels, which is precisely why the rules use
the provider's exact coordinate fields rather than silently choosing one prose
label over the other.

The grouping deliberately does not assert that different coordinates prove
independent days, operator sessions, microphones, recorders, or export
software. Future evaluation must retain recording ID, location text,
coordinates, and date; select at most one excerpt per coordinate group; keep
SATP as one provider stratum; and include leave-provider/domain sensitivity.

## Next gate

The subsequent
[RAVDESS source-identity audit](ravdess-source-identity-audit-20260802.md)
bound its two audio-only archives at 24 actor groups. TinySOL was subsequently
[bound as one common-collection group](tinysol-source-identity-audit-20260802.md).
The later
[source-partition correction](source-partition-correction-20260802.md) rejected
Speech Commands from Tier A, moved RAVDESS to encoder transfer, and added six
audited FSDD speaker groups. The remaining source gate is VCTK and RWC audio.
Only after both are bound may source allocation, factor levels, and toolchain
versions be frozen separately.

No benchmark derivative, mechanism score, candidate decision, or external
transfer evidence was opened by this audit.
