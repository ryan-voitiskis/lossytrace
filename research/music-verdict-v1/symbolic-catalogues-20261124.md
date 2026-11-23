# Can score catalogues supply independently authored finished music?

Two catalogue checks found potential source leads. All group counts below describe links in metadata. Verifying a particular work still requires rights, work and creator identity, an intended finished production, a traceable rendering chain and reconciliation with the historical inventory. The audits examined metadata only. No new score or audio entered a study partition.

## Battle of the Bits

Of 365 JummBox and 43 MML entries, 327 had a credited author, a text-score filename, a listed duration of at least 30 seconds and a competition outside the two documented cover events. Across the complete index for both formats and the three earlier FM formats, 139 provisional groups intersected those 327 works. Fifteen also contained a work from the earlier FM shortlist. The combined shortlist has 436 entries in 170 groups. Shared credits, equal normalized titles and previously documented cover relationships connect entries across formats. Some equal titles may be coincidences. Unrecorded aliases or retitled arrangements could connect further groups. [JummBox format](https://battleofthebits.com/lyceum/View/jummbox%20%28format%29/) · [MML format](https://battleofthebits.com/lyceum/View/mml%20%28format%29) · [Entry IDs and counts](botb-symbolic-20261124.json)

For project review, 60 JummBox entries and 11 MML entries also lacked a listed competition pack. The packs themselves were not inspected. The filename and published duration cannot establish the score contents, rights to incorporated material or a complete playthrough. The provider publishes entry licensing terms and competition rules. [Provider terms](https://battleofthebits.com/lyceum/View/BotB%20CC%20License) · [Rules](https://battleofthebits.com/lyceum/View/Rules)

## PDMX

The release index contains 254,077 scores. The publisher flags 31,221 copyright conflicts. Requiring a consistent CC0 record and a positive originality flag left 7,549. Further checks for non-draft status, no custom audio or paywall, the valid subset, a representative arrangement, at least one note and 30 seconds of listed music left 6,161. Their archived raw records agreed on originality and license and supplied 3,956 uploader accounts. The audit verified the official checksums of both the index and raw metadata archive. [PDMX release](https://zenodo.org/records/15571083) · [Dataset authors' documentation](https://github.com/pnlong/PDMX) · [Audit results](pdmx-metadata-20261124.json)

Across the full catalogue the account, provider song ID and dataset cluster links reduce the screen to 920 connected groups. Also connecting shared normalized composer strings gives 883. These are sensitivity checks. A prolific arranger who uploads other composers’ works can join distinct creators into a single component, while disconnected aliases can inflate the count. Of 376 works with matching uploader/composer text or a narrow first-person composition statement and no adaptation keyword, the two graphs yield 70 and 65 groups respectively. The additional English-language game or soundtrack keyword screen matched zero of those 376. This measures the particular wording in the records.

Reading the archived descriptions explains why these counts cannot establish finished-music capacity. One score passing the non-draft flag is expressly a rough draft for marimba. Another was composed for harp and subsequently adapted for piano. A third passed the originality flag while explicitly crediting a transcription of a visual-novel composition to a different person. Rendering these scores through a common synthesizer would document a new realization. The metadata reviewed here supplies no basis for treating those realizations as the creators’ finished recordings. The tracker shortlist has the more direct path to a verifiable, composer-intended production. [La Luna](https://musescore.com/user/137765/scores/5928613) · [Hergesell, op. 10](https://musescore.com/user/33541111/scores/5855750) · [Lolor](https://musescore.com/user/31187917/scores/5917401)

## Offline replay

```sh
set -e
base=/Volumes/schwarz/lossytrace/validation
python3 -B scripts/music_verdict_botb_symbolic.py "$base/botb-symbolic-metadata-20261124-001" \
  "$base/botb-opl-project-metadata-20261123-001" | cmp - research/music-verdict-v1/botb-symbolic-20261124.json
python3 -B scripts/music_verdict_pdmx_metadata.py "$base/pdmx-index-20261124-001" \
  | cmp - research/music-verdict-v1/pdmx-metadata-20261124.json
```
