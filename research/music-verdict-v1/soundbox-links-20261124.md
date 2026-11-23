# Recovering complete game arrangements from the offline snapshot

The score credited to Mark Sparling in *Submersible Warship 2063* reproduces the game's 96-second, eight-channel arrangement. All 898 note events, their positions and pitches, instrument parameters, scheduled patterns and effects agree with the shipped score. The four-second cue in the same file is a different arrangement. The project names Sparling as composer, while its MIT notice names developer Jerome Lecomte. The retained records establish composer and work identity. They leave the composer-specific grant for this use unresolved. This work received no render or allocation. [Composer credit and editable score](https://github.com/js13kGames/submersible-warship-2063/blob/6c234b88cf0867d712f17aab362fc974e648285a/README.md) · [Shipped score](https://github.com/js13kGames/submersible-warship-2063/blob/6c234b88cf0867d712f17aab362fc974e648285a/src/js/songs.js)

The *Miami Mice* notes contain two music projects and two sound effects. The project labeled “synthwave” matches all 1,193 note events and the full four-channel program in the shipped game music. The other three URLs do not match that music file. The developer describes the soundtrack as original, credits DerBenniBanni for code, art and design, and names SoundBox under music. The MIT notice names Christoph Schansky. We retained a private software render. Assigning a named composer or an independent study group from those credits would require more evidence. [Project and credits](https://github.com/js13kGames/miami-mice/blob/c5de969696e94c35a635f97f31faa94cb4a6b32c/README.md) · [Editable projects](https://github.com/js13kGames/miami-mice/blob/c5de969696e94c35a635f97f31faa94cb4a6b32c/music_nd_Sound.md) · [Terms](https://github.com/js13kGames/miami-mice/blob/c5de969696e94c35a635f97f31faa94cb4a6b32c/LICENSE)

For comparison, the same reader recovered the previously matched *Island Not Found* program and the 160-second *Witchcup1276* race arrangement. The latter matches despite being an explicitly credited cover of *Furatum Alci Provinciam*. Its publication notes describe permission for game use. Exact agreement can establish which arrangement shipped while leaving composition lineage and permission for a research corpus open. [Witchcup credits](https://github.com/js13kGames/witchcup1276) · [Seven editable-project comparisons](soundbox-links-20261124.json)

## What the Miami Mice file represents

Two fresh Node processes played one pass of the retained score into the author's bundled synthesizer in memory. Both produced the same 4,586,816-frame WAV, a 104.01-second stereo 44.1 kHz/16-bit render. Both included the project and player notices. We selected seed 20260927 for the player's noise oscillator and used its integer WAV export. FFmpeg independently reproduced the render's native PCM hash. Nothing was played through a sound card. [Render receipt](miami-render-20261124.json)

The same player's AudioBuffer method divides each integer mix sample by 65,536. Its WAV export clamps the mix to ±32,767 and writes those integers directly; nominal 16-bit playback scales by 32,768. We checked all 9,173,632 channel samples against both methods on the same mix. The peak integer magnitude was 11,054 and zero samples clipped. For this performance the WAV amplitude is exactly twice the float-buffer amplitude, a 6.02 dB difference. Either output has a known local synthesis history. They belong to the same work. The snapshot does not establish the final gain a player would hear in the game. [Player and export methods](https://github.com/js13kGames/miami-mice/blob/c5de969696e94c35a635f97f31faa94cb4a6b32c/src/game/lib/soundbox/soundboxplayer.js)

The five locally rendered works now comprise four previously documented named-composer constructions and this additional project-credited render. All are electronic game music. Zero works were fitted, scored or allocated here. Counts of game scores cannot establish acoustic or vocal coverage.

## Offline replay

The Python reader handles the two retained SoundBox format versions in their original layouts. It hashes the expanded timeline and compares it with the previously bound independent JavaScript parser's result for each published game score. The Node runner executes only the digest-bound music and synthesizer modules. Use Node 24.14.0 and a new output directory.

```sh
set -e
base=/Volumes/schwarz/lossytrace/validation
src="$base/js13k-score-metadata-20261124-001"
python3 -B scripts/music_verdict_soundbox_links.py "$src" | cmp - research/music-verdict-v1/soundbox-links-20261124.json
node --random-seed=20260927 scripts/music_verdict_miami_render.mjs "$src/miami-mice" "$base/miami-mice-replay"
diff -qr "$base/miami-mice-replay" "$base/miami-mice-render-20261124-002"
```
