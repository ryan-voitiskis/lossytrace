# A finished Game Boy score with a verified PCM rendering

Beatscribe released five editable hUGETracker scores in the free demos for the composer's Game Boy asset packs. The repository declares CC0 and identifies the composer. All five projects also credit Beatscribe internally. We privately constructed one work, *3am Skyline*, from the tracker's notes and instruments and verified direct and codec-derived FLACs. This adds a fourth finished work from a fourth credited composer, using a third rendering engine. Formal study allocation remains at zero. [Creator's rights statement](https://github.com/Beatscribe/homebrew_vgm/blob/5a82f88b87bb442499685c494b7a96278121b4c7/README.md) · [Creator's demo pack](https://github.com/Beatscribe/homebrew_vgm/tree/5a82f88b87bb442499685c494b7a96278121b4c7/GB/free_demos)

## What the score files establish

The five version-5 UGE projects each contain two pulse-channel sequences, a wave-channel sequence and a noise-channel sequence. The instrument data consist of hardware parameters and 16 tables of 32 four-bit waveform values. All 16 custom routine slots in each project are empty. The sequential order lists contain no jump, pattern break or routine call. The reader checked every file against the composer's pinned Git object. [Score records](uge-sources-20261124.json) · [GB Studio's UGE reader](https://github.com/chrismaltby/gb-studio/blob/c367dee2ffec5cb7870115aee66e85ed4667b94f/src/shared/lib/uge/ugeHelper.ts)

| Project | Pattern orders | Note events | One pass at 64 ticks/s |
|---|---:|---:|---:|
| 3am Skyline, no drums | 13 | 205 | 91 s |
| Beats by Beatscribe, faster | 8 | 676 | 24 s |
| Beats by Beatscribe | 8 | 676 | 32 s |
| Platformer demo | 6 | 710 | 42 s |
| Seaside Village | 8 | 382 | 56 s |

Both versions of *Beats by Beatscribe* have identical hashes for the ordered sequence of position, channel and pitch. Their speed commands differ. Counting those projects separately would count one arrangement twice. The other durations in the table are calculated from the notation and speed commands. Only *3am Skyline* has an independently measured WAV duration in this check.

## Direct export and matched encodes

The selected project has an explicit internal title, a release context and a corresponding WAV filename in the author's publication tree. We used the editable score. A locally served copy of GBS Music opened it and exported one loop as 16-bit stereo PCM at 44.1 kHz. The author-supplied waveform was never requested. This establishes the history of our performance. Equivalence to the author's own WAV remains untested. [Editable score](https://github.com/Beatscribe/homebrew_vgm/blob/5a82f88b87bb442499685c494b7a96278121b4c7/GB/free_demos/music_uge/bs-cyb-city-night-nodrum.uge) · [Editor's offline capability](https://chrismaltby.itch.io/gb-studio/devlog/1495872/gbs-music)

Two fresh Chrome processes using the same retained editor build produced identical WAV bytes. Each contains 4,014,080 stereo frames, or 91.0222 seconds. The exported interval extends 980 frames beyond the 91-second score calculation. We retained the complete export. During replay an attempted format selection left the editor on its MP3 default. The downloaded file was identified, set aside, and excluded from both WAV inputs and every construction. The successful repeat explicitly checked the selected format, loop count, download extension, file header and digest.

The direct FLAC and the six FLACs decoded from MP3 or AAC-LC reproduced their intended integer PCM with both FFmpeg and libsndfile. All six intermediate decodes had the expected original frame count. At one second, the midpoint and one second before the end, all 18 left-channel comparisons peaked at zero-frame lag. Minimum peak correlation was 0.9959. Two complete codec constructions reproduced all 15 retained files, including credits and the construction receipt. [Codec settings, packet measurements and hashes](uge-construction-20261124.json)

## Independence and source selection

Treat the five projects as one composer group. The source pack, platform, arrangement versions and the no-drums variant are identity references for future intake. A metadata check of the composer, the credited handle and the title or filename of *3am Skyline* found zero exact normalized matches in the 328 pinned RWC rows, 48 tag layers of the 24 private pilot tracks, 1,144 previously reviewed competition entries or 254,077 PDMX index rows. These checks cover only those recorded fields and spellings. Cross-collection aliases, session identities and the remaining historical inventories still need reconciliation. No file was fitted or scored.

The organizer's JummBox album also corroborates 14 works in the prior tracker shortlist. All 14 track titles and credited artist sets match entries in competition 9341, including the collaboration involving two artists who also contributed solo tracks. The format permits multiple editor variants, including variants with sample import. The publication establishes that these tracks were released. Qualifying their signal chains still requires access to the authored project. [Organizer's album](https://battleofthebits.bandcamp.com/album/jummbox) · [Competition format](https://battleofthebits.com/lyceum/View/jummbox%2B%2528format%2529)

A separate search of three GitHub topics returned 76 distinct repositories, of which 36 carried one of the six source-review license labels. A partial scan of 17 complete repository trees found 195 tracker file occurrences, all in MOD format, representing 102 distinct Git blobs. All 93 modules in one community asset collection were byte-identical to entries in another repository. The community credits identify a remix of *Darkstone* and describe *Park Music* as another version of *FridgeMusic*. Different bytes can still belong to one work. Prioritize explicit game-use and composer credits, including the original *Darkstone* used in *6rooms*. The remaining 19 trees were deferred as the unauthenticated metadata API approached its rate limit. No MOD payload or published recording was fetched. [Tree audit](gb-project-index-20261124.json) · [Collection credits](https://github.com/DeerTears/GB-Studio-Community-Assets/blob/7583b5a4235ffa890f002cefb82a7eaac0c2d816/Music/Readme.md)

## Offline replay

The score and editor snapshot on schwarz is `beatscribe-tracker-20261124-001`. The editor asset manifest binds 53 files. The reproducibility target for the WAV is SHA-256 `e33991eb70e88b5157427ec1fdf6637d6359f572a25d2164f39a6023fd0db410`. To repeat the export, serve the snapshot's `web` directory on localhost and open it in a fresh Chrome profile (observed version 157.0.8103.80), with external network requests disabled and audio muted. Open the local UGE via **Open File**, select **Export As… → WAV**, set **Loops** to **1**, verify WAV is selected and use **Export Song**. Compare the result with the bound WAV digest. The private snapshot retains both successful exports and their editor evidence. The paired construction only accepts those two exact WAVs and the bound editor build.

```sh
set -e
base=/Volumes/schwarz/lossytrace/validation
src="$base/beatscribe-tracker-20261124-001"
python3 -B scripts/music_verdict_uge_sources.py "$src" | cmp - research/music-verdict-v1/uge-sources-20261124.json
python3 -B scripts/music_verdict_gb_project_index.py "$base/gb-project-index-20261124-001" | cmp - research/music-verdict-v1/gb-project-index-20261124.json
out="$base/uge-codec-replay"
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_verdict_uge_construction.py "$src" "$out"
cmp "$out/construction.json" research/music-verdict-v1/uge-construction-20261124.json
```
