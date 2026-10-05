# Finished-music sources: original sessions and archival transfers

Date: 2026-10-05. Metadata only; no audio acquired, decoded, played or scored.

The laptop-storage authorization removes the unavailable-drive constraint, but
does not resolve the source gate. This pass admits **zero sources**. The frozen
study still needs 100 training, 40 selection, 100 calibration and 300 fresh
evaluation components, including three evaluation production/provider strata.
Neither more tracks from the same performers nor more synthetic encodes supply
that independence. The candidate and comparator have synthetic implementation
tests, not new real-music accuracy evidence.

This extends the [initial feasibility record](music-verdict-source-feasibility-20260927.md)
and the [recording-level follow-up](../../research/music-verdict-v1/source-intake-followup-20261005.json).
The [resource amendment](../../research/music-verdict-v1/resource-authorization-20261005.json)
supersedes the original discovery caps, not the scientific requirements.

## Findings

| Source | What the primary evidence establishes | Qualification result |
| --- | --- | --- |
| [Lorenzo's Music: With you](https://github.com/lorenzosmusic/with-you) | Public Ardour session, WAV assets managed through Git LFS, and a song/session CC BY-SA 4.0 statement. Session metadata was inspected at a pinned commit. | Promising original-session provenance, but imported inputs and the final export chain remain unresolved. One band's songs are not separate artist-disjoint groups. No audio or plugins fetched. |
| [EnsembleSet](https://zenodo.org/records/6519024) | The inspected multitrack release contains 80 chamber pieces rendered using the Spitfire BBC Symphony Orchestra sample library, with multiple microphone/mix configurations. | Synthetic material, not independent real-performer validation. Different microphone mixes do not create new performances. The score sources have differing terms; a paper license does not clear all rendered audio. |
| [KUG Dastgahi Corpus](https://archives.ismir.net/ismir2022/paper/000038.pdf) | The paper identifies four musicians, 65 performance recordings and 31 radif recordings, with studio, Zoom H4 and cellphone recording routes. Audio terms are CC BY-NC-ND 4.0, distinct from the paper's license. | At most four performer components before further grouping, not 96 independent groups. Capture modes, processing history and applicable derivative/weight rights require qualification. Complete solo musical forms are not rejected merely for being solo. |
| [Broadcast Audio Fingerprinting dataset](https://zenodo.org/records/6868083) | 2,000 reference music tracks, but audio is mono 8 kHz 16-bit WAV. Files require an access request and have restrictive use conditions. | Outside the frozen 44.1/48 kHz population. Upsampling would not repair this mismatch. No access request, account or audio acquisition. |
| [Great 78 preservation project](https://great78.archive.org/preservation/) | Documented direct digitization of physical discs at 96 kHz/24-bit, with multiple stylus and equalization variants. Two inspected item records list original 24-bit FLAC transfers. | A large, plausible provenance lead, not an eligible inventory. Delivered rate/channels, rights, complete-work identity and independence remain unresolved. All variants of one recording stay together. |

## Original-session inspection: useful evidence, not a clean label

The Lorenzo session is pinned to commit
`939278c798020e7baf78711138ce8cb6bf5a3f23`. Its XML declares 44.1 kHz.
Of 154 source entries, 114 are audio. Resolving the older Ardour schema's
`Route/Diskstream` playlist-name references yields 25 playlists referencing
40 sources, including 33 audio sources. Fifteen of those audio sources lack
`captured-for` metadata, including drum exports, bass files, a beat and a vocal
selection. That absence is an unresolved provenance detail, **not evidence of
lossy encoding**.

Some screen-capture filenames occur in the complete source list, but none is
referenced by the selected playlists. Playlist references alone do not establish
audible contribution: routing, layers, mute state and export correspondence have
not been fully audited. The README also mentions a missing imported track.
The final released export and the histories of contributing imported material
must therefore be resolved before this session can be a clean negative.
The XML fingerprint is retained in the observation record; incidental local
paths in the public session are not reproduced here.

## Great 78: large catalog, unresolved usable population

A public metadata query for `collection:georgeblood AND year:[1898 TO 1922]`
returned 19,146 catalog matches. Only the first 20 rows were inspected. Their
44 distinct creator strings mix performers and composers; they are not group
counts. None of those rows supplies a license URL. Catalog dates were not
independently verified.

The two item records inspected were Louise & Ferera's *Aloha Oe / Wa Like No A
Like* and Mischa Elman with Percy B. Kahn's *Gavotte / Tambourin*. Each lists an
original `24bit Flac`, a derivative MP3, and a ZIP of additional material.
Listed FLAC durations are 166.27 and 192.63 seconds. Neither metadata response
states the FLAC sample rate or channel count, nor resolves reuse permissions.
We did not fetch headers, audio, ZIPs or spectral previews. Metadata visibility
does not itself prove downloadable access or permission.

The [provider's research page](https://great78.archive.org/research/) invites
research, but is not a substitute for resolving applicable rights. Historical
dates alone are not treated as blanket clearance. No legal conclusion is made.
The documented 96 kHz preservation route also needs an explicit eligibility
decision: this audit does not silently introduce 96-to-48 kHz construction or
expand the frozen inference frontend. These transfers would be a historical,
band-limited stratum, not proof of performance on contemporary studio music.

## Next qualification work and stopping boundary

Great 78 is a new large-scale lead, not a claim that the web search is exhausted
or that the study is ready. Before broad catalog expansion or audio acquisition:

1. Resolve primary-provider access/rights and technical metadata for the two
   records, without bypassing restrictions or relying on a paper's license.
2. Determine whether eligible lossless deliveries exist and whether their
   construction fits the frozen population; document any required scope choice
   rather than silently amending the design.
3. Use performer, session and matrix/work identities to assess component
   capacity and historical overlap. Even a large eligible pool from this one
   production chain would not satisfy the three-stratum requirement alone.

Original-session, Michael Garfield and Trolley Barn leads remain open for
specific lineage questions. Repeated variants or incomplete personnel records
must not be promoted into independent examples. If the remaining gaps require
provider correspondence or a different study scope, request that authority.
Do not fill the gap with more scaffolding, describe missing data as a negative
CNN result, or lower the release gate without a new prospective decision.

Temporary research storage remains ignored under `.tmp/music-verdict-v1`, with
at least 100 GiB filesystem space reserved and retained data destined for
`/Volumes/schwarz` later. No outreach, spending, historical sealed-data access,
training, calibration, evaluation, public verdict or release change occurred.
