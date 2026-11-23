# Can the inexpensive measurements identify a single encoded file?

The measurement classifier missed the locked pilot criteria. On 64 synthetic compositions it flagged 29 of 384 encoded copies (7.6%) and 4 of 64 direct renders (6.3%). It gave a no-evidence call to 41 encoded copies. Across this population, a file chosen at random from the encoded copies scored higher than a randomly chosen control 53.8% of the time, counting ties as half. Identifying an added codec stage from one file remains the unresolved problem. [Prespecified analysis](single-file-comparator-plan-20261124.md) · [Counts by recipe and codec](single-file-comparator-results-20261124.json)

| Pipeline | Encodes flagged / 384 | Direct renders flagged / 64 | Balanced coverage | ROC AUC |
|---|---:|---:|---:|---:|
| Measurement logistic classifier | 29 | 4 | 20.8% | 0.538 |
| Original CNN | 5 | 1 | 12.1% | 0.524 |
| CNN trained to rank matched pairs | 0 | 0 | 7.8% | 0.533 |

Balanced coverage gives equal weight to the fraction of direct renders and the fraction of encodes that received either definite answer. The measurement classifier abstained on 49 direct renders and 314 encoded copies. The locked targets included at least 50% detection and 60% balanced coverage. All four evaluation recipes used the same sequencer, and each source contributed six encodes. These figures describe this synthetic pilot. [CNN experiment](single-file-interpretation-20261123.md)

The comparator scored 225 of 384 encodes above their own direct render. The original CNN did so for 330 and the ranking CNN for 378. That comparison requires both versions of a track. None of the three pipelines achieved comparable separation when the source recording was unavailable. In a post hoc check the inspector could measure a spectral edge on only two of the 448 evaluation files. The fitted comparator used its missing-value handling on the other 446. The other features still contributed to its score.

## Verification and replay

Training used the existing logistic recipe and the 1,008 synthetic reports from four training families. The 224 calibration cases set lower and upper raw-logit cutoffs of −0.209537 and 0.162307. The model flagged no direct renders among 32 calibration compositions. The cutoffs were saved before evaluating the other four recipes. The earlier CNN results were already known when this follow-up was planned. Each single-file prediction used only that WAV's measurements. The input archive, decoded PCM, inspector binary, model, thresholds and per-file features are bound in the retained records.

Two complete runs matched on every PCM and WAV hash, measured feature and logit across all 672 files. Checkpoints, cutoffs and aggregate results were byte-identical. A separate scalar calculation reproduced all scores within numerical rounding and independently recovered the cutoffs, three-way counts and ROC AUC. The two run directories on schwarz end in `single-file-comparator-20261124-001` and `-002`. Use a new output directory for replay.

```sh
base=/Volumes/schwarz/lossytrace/validation
PYTHONPATH=.tmp/music-verdict-v1/regression-extras-20261010-001 \
  .tmp/music-verdict-v1/python-env/bin/python -B scripts/music_single_file_comparator.py \
  "$base/single-file-comparator-replay"
cmp "$base/single-file-comparator-replay/summary.json" research/music-library-pilot-v1/single-file-comparator-results-20261124.json
```
