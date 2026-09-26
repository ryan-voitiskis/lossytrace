# ODAQ clean-reference acquisition authorization - 2026-08-13

**Status:** narrow CC BY/CC0 development track selected; acquisition of the 16
exactly frozen clean `reference.wav` members authorized; processed conditions,
published scores, stimuli, metrics, and listener collection remain unauthorized

## Responsible-human decision

The responsible human selected the narrow ODAQ CC BY/CC0 development path,
accepted its one-provider, development-only limitation and bound attribution
requirements, and authorized acquisition only of the 16 clean reference
members in the exact metadata freeze. This decision does not authorize the
provider's processed conditions or published scores and does not make ODAQ
independent transfer or final-validation evidence.

The machine authorization duplicates the exact frozen provider and reference
arrays and binds the parent freeze at SHA-256
`1a39f50013a4274f60ca7c1771ebad22dcafda6950db87d2ffe4acdfb58ab0e7`.
The existing extractor must additionally require this authorization file to be
committed and clean before making a provider request.

## Playback declaration

The declared chain is a macOS computer feeding an RME ADI-2 Pro FS over USB and
a stereo pair of Adam Audio T7V active monitors. The room is a domestic living
room with bass traps, a soft sofa, carpets, rugs, and curtains. Spatial audio,
EQ, loudness normalization, crossfade, communications ducking, headphone
accommodations, and other audio effects were declared off.

Live system inventory observed the RME as the current default two-channel
output on macOS 26.6.1, currently at 96 kHz. That rate is an observation, not
session qualification. Before listening, the frozen player must require exact
agreement between the stimulus rate, AudioContext rate, and declared CoreAudio
rate. Quiet-session conditions, fixed listening position, channel correctness,
and comfortable conservative calibration remain to be observed.

The first bounded acquisition attempt stopped after the exact size and CRC
check because the first authorized reference uses 32-bit IEEE-float WAV rather
than integer PCM. Acquisition may preserve and explicitly inventory that
lossless source representation, but the version-1 browser delivery boundary
continues to reject float WAV. Any listening stimulus therefore requires a
separately frozen deterministic conversion to integer PCM; no browser or
platform decoder may convert it implicitly.

After seven references were journaled, the next member was observed as
WAVE_FORMAT_EXTENSIBLE with the canonical 24-bit integer PCM subtype. The
acquisition parser may record that container and its channel mask explicitly;
the version-1 browser remains unchanged. To permit safe resume across these
implementation-only corrections, the acquisition journal identity is frozen
to SHA-256 `a328198da9bf4e2c6061db69c4fd961884360074a90b432f53b0ebf739cbf5d3`,
the exact authorization under which the successful journal began. Provider,
reference inventory, and every access boundary remain unchanged.

## Remaining boundary

This authorization enables only bounded reference acquisition. It does not
authorize excerpt selection by listening, actual-codec or control generation,
perceptual metric execution, playback qualification, degradation ratings,
participant contact, response storage, or human collection. Those require
separate score-blind successor gates.
