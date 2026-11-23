# Capacity of the retained Commons FLAC category

At most **21 independent finished-music groups** can come from the 146 direct members in this category snapshot under the frozen source rules. The study requires at least 30 evaluation groups in each of at least three production/provider strata. The entire category therefore cannot fill one stratum by itself, even if every remaining source passes the capture-chain, identity and rights checks. These figures apply to the retained category snapshot. The wider Commons catalogue and the original producers' catalogues are separate discovery routes. [Page dispositions](commons-capacity-20261124.json) · [Study design](../../docs/research/music-verdict-successor-20260927.md)

| Disposition | Files |
|---|---:|
| All direct members in the saved category | 146 |
| Outside the native rate, duration or both, per provider STREAMINFO | 24 |
| Native format and duration within scope | 122 |
| Explicit excerpt, interview/discussion, memory exercise, environmental recording or bird recording | 17 |
| Potentially in scope, including unresolved cases | 105 |

Of the remaining files, 90 fall into six shared performing-artist groups. C418 accounts for 29, HOME for 26, baritone Hans Duhan for 24, Resonant Bodies for seven, the Harmonica choir for two and Kitty for two. Some *Winterreise* pages list Franz Schubert in the artist field. Their credits or descriptions identify Duhan as the performer. The other 15 files each receive a separate slot in the ceiling, even if some later prove ineligible or connected. Even dropping the choir, Kitty and Resonant Bodies groupings, the three largest credits alone give a ceiling of 29. Additional source-work or session links can only decrease the count. Both Harmonica items declare an own recording and CC BY-SA 4.0. Their stored FLAC headers describe stereo 44.1 kHz/16-bit delivery. The snapshot does not establish the microphone-to-file path. [Winterreise recording credit](https://commons.wikimedia.org/?curid=42262740) · [Tourdion](https://commons.wikimedia.org/?curid=41288769) · [Uti vår hage](https://commons.wikimedia.org/?curid=41289142)

## Can archived MP3s provide ready-made matched pairs?

The RareTunes subset lists 252 original WAVs, 251 explicitly linked FLACs and 372 explicitly linked VBR MP3s. All 251 FLAC durations agree with their WAV parent within two seconds. **62 MP3 durations differ by more than two seconds**, one per affected WAV. Each of those 62 WAVs also has another MP3 and a FLAC with a concordant duration. Fourteen affected originals were in the earlier 40-item catalogue shortlist. For *When First I Went to Caledonia*, the WAV is listed at 145.91 seconds and the two sibling MP3s at 2:25 and 8:19. The stored records cannot establish whether the discrepancy lies in duration reporting, a stale relationship or the files themselves. [Item metadata](https://archive.org/metadata/raretunes_285_when-first-i-went-caledonia) · [All affected items](archive-pair-durations-20261124.json)

The corresponding Potpourri subset has 137 WAVs with 137 linked FLACs and 137 VBR MP3s. Every listed derivative falls within the same duration tolerance. Concordant metadata helps prioritize later checks. Both the declared upstream history and an exact controlled encode/decode from the verified PCM are still needed for the frozen study. The two-second window here accommodates the mixed precision of the catalogue's durations. It is a metadata discrepancy screen, not an alignment tolerance for any training or evaluation audio.

Both checks read already retained JSON only. No source was assigned to a partition.

```sh
set -eo pipefail
base=/Volumes/schwarz/lossytrace/validation
python3 -B scripts/music_verdict_commons_capacity.py "$base/commons-music-metadata-20261123-001" \
  | cmp - research/music-verdict-v1/commons-capacity-20261124.json
python3 -B scripts/music_verdict_archive_pair_durations.py "$base" \
  | cmp - research/music-verdict-v1/archive-pair-durations-20261124.json
```
