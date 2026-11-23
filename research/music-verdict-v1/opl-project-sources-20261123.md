# Authored electronic music from FM tracker projects

The Battle of the Bits public API lists original project filenames and credits separately from encoded listening previews. Its OPL2 competition specifies Yamaha FM synthesis and explicitly excludes sampled instruments for S3M and MPTM entries. The composition rules permit some competition-specific remixes, so a format label alone cannot establish work lineage. We inspected public catalogue metadata only. No project, waveform or preview was downloaded or played. [API documentation](https://battleofthebits.com/lyceum/View/BotB%2BAPI%2Bv1) · [OPL2 format](https://battleofthebits.com/lyceum/View/opl2%2B%28format%29) · [Competition rules](https://battleofthebits.com/lyceum/View/Rules)

| Screen | Entries | Provisional groups represented |
| --- | ---: | ---: |
| OPL2, OPL3 and legacy AdLib catalogues combined | 736 | 199 |
| From 2012 onward, credited, listing at least 30 seconds | 643 | 171 |
| Shortlisted tracker filename extensions | 628 | 164 |
| No supplied competition resource pack listed in any period, period data present | 311 | 123 |
| Above subset also matching the OPL Archive's Originals by solo artist and title | 110 | 46 |
| Above 311 matching the OPL Archive's Covers instead | 2 | 2 |

The snapshot contains 218 OPL2, 106 OPL3 and 412 legacy AdLib entries. We grouped all 736 by shared provider artist ID or exact normalized title before filtering, including all credited collaborators. These counts omit undisclosed aliases, collaborators, common sessions and unrecognized work relationships. A supplied pack can consist solely of written instructions. Excluding listed packs is a conservative feasibility screen. The duration is the provider's listed length and still needs a one-pass arrangement check. Two entries even list MP3 as the source filename. Parsing literal filenames recovered two module extensions after number signs in their titles. An independent traversal of the group graph and extraction of the catalogue links reproduced 311 leads and both matched ID lists. [Public metadata API](https://battleofthebits.com/api/v1/entry/list/0/250?filters=format_token~opl2&sort=id) · [OPL Archive](https://opl.wafflenet.com/)

The 110 matches contain 49 artist accounts across 46 groups. Of those works, 37 are labelled A2M, 25 RAD, 20 S3M, 17 MPTM, nine AMD and two Furnace. Two limited historical identity comparisons found zero exact normalized credited-name or work-title overlaps with either 328 pinned RWC annotation rows or both metadata layers of the 24 selected private pilot tracks. The comparison used the same bound inventories as the [earlier cross-check](source-group-and-transfer-audit-20261123.md) and included composer, performer and available remixer credits. Freshness remains unverified across the full research history.

## What changed at the item level

Chip Champion's *biomech 3* has a RAD source filename and a listed duration of 161.02 seconds. The author's entry describes composing with RAD patterns, the OPL Archive lists the work as an OPL2 original, and the competition's published album credits the same artist and title at 2:41. Its album page links CC BY-NC-SA 4.0. This corroborates a finished composition and provides a concrete source for instrument and renderer checks. The album license applies to the published release. Rights for the particular project and for distributing learned weights remain separate questions. [Author's entry](https://battleofthebits.com/arena/Entry/biomech%2B3/10433/) · [Competition release](https://battleofthebits.bandcamp.com/album/summer-chip-iii) · [OPL Archive](https://opl.wafflenet.com/)

Snyderman's *OPL2.1* and Spring's *Mighty Kingdom of Stupidum* both passed the filename, duration, attribution and competition-pack checks. The OPL Archive lists both under Covers. Hold both aside pending underlying-work identification. The archive's VGM logs document previously released works and do not add new independent recordings. The catalogue match list preserves public entry IDs for replay. [OPL Archive](https://opl.wafflenet.com/) · [Matched public identifiers](opl-project-metadata-20261123.json)

The publication policy describes a noncommercial share-alike license for third parties and separate redistribution terms for the organizer. The catalogues therefore do not establish permissive weight distribution. The first three RAD author lookups in hash order were *biomech 3*, *OPL2.1* and birdrun's *Lo-Fi 16-bit Beats to Chill and Relax to*. Direct detail lookups were unavailable; indexed author text and the organizer's release corroborated the first, the catalogue contradicted original-work status for the second, and the third lacked an exact solo artist-title match. The Furnace project's own demo policy also reserves the songs' rights to their authors. [Competition license policy](https://battleofthebits.com/lyceum/View/BotB%20CC%20License) · [Furnace demo policy](https://github.com/tildearrow/furnace/blob/eac8c031584499a1cad77b9d54ff3a7955405ff9/demos/README.md)

**Qualification decision.** Prioritize the 46 corroborated groups for source review. A useful first check is RAD instrument type. Its native format supports both FM and external MIDI instruments, so the project suffix cannot establish a self-contained render. Establish per-project rights, verify instrument sources and revision, identify a complete playthrough and renderer, and reconcile source identities with the other splits before admitting any group. All these works currently represent one candidate electronic production stratum. Zero groups were allocated or scientifically scored. [RAD technical specification](https://www.3eality.com/productions/reality-adlib-tracker/docs)

## Replay

The four projected API pages and the OPL catalogue HTML are retained on schwarz. API page records include the request URL and original response digest. The [summary](opl-project-metadata-20261123.json) binds both snapshot digests. The offline command reads only these captured records. The script's optional capture mode is solely for the three public API lists.

```sh
snapshot=/Volumes/schwarz/lossytrace/validation/botb-opl-project-metadata-20261123-001
python3 -B scripts/music_verdict_opl_sources.py "$snapshot" \
  --opl-catalogue "$snapshot/opl-catalogue.html"
```
