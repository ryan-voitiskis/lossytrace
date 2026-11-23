# Independent sources in two live-recording collections

The Blue Funk collection has 71 dated sessions and The Ship’s Cat has 81. Every session in both collections names the same recordist and transfer engineer, Lucas Krazywaffle. All 152 descriptions also credit a bassist named Lucas, including one shared bass credit. Together, the band names, personnel and production credits justify conservatively linking these sessions for allocation until fuller identities are available. A recordist credit alone would be insufficient to establish a shared performer. Of these records, 115 specify CC BY-NC-SA 4.0 and 37 lack an item-level license URL. The two collection permission statements cover posting or circulation. Permission for a distributable learned artifact remains unresolved. [Collection and item counts](lma-session-series-20261124.json) · [Blue Funk collection](https://archive.org/metadata/BlueFunk) · [The Ship’s Cat collection](https://archive.org/metadata/TheShipsCat)

The Ship’s Cat’s January 7, 2021 jam has a more useful source declaration than the previously examined June 10 item. It documents the DR-07 built-in microphones, a 24-bit/48 kHz WAV on the recorder’s SD card, and tracking and peak normalization in Audacity to a 24-bit/48 kHz WAV. The catalogue lists the complete 1,063.04-second WAV as original and the same-duration FLAC as its derivative. Blue Funk’s August 2, 2013 session lists two original WAVs with linked FLACs and documents a 24-bit/48 kHz capture, a 10 dB gain change in Audacity and a 24-bit WAV export. Its final rate is unstated. Both records are amplified ensemble performances. All file hashes and lengths in the receipt are archive declarations. No audio was retrieved and zero groups were allocated. [January 2021 item](https://archive.org/metadata/ShipsCat2021-01-07) · [August 2013 item](https://archive.org/metadata/BlueFunk2013-08-02)

For vocal material, Sanidha's five Carnatic concerts provide a concrete illustration of artist grouping. The published credits link concerts 1, 3 and 4 through two returning musicians, and concerts 2 and 5 through a third. That leaves at most two performer-independent groups before checks for other shared works or sessions. Access requires contacting the team and using guest credentials. Saraga’s authors list the distributed stereo concert mixes as 128 kb/s MP3. Neither collection supplies verified offline negative examples for this experiment. [Sanidha recordings and credits](https://ccml.gtcmt.gatech.edu/data/Sanidha/) · [Saraga release formats](https://mtg.github.io/saraga/organization.html)

Replay the item and collection counts from the six retained JSON responses with the standard library.

```sh
python3 -B scripts/music_verdict_lma_session_series.py \
  /Volumes/schwarz/lossytrace/validation/lma-acoustic-sessions-20261124-001 \
  | cmp - research/music-verdict-v1/lma-session-series-20261124.json
```
