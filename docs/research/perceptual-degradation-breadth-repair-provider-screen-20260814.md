# Breadth-repair provider screen - 2026-08-14

**Status:** official collection-level records expose a possible arithmetic
repair for the remaining speech, natural-sound and mastered-music shortages,
but the repair is not scientifically established. Three candidates have
immutable or stable records. ICSI and three artist releases remain
preservation-required provisional records. No audio, archive member, metric,
score, listener response or sealed evidence was opened.

## Outcome

The bounded public-record screen adds seven providers to a labelled
sensitivity pool:

| Provider | Domain | Public-record capacity | Record status | Critical limit |
| --- | --- | ---: | --- | --- |
| English children speech | speech | 11 child speakers | immutable Zenodo record | parallel microphone versions must remain grouped by child |
| GESMA | natural sound | 18 contributors | immutable Zenodo record | contributor, device, session and location relationships need audit |
| DataSTORRE acoustic examples | natural sound | 67 recordings; conservative floor 8 | stable versioned repository record | 67 files are not yet 67 independent groups |
| ICSI Meeting Corpus | speech | 53 speakers | preservation required | the official page is not an immutable release record |
| The Grumbles, *A Pretty Bad Good* | mastered music | 8 tracks | preservation required | one mutable Bandcamp release and one shared production chain |
| Stranger, *Self-imposed Exile* | mastered music | 20 tracks | preservation required | one mutable Bandcamp release and one shared production chain |
| WangleLine, *Honey* | mastered music | 9 tracks | preservation and production audit required | no explicit mix/master credit on the mutable page |

The [English children speech record](https://zenodo.org/records/200495)
declares CC BY 4.0, eleven children, lossless WAV delivery and three parallel
microphone paths. The group ceiling is therefore eleven speakers, not three
times eleven microphone files.

The [GESMA record](https://zenodo.org/records/18315044) and
[paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC13090659/) declare CC BY 4.0,
22,193 uncompressed field recordings and eighteen contributors. The screen
uses contributors—not files or sound labels—as its pre-audit capacity ceiling.

The [DataSTORRE record](https://datastorre.stir.ac.uk/handle/11667/220?mode=full)
declares CC BY 4.0 and 67 one-minute WAV recordings with location, time,
equipment and recordist metadata. Because those relationships have not been
collapsed, the plan reports both its 67-recording ceiling and an explicit
eight-group conservative floor.

The [ICSI collection page](https://groups.inf.ed.ac.uk/ami/icsi/) declares CC
BY 4.0, about 70 hours of meetings and close-talking channels. Its 53-speaker
public count repairs a fourth provider-pure speech slot only in the
preservation-required sensitivity.

The public pages for
[*A Pretty Bad Good*](https://thegrumbles.bandcamp.com/album/a-pretty-bad-good),
[*Self-imposed Exile*](https://stranger-theband.bandcamp.com/album/self-imposed-exile),
and [*Honey*](https://wangleline.bandcamp.com/album/honey) expose CC BY 4.0
artist releases and lossless download options. Those mutable transactional
pages do not establish an immutable rights record, the artist-upload
container, or a never-lossy origin chain. They therefore enter only a clearly
labelled arithmetic sensitivity, not the exact-member-audit candidate tier.

## Arithmetic sensitivity

The predecessor pool had 11 providers and 1,930 metadata-level candidate
groups. After the successor stable-music screen added Vienna 4x22 and ROD, the
public-record ceiling produces 20 providers and 2,140 groups; using the
conservative DataSTORRE floor produces 2,081. Qualified and allocated counts
remain zero.

| Sensitivity | Arithmetic result | Why it does not cross the scientific gate |
| --- | --- | --- |
| music, speech and natural sound in every partition, all public records | feasible | the fourth speech provider is unpreserved ICSI |
| same, stable records only | infeasible | only three speech providers remain |
| eight mastered-music groups in every partition, all public records | feasible | three of four mastered providers are mutable single-release pages |
| same, stable records only | infeasible | AlbumDB remains the only stable mastered provider |
| two mastered providers in final validation, all public records | feasible | the second provider is provisional; no final allocation exists |
| 120 groups in every partition at DataSTORRE's 67-recording ceiling | feasible | it uses provisional providers and unaudited metadata capacity |
| 120 groups in every partition at the eight-group floor | feasible after Vienna 4x22 and ROD supplement | it still uses provisional providers and selects no exact members |
| 120 groups in every partition, stable records only at the 67-recording ceiling | infeasible | stable non-Slakh capacity remains below the three other 120-group partitions |

This resolves an arithmetic question, not the source design. Every positive
witness still assigns whole candidate providers without selecting exact
members. The stable-only result does not yet support three primary domains in
all partitions, mastered-music transfer, or the 120-group sensitivity. The
full public-record 120-group result no longer depends on the DataSTORRE ceiling
alone, but it still depends on unpreserved provisional providers.

## Screened but not added

The [FreiDi record](https://zenodo.org/records/20285754) is CC BY-SA 4.0 and is
outside the selected narrow path despite its strong multitrack provenance.
Clarity Speech has conflicting rights statements; DAPS is noncommercial;
Trustworthy Intent leaves the remote capture encoding chain unresolved; and
the located anechoic speech record did not expose an exact corpus licence.
Two other Bandcamp pages combined explicit CC BY text with an `all rights
reserved` page field and were rejected for that conflict.

## Boundary and next decision

No provider is selected. No public page has been promoted to immutable rights
evidence. No exact source relationship, source manifest, provider allocation,
primary-domain claim or resource plan is frozen. This screen does not broaden
the existing ODAQ authorization, select ViSQOL, authorize audio acquisition or
member access, execute a perceptual metric, collect listening evidence, open
sealed evidence, permit no-reference training, or change the public CLI.

The next source-side decision is whether to authorize bounded preservation and
exact-member metadata audit of these records, narrow the primary-domain claim,
or reject the current truth-source design. Metric-successor selection remains
a separate responsible-human decision.

Machine-readable artifacts:

- [`public metadata observation`](../../research/toolchains/evidence/perceptual-degradation-breadth-repair-public-metadata-observation-20260814-001.json)
- [`allocation-sensitivity plan`](../../benchmarks/perceptual-degradation-v1/breadth-repair-provider-allocation-feasibility-plan.json)
- [`deterministic report`](../../research/toolchains/evidence/perceptual-degradation-breadth-repair-provider-allocation-feasibility-20260814-001.json)
- [`solver and validator`](../../scripts/perceptual_degradation_breadth_repair_feasibility.py)
