# Additional permissive-provider screen - 2026-08-14

**Status:** four additional purpose-recorded music providers enter the
metadata-level exact-member-audit candidate tier. They improve several
arithmetic sensitivities, but do not establish a listening-truth manifest,
mastered-music transfer, broad three-domain transfer, or the 120-group
reference sensitivity. No audio archive or member was downloaded or opened.

## Outcome

The public-record screen found four immutable CC BY 4.0 or CC0 candidates:

| Provider | Exact public version | Conservative candidate groups | Music limit |
| --- | --- | ---: | --- |
| AlbumDB | Zenodo `19683001`, v1.0, CC BY 4.0 | 10 songs | one indie rock/folk album and one engineer; only mastered-music provider found |
| ChoraleBricks | Zenodo `20849469`, v1.1.0, CC BY 4.0 | 10 chorale works | controlled isolated wind performances, not mastered multigenre music |
| Good-sounds | Dataverse `DATA2314`, v1.0, CC BY 4.0 | 15 performers | controlled single-note and scale exercises, not mastered music |
| URMP | Zenodo `5034983`, CC0 | 28 unique works | controlled classical performances; 44 arrangements collapse to 28 work groups |

AlbumDB's official record describes an original ten-song album, raw, mixed-dry
and mixed stems, stereo and 7.1.4 masters, and 16-bit 44.1 kHz PCM WAV. The
paper documents the home-studio chain and also identifies sample-reinforced
drums and software instruments. Exact members and their source relationships
therefore still need auditing; ten songs are not ten independent providers.

ChoraleBricks purpose-recorded 193 isolated wind-instrument tracks with a
Schoeps MK 4 microphone and Apple Logic Pro in three controlled environments.
The exact v1.1.0 record is bound because it is a breaking release whose archive
checksums differ from v1.0.0. Raw recordings may be candidates; processed
reference mixes and modular derivatives cannot be counted as independent
sources.

The current Good-sounds Dataverse re-release is explicitly CC BY 4.0 and says
15 professional musicians were purpose-recorded in studio conditions. Its
older Zenodo record is internally inconsistent: the structured licence field
says CC BY, while the description says CC BY-NC. Only the exact 2025 Dataverse
v1.0 re-release is a candidate, and its embedded archive rights must be checked
before any member is selected.

URMP's immutable record is CC0. Its documentation distinguishes separate
24-bit 48 kHz WAV tracks and direct-sum WAV mixes from AAC audio embedded in
the videos. The 44 arrangements derive from 28 unique works, so the screen
uses 28 as the conservative metadata-level ceiling before musician, session,
guide-performance and derivative grouping.

## Updated arithmetic

The predecessor exact-member-audit pool contained seven providers and 1,867
candidate groups. Adding 63 candidate groups from these four providers yields
11 providers and 1,930 metadata-level groups. Qualified and allocated counts
remain zero.

The deterministic whole-provider solver now gives:

| Sensitivity | Arithmetic result | Scientific result |
| --- | --- | --- |
| 39 groups in each of four partitions | feasible | ineligible |
| two providers and 39 groups in each partition | feasible | ineligible |
| 8 music, speech and natural groups in final validation | feasible | ineligible |
| 8 music groups in every partition | feasible | ineligible |
| 8 music, speech and natural groups in every partition | infeasible | ineligible |
| 8 mastered-music groups in every partition | infeasible | ineligible |
| two mastered-music providers in final validation | infeasible | ineligible |
| 120 groups in each partition | infeasible | ineligible |

The positive arithmetic results do matter: the earlier seven-provider and
seven-real-music bottlenecks are no longer accurate. They do not cross the
scientific gate. Only two speech providers and two natural-sound providers are
available, so those domains cannot remain whole-provider separated across all
four partitions. AlbumDB is the only mastered-music provider and represents a
single album. Controlled classical, wind, solo-instrument and exercise
recordings cannot silently become evidence for mastered multigenre transfer.

## Other candidates screened out

RWC 2.0, MUSDB18-HQ, the anechoic string-quartet set and mshoxxDB are outside
the narrow path because their current licences contain noncommercial terms.
WaivOps EDM-TR9 is programmed and its sample chain is unresolved. BSD35k-CS is
crowdsourced, converted from Freesound sources and includes noncommercial
members. The Open Multitrack Testbed lacks a currently bound immutable member
record. OrchideaSOL's current Zenodo record binds metadata but not the audio
member set. The Bach Violin Dataset derives from MP3 and Opus web sources.
None enters truth-bearing capacity in this checkpoint.

## Boundary and next decision

No exact member, source manifest, provider allocation or primary-domain design
is frozen. No new audio, retained ODAQ read or projection, processed condition,
target degradation score, metric execution, human collection, sealed evidence,
no-reference training or public verdict is authorized. An unrelated URMP
synchronization-study summary was incidentally visible in a search result; it
was not used in candidate classification and no target degradation score was
opened.

The source successor remains a responsible-human decision: authorize a bounded
exact-member metadata audit of the expanded candidates, narrow the primary
domain claim, or reject the current truth-source design. That choice remains
independent of the metric-successor decision.

Official public records:

- [AlbumDB record](https://zenodo.org/records/19683001) and [paper](https://www.pure.ed.ac.uk/ws/portalfiles/portal/656673398/2026_McK_Dataset_AES_Europe_2026_2_.pdf)
- [ChoraleBricks record](https://zenodo.org/records/20849469), [dataset page](https://www.audiolabs-erlangen.de/resources/MIR/2025-ChoraleBricks), and [paper](https://www.audiolabs-erlangen.de/content/resources/MIR/00_2025-ChoraleBricks/2025_BalkeBM_ChoraleBricks_TISMIR_ePrint.pdf)
- [Good-sounds v1.0 re-release](https://doi.org/10.34810/DATA2314) and [historical Zenodo record](https://zenodo.org/records/820937)
- [URMP record](https://zenodo.org/records/5034983), [documentation](https://labsites.rochester.edu/air/projects/URMP/URMP_doc.pdf), and [paper](https://labsites.rochester.edu/air/publications/li2018creating.pdf)

Machine-readable artifacts:

- [`public metadata observation`](../../research/toolchains/evidence/perceptual-degradation-additional-permissive-provider-public-metadata-observation-20260814-001.json)
- [`allocation plan`](../../benchmarks/perceptual-degradation-v1/additional-permissive-provider-allocation-feasibility-plan.json)
- [`deterministic report`](../../research/toolchains/evidence/perceptual-degradation-additional-permissive-provider-allocation-feasibility-20260814-001.json)
- [`solver and validator`](../../scripts/perceptual_degradation_additional_provider_feasibility.py)
