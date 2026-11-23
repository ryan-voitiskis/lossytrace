# Session identities and calibration mechanics

## Source independence

Of the 137 Potpourri transfers shortlisted in the [source audit](source-group-and-transfer-audit-20261123.md), 35 have one candidate Victor take in the Library of Congress metadata subset after matching catalogue number, normalized title and at least one credited performer. Shared performers and works connect these 35 transfers into eight provisional groups of sizes 25, 2, 2, 2, 1, 1, 1 and 1. Grouping common recording dates and places as an additional precaution yields the same membership. The other 102 leads remain outside this count. [National Jukebox dataset](https://data.labs.loc.gov/jukebox/)

| Cumulative screen | Transfers |
| --- | ---: |
| Shortlisted transfers | 137 |
| Explicit Victor catalogue number recognized | 64 |
| Number appears in the 5,882-row catalogue extract | 46 |
| Title also matches | 39 |
| At least one performing credit agrees | 37 |
| Exactly one take listed for the matching number and title | 35 |

For *At the Jazz Band Ball*, the matched record gives matrix B-21583, take 1, recorded on 19 March 1918. For *Depuis le jour*, the same matrix and credited singer occur on takes recorded in 1911 and 1913. *Dollar Princess Waltz* also has two plausible takes. Both ambiguous transfers were excluded from grouping. The catalogue covers part of Victor's output. Even a unique match in this extract leaves the physical pressing and its digital transfer to verify. [At the Jazz Band Ball](https://www.loc.gov/item/jukebox-28219/) · [1911 take](https://www.loc.gov/item/jukebox-130689/) · [1913 take](https://www.loc.gov/item/jukebox-130690/)

These metadata checks admitted zero sources. Technical eligibility, rights for the specific transfer, the full digital chain, and overlap with previously consumed sources still require evidence. One archive transfer workflow also supplies limited production diversity.

Replay the join against the two bound metadata snapshots on schwarz. The script verifies their digests before joining. The Library of Congress JSON has SHA-256 `ea6b74f30eeac6be74f4ab947f41001a070719bdb5831bcdac12e243b9cbb93a`. [Metadata download](https://data.labs.loc.gov/jukebox/metadata.json)

```sh
python3 -B scripts/music_verdict_victor_sessions.py \
  /Volumes/schwarz/lossytrace/validation/commons-music-metadata-20261123-001 \
  /Volumes/schwarz/lossytrace/validation/potpourri-session-audit-20261123-001/metadata.json
```

## Single-file decision policy

The [release study design](../../docs/research/music-verdict-successor-20260927.md) fixes the three decision regions before fresh evaluation. The research implementation accepts one raw logit per file and enforces the complete calibration inventory of six negative and 36 encoded cases per source. It fits a scalar temperature with equal weight for each source and class. It takes both decision cutoffs directly from the raw scores so rounding a probability to zero or one cannot change the verdict. Callers must bind source identities to an independently verified allocation before fitting.

Two artificial score distributions with exact temperature optima verify the fit and the class weighting. Additional checks cover inclusive cutoffs, missing groups and cases, restricted partitions, saturated probabilities, and unrepresentable cutoffs. A deterministic smoke check over 100 artificial groups and 4,200 logits gave an absolute weighted loss derivative below `1e-12` at the fitted optimum. All calibration cases respected their class-specific cutoff. Those checks measure software behavior. Finished-music accuracy and coverage remain unmeasured.

```sh
.tmp/music-verdict-v1/python-env/bin/python -m unittest discover \
  -s scripts/tests -p 'test_music_verdict*.py'
```

The earlier [offline single-file experiment](../music-library-pilot-v1/single-file-interpretation-20261123.md) retains its original threshold rule and negative result. Neither its scores nor the sealed evaluation data were used to fit this policy.
