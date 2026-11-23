# Finished game music with editable scores

Two composers published playable BeepBox arrangements with their game music. The public source of a future PCM render can be bound to the exact authored notes, instruments and arrangement. This gives stronger evidence about the signal chain than a downloadable WAV alone. The present review decoded notation only. It contributes **at most two candidate artist groups** from one synthesis platform and **zero allocated groups**. [Four Original MIDI Loops](https://opengameart.org/content/four-original-midi-loops) · [Random Retro-ish Music Tracks](https://opengameart.org/content/random-retro-ish-music-tracks) · [Author's description of the BeepBox song format](https://github.com/johnnesky/beepbox)

| Author credit | Item license declaration | Editable scores recovered | One authored pass ≥30 s | Last scheduled note ends ≥30 s |
| --- | --- | ---: | ---: | ---: |
| tapatilorenzo | CC0 1.0 | 4 | 4 | 4 |
| cubee | CC BY 4.0 | 23 | 20 | 19 |

The first author identifies all four pieces as originals. The second describes 41 published tracks and supplies a text index containing 23 BeepBox URLs and three explicitly missing scores. This review covers only the scores actually supplied. Restoring missing projects from an encoded copy would lose the construction history.

*The Lab* has 20 bars, a 64-second arrangement and a note in the final bar. It uses chip, pulse-width and noise instruments. *high loop* illustrates the risk of inferring complete music duration from editor length. Its 16 bars span 59.08 seconds, but the last note ends 14.77 seconds into bar four. This observation puts its intended playthrough in question. It introduces no new evaluation rule about silence. *gorio* and *cyborg* have different score bytes and instrument inventories, but identical per-channel pitches, note timing and bends, key, tempo and loop boundaries. Treat them as related works even if they appear under different credits elsewhere. [Individual source commitments and measurements](beepbox-arrangements-20261123.json)

## Verification

We decoded each score with the pinned BeepBox 4.2.0 package and separately with a source build for its native score format. BeepBox 3.0.13 read the 23 version-8 scores and BeepBox 4.0 read the four version-9 scores. Both paths agreed on the hash of the sequenced note data for every score. That hash omits timbre, volume and effects and can flag exact arrangement matches. Distinct hashes cannot establish independent composition. A separate reader extracted the compact source header directly and reproduced the tempo, beats per bar, bar count, loop start, loop length and resulting duration for all 27 scores. [BeepBox 3.0.13](https://github.com/johnnesky/beepbox/tree/1401fcf36520fcc1c489b3c9de48bf2699930524/synth) · [BeepBox 4.0](https://github.com/johnnesky/beepbox/tree/5c57650cabbe8dba6e21a533bb4ce7572f9000ac/synth) · [Pinned decoder package](https://www.npmjs.com/package/beepbox/v/4.2.0)

The published scores specify only native BeepBox instruments. None references an external sample library. The 4.2.0 synthesis implementation uses random values for some noise and phase operations. The score alone therefore cannot commit a unique PCM byte sequence. Before creating study material, bind a renderer revision, sample rate, PCM conversion, repeat count and reproducible random initialization. Verify independent renders by decoded PCM hash. Resolve completeness, identity links across providers, historical freshness and rights for the intended use before allocation. The compiled decoder checks establish note agreement across software releases. Audio equivalence across releases is untested.

The historical repository search at `d28f9cb` found neither exact artist handle in tracked benchmark, research or documentation text. Private source identities, aliases, previously consumed works under different names and sealed material were outside that text search. The site lists Codex among the agents it disallows in its robots file. We identified that restriction after fetching the two submission pages, the linked text score list and one catalogue page. We stopped site discovery and used the captured records for the offline work. Future automated intake should use an authorized source. [Site access policy](https://opengameart.org/robots.txt)

## Offline replay

The snapshot on schwarz contains both submission pages, the score index, the pinned npm package, and the upstream TypeScript sources and compiled decoders. In each of the snapshot's `legacy` and `v4_0` source directories the build command was `tsc --module commonjs --target ES2020 --skipLibCheck --outDir upstream-build synth.ts`. We used the upstream lockfile compiler versions, respectively 4.0.3 and 4.4.4. The replay verifies the exact package and build digests before decoding. No score links are followed. Run from the repository root with Node and tar. [Offline reader](../../scripts/music_verdict_beepbox_sources.mjs)

```sh
snapshot=/Volumes/schwarz/lossytrace/validation/beepbox-project-review-20261123-001
node scripts/music_verdict_beepbox_sources.mjs "$snapshot" \
  | cmp - research/music-verdict-v1/beepbox-arrangements-20261123.json
```
