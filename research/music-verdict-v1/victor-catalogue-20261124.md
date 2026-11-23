# What the full Victor credits change about the shortlist

The 35 provisionally matched Victor transfers previously formed eight groups within the [Potpourri shortlist](victor-session-and-calibration-checkpoint-20261123.md). Applying the same performer and title matching across **all 5,882 retained catalogue records** connects the 35 into one group. Even leaving every newly introduced title edge out and retaining only the original shortlist's title edges produces two groups. Additional metadata can reveal collaborations between recordings considered for different partitions. [Full results and memberships](victor-catalogue-20261124.json)

| Credits used across the catalogue | Groups represented by the 35 shortlisted transfers | Group sizes |
|---|---:|---|
| Performing credits only | 3 | 30, 3, 2 |
| Performing credits across catalogue and exact work titles inside shortlist | 2 | 33, 2 |
| Performing credits and shared normalized title with at least one common composer credit | 1 | 35 |
| Performing credits and shared normalized title | 1 | 35 |

For example, Charles Harrison connects *A Little Bit of Heaven* to *When I Met You Last Night in Dreamland*. The Victor Orchestra connects that recording to *Gems from The Sultan of Sulu*, which also credits Walter Van Brunt. Van Brunt sings on *Don't Turn My Picture to the Wall*. The two end recordings belonged to separate shortlisted groups. Both middle records sit outside that shortlist. [A Little Bit of Heaven](https://www.loc.gov/item/jukebox-12879/) · [Dreamland](https://www.loc.gov/item/jukebox-190432/) · [The Sultan of Sulu](https://www.loc.gov/item/jukebox-130805/) · [Don't Turn My Picture to the Wall](https://www.loc.gov/item/jukebox-132102/)

Use the whole catalogue as identity evidence. Treat all 35 transfers as related for prospective allocation under the current title rule. A matching ensemble credit can span changes in personnel, and similar titles can describe different works. The table shows how much the result depends on title matching. Even the performer-only graph for **all** 5,882 records has just 148 components containing a named performing credit. Another 172 records have no identified performer under the existing role parser. The 148 includes groups with unverified source histories and terms. Every catalogue row lists only audio/mpeg among its audio MIME types. Any suitable PCM must come from a documented separate transfer. These counts concern the retained Victor extract and the 35 matched Potpourri transfers. The other 102 transfer leads and other labels remain unresolved.

The calculations read only the pinned LC metadata and retained transfer descriptions. An independent breadth-first traversal reproduced all four counts and every shortlist membership. The reference graph supplies zero audio or independent study observations. [Grouping script](../../scripts/music_verdict_victor_catalogue.py)

```sh
set -o pipefail
base=/Volumes/schwarz/lossytrace/validation
python3 -B scripts/music_verdict_victor_catalogue.py \
  "$base/commons-music-metadata-20261123-001" "$base/potpourri-session-audit-20261123-001/metadata.json" \
  | cmp - research/music-verdict-v1/victor-catalogue-20261124.json
```
