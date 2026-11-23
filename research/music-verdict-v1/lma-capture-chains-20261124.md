# Live recordings with a documented capture chain

**This Close!’s performance of “I’ll Take Two” is a candidate live-band control with a documented recording and transfer chain.** It is track one of the 28 February 2025 set at Joe’s Bar in Boulder Creek, California. The indexed original FLAC runs 295.03 seconds. The set notes identify the piece as a band original and credit Rob Jenkins, Pete Catizone and Jim Anderson as the performers. Jenkins recorded the mixer output directly to its SD card, then mastered the WAV in Studio One Pro 7 and exported tracked 16-bit FLACs. Anderson handled final tagging. The reference to MP3tag in the notes describes editing tags. [Recording record](https://archive.org/metadata/ThisCloseBand2025-02-28.sbd.flac16) · [Band’s transfer notes](https://archive.org/download/ThisCloseBand2025-02-28.sbd.flac16/ThisCloseBand2025-02-28.SBD.JoesBar.txt)

The transfer notes name the PreSonus StudioLive AR16c. Its onboard SD recorder captures the stereo main mix as 24-bit, 44.1 kHz WAV. Those specifications corroborate the initial capture. The mastered FLAC still needs direct verification of sample rate and channels. The Archive lists the track’s file SHA-1 as `d5c4b1c9e8635e404958ac5032de84c9a4db5c77`. The band’s separate fingerprint sheet lists decoded-audio MD5 `7c1fbd5531083364200c8e9b625eeebe`. The 22 listed fingerprints match all 22 original FLAC filenames. We verified the two text documents against their Archive file digests. Both track hashes remain provider declarations until audio can be checked. [PreSonus specifications](https://www.presonus.com/products/studiolive-ar16c-analog-mixer) · [Manufacturer’s manual, SD recorder specifications](https://www.fmicassets.com/Damroot/Original/10015/OM_2779200101_AR12c_EN.pdf) · [Fingerprint sheet](https://archive.org/download/ThisCloseBand2025-02-28.sbd.flac16/ThisCloseBand2025-02-28.SBD.JoesBar.ffp)

The item carries CC BY-NC 4.0. The collection quotes band member Anderson permitting noncommercial circulation. These records support prioritizing the track for private research review. Commercial or unrestricted weight distribution remains uncleared. Exact normalized searches of the track title, band and three performers found zero matches in the 328 pinned RWC rows and the 48 tag layers from the 24 selected private-library tracks. Full historical identity reconciliation remains outstanding. The set mixes originals and covers, and all tracks share a recording group. [Collection permission](https://archive.org/metadata/ThisCloseBand) · [Historical inventory bindings](source-group-and-transfer-audit-20261123.md)

## Scope of the search

The two retained October catalogue pages contain 1,495 unique items with populated license fields. We searched the source and lineage fields for a WAV or WAVE token and the text FLAC. A WAV token may sit beside digits in technical shorthand. CDWAV alone never matches. The table counts item declarations. This text screen misses recording histories expressed differently or documented only in a text attachment.

| Item license URL family | Index entries | Entries matching the chain text |
| --- | ---: | ---: |
| BY, BY-SA or CC0 | 398 | 97 |
| BY-NC or BY-NC-SA | 226 | 15 |

The 112 matches have 20 distinct case-folded creator labels. Within each label we selected the lowest SHA-256 of the UTF-8 prefix `lossytrace-lma-chain-v1:` followed by the item ID. We inspected all 20 recording records and their 17 artist collection policies. Three responses were already retained and 34 came from the public metadata API. These recordings list 355 original FLACs, 343 at least 30 seconds long. They include introductions, stage conversation, anonymous segments and whole sets. Duration and archive format alone cannot establish a complete song. [October index and bindings](source-intake-observation-20261005.json) · [Per-record counts](lma-capture-chains-20261124.json)

Two records credited respectively to Matt Berninger and The National document the same solo artist’s 2025 tour. Three more records carry three creator labels for performances linked through the Lane family. Ben Lane connects the 2024 Flat Earth set to the late-night party jam, and Wayne Lane Jr. and Quinn Lane connect the jam to the opening set. Those two corrections alone reduce the 20 selected recording records to **at most 17 independent groups**. That falls below the required 30 for one evaluation stratum even before further review. The bound applies to the 20 selected items. Other records, including some sharing a catalogue creator label, may represent different performers. [Dublin](https://archive.org/metadata/NTL_MB2025-08-22.mk41v) · [Utrecht](https://archive.org/metadata/NTL_MB2025-08-31.mk4v) · [Flat Earth](https://archive.org/metadata/lf2024-10-01) · [Party opening](https://archive.org/metadata/lf2026-09-05) · [Late-night jam](https://archive.org/metadata/lf2026-09-05.f)

Two further cases illustrate the remaining screening work. Moon Hollow’s submission identifies all four performers but delivers one 3,228-second soundboard set without track boundaries in its file list. The Ship’s Cat documents its microphones, analogue desk and WAV capture in detail, but the notes mention both 192 kHz and 96 kHz without documenting a supported-rate delivery. Neither has been allocated. [Moon Hollow record](https://archive.org/metadata/MH2025-03-23) · [The Ship’s Cat record](https://archive.org/metadata/ShipsCat2021-06-10)

## Offline replay

The retained capture index has SHA-256 `fde1ff176ba52c56a88b2de07a0e2c959325cd26e026153e7f8433c9eb235d28`. It binds the exact recording and collection responses. The offline screen verifies those digests, repeats selection and compares the complete fingerprint list to the original filenames. This pass used no audio, model outputs or sealed material. No source received an allocation.

```sh
set -o pipefail
python3 -B scripts/music_verdict_lma_chains.py \
  .tmp/music-verdict-v1/source-intake-20261005 \
  /Volumes/schwarz/lossytrace/validation/lma-capture-chain-review-20261124-001 \
  | cmp - research/music-verdict-v1/lma-capture-chains-20261124.json
```
