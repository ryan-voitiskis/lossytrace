# Correction to the FM project shortlist

One of the OPL Archive's 110 original-work matches is a documented cover. Jangler identifies the underlying composition of *hot bun crossing* as kfaraday's *lagomorph junction*. The entry also links two later arrangements, Bravoman's *Rabbit Connection* and dogsplusplus's *freshpretzel*. The latter two have different titles, author IDs and tracker formats. Preserve all four works as one lineage in future cross-collection checks. [Author's explanation and cover links](https://battleofthebits.com/arena/Entry/hot%2Bbun%2Bcrossing/21262/) · [Bravoman's entry](https://battleofthebits.com/arena/Entry/Rabbit%2BConnection/81658/)

The organizer describes both Decadent Decade events as cover competitions. We set aside all 26 OPL entries from those events for underlying-work review. Only *hot bun crossing* intersected the OPL Archive Originals shortlist. **109 leads remain, spanning 46 provisional groups and 23 competitions.** Shared competition membership is relevant to production diversity. The available evidence does not establish a common recording session for all entrants. The earlier count of 110 remains reproducible as a catalogue match count. Future source review uses the corrected list. [Competition rules](https://battleofthebits.com/lyceum/View/Decadent%20Decade) · [Recorded identities](opl-lineage-review-20261123.json)

For *biomech 3*, the provider's entry API confirmed the original filename and the separate preview field. A HEAD request to the provider's published original-project endpoint returned HTTP 403. The OPL Archive player fetches a register-log file for playback. We did not request that file or any preview. The 2013 publication predates the vendor's 2018 second-generation tracker release and is consistent with the earlier FM format, but the precise source revision, instrument configuration and single-playthrough duration remain unverified. No source was acquired or allocated. [Creator's entry](https://battleofthebits.com/arena/Entry/biomech%2B3/10433/) · [Tracker documentation](https://www.3eality.com/productions/reality-adlib-tracker/docs)

The offline replay preserves the original screen when the optional review is omitted. With the review, it emits the corrected list of entry IDs.

```sh
snapshot=/Volumes/schwarz/lossytrace/validation/botb-opl-project-metadata-20261123-001
python3 -B scripts/music_verdict_opl_sources.py "$snapshot" \
  --opl-catalogue "$snapshot/opl-catalogue.html" \
  --lineage-review research/music-verdict-v1/opl-lineage-review-20261123.json
```
