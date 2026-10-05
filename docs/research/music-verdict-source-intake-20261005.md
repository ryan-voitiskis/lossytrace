# Expanded finished music source intake

Date: 5 October 2026. Source intake has resumed under the user's
[resource and temporary laptop storage authorization](music-verdict-resource-authorization-20261005.md).
The source-search ceiling is removed. This pass retrieved metadata only; no
audio was acquired, scored or admitted to an execution inventory. There is
still no successor CNN result or release verdict.

## Catalogue evidence and its limits

The public Internet Archive metadata API returned 1,495 distinct Live Music
Archive recording entries with a populated license field. Across those entries
there are 300 case-folded creator strings. A preliminary URL filter for CC BY,
CC BY-SA or CC0 gives 398 entries and 61 creator strings. These are discovery
counts, not verified licenses, independent performers, qualified clean sources
or the whole Live Music Archive. Shared performers, aliases, incomplete
histories and incorrect license tags still require review.

Two sorted catalogue pages are complete for that query at retrieval time; they
are not an immutable catalogue snapshot guaranteed by the provider. Their
response hashes and retrieval times are recorded in the
[observation ledger](../../research/music-verdict-v1/source-intake-observation-20261005.json).
The same ledger binds 49 saved responses totalling 855,266 bytes. Raw metadata
is kept outside Git in the authorized `.tmp/music-verdict-v1` working area;
the ledger contains request URLs and fingerprints, not uploader contact details.

A separate policy-text search returned 31 artist collections, all inspected.
Four additional artist policies were read alongside individual recordings.
Searching seven collections with more explicit Creative Commons language
returned 19 recordings from five creator strings. A broader Community Audio
original-recording keyword query returned 124 entries and 85 creator strings,
including non-music and unresolved sources. None of these counts establishes
the frozen source allocations.

## Recording level findings

| Recording | Evidence | Qualification outcome |
| --- | --- | --- |
| [Gold Ramble, 24 July 2022](https://archive.org/metadata/gr2022-07-24) | Microphone, USB interface and Reaper chain; original 24-bit FLAC entries; item marked CC BY. | [Artist policy](https://archive.org/metadata/GoldRamble) records noncommercial circulation. Resolve the scope and authority of the broader item license; do not automatically clear release rights. |
| [Bluesphere, 12 February 2026](https://archive.org/metadata/Bluesphere2026-02-12.Bluesphere) | Recorder and Audacity chain, guitar/looper/synth setup and three performers described; CC BY-SA item tag. | [Artist policy](https://archive.org/metadata/Bluesphere) describes noncommercial circulation. Capture mode and license scope remain unresolved. |
| [Blasting Rod, 8 April 2023](https://archive.org/metadata/bsr2023-04-08.aud.mn612ja.pcm) | Explicit 16-bit/44.1-kHz mono PCM recording, Audacity and FLAC path. | Stronger capture documentation, but [artist policy](https://archive.org/metadata/BlastingRod) limits distribution to personal trading and retains underlying rights. The CC BY-SA item tag alone does not resolve that mismatch. |
| [The Breakfast, 27 November 2019](https://archive.org/metadata/breakfast2019-11-27.Multitrack-Soundboard) | 24-bit/48-kHz multitrack capture, stereo mix and FLAC; personnel named; CC BY item tag. | [Artist policy](https://archive.org/metadata/TheBreakfast) describes personal, noncommercial audience taping and prohibits soundboard patches. Do not infer this particular upload has broader authorization. |
| [Michael Garfield, 12 July 2012](https://archive.org/metadata/MG2012-07-12) | Artist-curated acoustic/electronic guitar excerpts, Boss RC-300 to Ableton; originals listed as AIFF. | [Artist policy](https://archive.org/metadata/MichaelGarfield) explicitly states noncommercial attribution/share-alike and remix permission. Promising private-research lead; complete-track selection, actual capture/export representation and grouping still need qualification. |
| [Michael Garfield, 1 May 2013](https://archive.org/metadata/michaelgarfield2013-05-01.ca14s.cards.16bit) | Microphones to DR-2d, 24-bit/48-kHz WAV, documented resampling/dither, 16-bit/44.1-kHz WAV and FLAC. | Concrete PCM-chain lead. Verify full-song membership, performer/lineage overlap and scope before admission. A second recording of this performer does not create another artist-independent group. |
| [Mnemonic, 1 November 1997](https://archive.org/metadata/Mnemonic1997-11-01) | [Artist policy](https://archive.org/metadata/Mnemonic) specifies CC BY-SA 2.0; all 17 originals listed as Ogg Vorbis. | Not a clean-negative source. Collection membership does not guarantee lossless original files. |
| [Black Coffee, 5 June 2011](https://archive.org/metadata/BC2011-06-05.flac) | Original FLAC entries and a soundboard label; [artist policy](https://archive.org/metadata/nocreamorsugar) specifies noncommercial/share-alike. | Recorder, encoding and transfer stages missing. A soundboard label is not a complete PCM chain. |

The seven-collection search also found
[Tacit Dynamite, 10 February 2006](https://archive.org/details/td2006-02-10.flac16)
with an explicit Sony MiniDisc stage before WAV/FLAC. It cannot be used as a
clean negative merely because its distributed files are FLAC.

Creative Commons' [technology guidance](https://creativecommons.org/faq/#artificial-intelligence-and-cc-licenses)
does not require an extra AI-specific permission when a valid license already
covers the use and its conditions are met. The unresolved issues here are
licensor authority, inconsistent source statements, applicable conditions and
the exact recording—not a blanket requirement that every CC license mention
machine learning. Private research and distribution of weights remain separate
decisions under the frozen study.

## Other leads reconciled

- The current [Mixing Secrets FAQ](https://www.cambridge-mt.com/ms3/mtk-faq/)
  is explicit that research and AI training require individual contributor
  permission. Search-indexed primary-page text resolved the previously unknown
  restriction, although direct page reads still failed. No audio was fetched
  and no request sent.
- The [RWC v2 release](https://zenodo.org/records/18656623) and
  [2026 paper](https://reference-global.com/article/10.5334/tismir.326?tab=article)
  were rechecked. This is **not a fresh collection for LossyTrace**: the
  [August source audit](rwc-source-identity-audit-20260802.md) already bound all
  five archives, 328 recordings and 85 historical artist families, without
  certifying independent sessions/backing personnel. No retained audio or
  sealed partition was opened, and no RWC family was relabelled fresh.

## Engineering checks and continuation

The new metadata collector accepts only public Archive search/item metadata
endpoints, refuses redirects and download URLs, limits each response size,
uses fresh no-clobber output directories and binds response bytes to hashes.
It never follows license URLs, opens audio or certifies sources. Requests in
the artist-policy batches were sequential and paced; no credentials or account
creation were used. Its nine offline tests and the existing 23 study-preflight
tests pass. The historical preservation check confirms 980 protected files
are unchanged. The full release regression suite was not rerun for this
metadata-only addition.

Continue with artist-authorized original recordings, complete personnel and
session/lineage metadata, and the unresolved Community Audio leads. Check
source identities against historical metadata before acquisition. Keep live
recordings distinct from studio-mix strata; do not quietly redefine the
population as whatever is easiest to download. Before any larger write, enforce
the newly approved 100 GiB free-space reserve. Source qualification, independent
coverage and execution freeze remain prerequisites for model work; storage
absence and the old query ceiling are no longer the immediate blockers.
