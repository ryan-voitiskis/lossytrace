# Finished-music source feasibility: initial metadata observations

Date: 2026-09-27. No audio fetched, decoded, played or scored.
This is an open qualification record, not an exhaustive dataset review or a
completed source allocation. Public descriptions are not verified per-file
provenance. The proposed study is in
[the successor design](music-verdict-successor-20260927.md).

| Candidate | Primary evidence inspected | Present disposition |
| --- | --- | --- |
| MoisesDB | [Provider repository](https://github.com/moises-ai/moises-db), [paper](https://arxiv.org/html/2307.15913v1) | Promising raw multitracks, not qualified. The paper describes additive, unmastered mixes, and a noncommercial research dataset. The abstract says 45 artists whereas section 3 says 47; resolve with metadata, do not assume 240 independent songs. Recording-to-file codec history and public weight rights need qualification. Even 47 independent groups are insufficient for the proposed final false-alert bound. |
| MedleyDB | [Provider description](https://medleydb.weebly.com/description.html) | 196 multitracks; raw, stem and mixed versions; mixes have unknown mastering status. Audio has noncommercial/share-alike terms. A paper's CC BY notice is not its audio license. Known MUSDB overlap prevents treating the collection as entirely fresh. Raw recording chain and artist/session grouping need member-level evidence. |
| MUSDB18-HQ / DSD100 | [Provider documentation](https://sigsep.github.io/datasets/musdb.html), MoisesDB paper's source history | Already consumed here in part, and overlaps MedleyDB/DSD100. HQ supplies uncompressed WAV, not proof of every upstream stage. Do not open other retained/sealed members to manufacture a fresh population. |
| Mixing Secrets | [Provider FAQ](https://cambridge-mt.com/ms2/mtk-faq/) | Search-visible restrictions require closer primary-page inspection; full page fetch failed. Do not infer permission from free download availability or from another dataset's terms. No outreach or download performed. |
| FMA | [Provider repository](https://github.com/mdeff/fma) | Distributed audio is MP3: not a source of clean negatives. Could establish known-positive examples, but not this matched clean-source study. |
| MAESTRO | [Provider page](https://magenta.withgoogle.com/datasets/maestro) | Documented piano recording corpus, noncommercial/share-alike, already part of historical consumed work. Not a source of unrestricted fresh finished-music validation by relabelling unused members. |
| Slakh | [Provider site](https://www.slakh.com/) | Page retrieval failed in this pass; qualification incomplete. Synthetic rendering, if independently documented/licensed, could support development but would not establish transfer to finished real recordings. No availability/license claim is made from the failed fetch. |
| 2L test bench | [Provider endpoint](https://2l.no/hires/) | Page retrieval failed. Availability, use terms, source count and recording chain remain unverified. Do not use third-party mirrors to evade those unresolved boundaries. |

Additional search hits for isolated-note or dry-voice datasets do not satisfy
the declared finished-music population. Historical TinySOL and other sealed
collections remain untouched. No candidate is rejected because a model dislikes
its waveform: no model has seen these candidates in this study.

The initial metadata pass does **not** yet demonstrate the independent,
provenance-qualified pool required for training and fresh evaluation. It also
does not prove that no such pool exists. Next steps are a bounded primary-source
follow-up, metadata-level grouping/overlap reconciliation, and checking whether
documented direct-recording or source-project collections can fill the gap.
The CNN remains a proposed experiment, not one that has failed a new test.

## Targeted follow-up, first eight of twelve queries

The design permits twelve additional queries and twenty primary provider
records. Eight follow-up queries have now searched recent multitrack releases,
original masters, open testbeds, CC0/lossless collections and recording-chain
documentation. The remaining four queries and unresolved primary leads are
not exhausted. The following findings extend, rather than replace, the table.

- **MTG-Jamendo:** the [provider](https://mtg.github.io/mtg-jamendo-dataset/)
  specifies MP3 distribution, including a second lower-bitrate version.
  Its large track count cannot supply clean negatives.
- **AlbumDB:** the [institutional record](https://research.aalto.fi/en/datasets/albumdb-a-multitrack-dataset-of-a-ten-song-album-with-stereo-and-/)
  describes ten songs with raw, processed and stereo-master versions, PCM
  delivery and a CC BY 4.0 dataset license. This is a promising provenance
  lead, but one album is not ten independent production groups. The linked
  Zenodo record failed to load; member-level chain and overlap remain unverified.
- **Sanidha:** the [authors' paper](https://arxiv.org/html/2501.06959v1)
  documents five concert sessions, fifteen performers, direct DAW recording,
  PCM files and a dataset-specific CC BY 4.0 statement. Several performers
  recur across sessions. A recorded drone may originate from an internet video,
  and headphone leakage is documented. Therefore a full mix cannot automatically
  be labelled clean merely because its microphone tracks were recorded to PCM.
  Resolve the actual drone/monitoring chain before any negative qualification.
- **Hi-Audio:** the [authors' platform paper](https://link.springer.com/article/10.1186/s13636-026-00459-0)
  describes PCM browser recording and retaining original files, but also AAC
  conversions for delivery and support for uploaded material. Dataset-specific
  music licensing is stated; exact original retrieval and member histories are
  still needed. A WAV export can include decoded AAC inputs. No signup or
  platform audio access has occurred.
- **Open Multitrack Testbed:** the primary endpoint was unavailable. Its
  MedleyDB indexing is not a new independent source. Other original-project
  records remain a possible lead, not an accepted corpus.

Eight named primary provider records have been followed up since the design
was written: Mixing Secrets (alternate FAQ), Slakh (about page), MTG-Jamendo,
AlbumDB (institutional/Zenodo record pair), Hi-Audio, Sanidha, Open Multitrack
Testbed, and the MoisesDB primary research page identified in search. Page
finds and alternate URLs for the same record are not new providers. No source
has yet been added to an execution inventory.

## Final four discovery queries and direct-source checks

The remaining four queries examined original DAW/master collections, Live
Music Archive recording lineages and permissions, MusicNet, and Musopen.
All twelve follow-up search queries are now consumed. This is the discovery
query limit, **not** exhaustion of every source on the web or of the separate
twenty-record primary review allowance. Twelve primary provider records have
been reviewed, counting MusicNet, Musopen, Live Music Archive and etree's
seeding guidance in addition to the earlier eight. Retries and metadata files
for the same source do not add new candidates.

### MusicNet: actual metadata inspected, not audio

The [provider record](https://zenodo.org/records/5120004) links a public
[metadata CSV](https://zenodo.org/records/5120004/files/musicnet_metadata.csv?download=1).
A bounded in-memory fetch of that CSV returned 43,775 bytes with SHA-256
`1308d938bafb594e3b0471f2bdda3630da352f881857f265f92114cf398de7ca`.
It contains 330 rows, 32 distinct source strings, 136 distinct
composer/catalog/source tuples, and 123 composer/catalog tuples. Source strings
mix institutions and named performers; these are **not** independent-group
counts. Movements recur within works and performers recur across recordings.
There are no complete capture/codec-chain columns. The transcription labels
and PCM delivery format do not establish the negative history labels needed
here. No MusicNet audio or MIDI archive was fetched.

### Live Music Archive: promising intake lead, not a qualified corpus

The [Internet Archive FAQ](https://archivesupport.zendesk.com/hc/en-us/articles/360016553532-Live-Music-Archive-etree-org)
requires lossless parent material and describes source/lineage metadata, while
also allowing unknown source fields and describing DAT/MD/cassette transfers.
The [etree guidelines](https://wiki.etree.org/index.php?page=SeedingGuidelines)
discourage lossy parents and request full genealogy. These are community
requirements, not verified provenance for each item. A MiniDisc-origin chain,
for example, cannot become a negative merely by ending in FLAC.

The collection's browser page did not expose its catalogue to the text fetcher,
but a direct official metadata-API retry succeeded (HTTP 200). Access is not
the present blocker. The collection states noncommercial circulation and
per-artist policy conditions; it does not establish this study's complete
research/derivative/weight-rights clearance. No artist policy or actual show
has yet been qualified, and no audio or catalogue-wide search was performed.
This is the best remaining large-scale lead for a separately bounded, member-
level metadata intake; claiming 300 suitable independent groups now would be
unsupported. Audience/live recordings would also require checking their fit
to the declared finished-music population, not quietly replacing that population.

### Musopen and retry outcomes

[Musopen's FAQ](https://musopen.org/faq/) explicitly distinguishes uploader
representations from its own verification of recording rights. Its catalogue
description supplies neither complete capture chains nor artist/session
independence. No account was created and no audio downloaded.

Direct official API access also resolved the earlier AlbumDB page-fetch
failure. Its [record](https://zenodo.org/api/records/19683000) reports CC BY 4.0,
PCM raw/processed/master versions and six downloadable archive entries for
one named artist's ten-song album. This is useful source documentation but
does not supply ten artist-disjoint groups. Only metadata was read. A direct
Mixing Secrets FAQ retry returned HTTP 403; no workaround, permission
assumption or source download followed.

## Feasibility checkpoint and next decision

The [machine-readable observation](../../research/music-verdict-v1/source-feasibility-observation-20260927.json)
records the query accounting and MusicNet metadata fingerprint. There is still
no qualified private inventory for the frozen allocations of 100 training,
40 selection, 100 calibration and 300 fresh evaluation groups. Those numbers
were chosen in the prospective design; they are not a theorem that smaller
exploratory experiments are worthless. They cannot be silently relaxed and
then presented as this study passing.

**The immediate execution blocker is source qualification and independent
coverage, not a measured CNN failure.** No training comparison, calibration,
fresh validation or new release preparation is complete. The original goal
remains unfulfilled and the public inspector remains verdict-free.

The actionable next choice is either a larger explicitly bounded metadata-only
intake (the Live Music Archive is a promising lead), or access to an adequately
documented original-recording collection. Outreach, spending and waveform
acquisition are not implied by that choice. A smaller development-only pilot
would require a separately declared successor scope and still could not
support the promised independent release validation. Manufacturing hundreds
of synthetic encodes does not manufacture hundreds of independent real-music
sources. No further discovery queries or model fitting are initiated at this
checkpoint.
