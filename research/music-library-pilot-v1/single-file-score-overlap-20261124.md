# Could a different cutoff rescue these single-file scores?

Each model assigns one score per file. For any upper cutoff on that score, flagging at least 192 of the 384 encodes would also flag at least 28 of the 64 direct renders. Tuning the cutoff alone cannot yield both 50% detection and few false alerts on these compositions.

| Model | Encodes scoring above every direct render (of 384) | Minimum direct renders flagged when detecting half the encodes (of 64) |
|---|---:|---:|
| Original CNN | 4 | 28 (43.8%) |
| Matched-pair ranking CNN | 12 | 29 (45.3%) |
| Measurement logistic classifier | 3 | 31 (48.4%) |

These are retrospective bounds on the already examined four-recipe procedural test set. They are **not** observed operating points of the locked detectors. Count the direct renders that score at least as high as the 192nd highest encoded file. Every such render must be included whenever a common upper cutoff includes that encoded file. Changing the lower, no-evidence cutoff cannot affect this count. Under the actual prespecified cutoffs the three models flagged respectively 5, 0 and 29 encodes and 1, 0 and 4 direct renders. [Fixed-cutoff results](single-file-comparator-20261124.md) · [Score inventory digests and counts](single-file-score-overlap-20261124.json)

The counting script used retained logits only. A separate enumeration of all 448 distinct score levels for each model reproduced both columns. It does not return a new cutoff or policy. The compositions share one sequencer and each contributes six encodes. These observations supply no accuracy estimate for independently recorded finished music.

```sh
python3 -B scripts/music_single_file_score_overlap.py /Volumes/schwarz/lossytrace \
  | cmp - research/music-library-pilot-v1/single-file-score-overlap-20261124.json
```
