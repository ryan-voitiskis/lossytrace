# Lossy-detector comparison and next research direction - 2026-08-02

**Decision:** published 98-100% accuracy figures do not establish a safe
lossy-source verdict for LossyTrace. The exact Cannam detector revision reached
high positive recall in the retained pilot, but its 62.5% negative false-alert
rate shows that it primarily recognizes codec-correlated spectral appearance,
not source history. Do not revive a CNN, spectral-cutoff rule, AAC
quantization-error rule, inverse-decoder scalar, or codec-projection threshold
as the next candidate.

The next long-running program should first define what history is identifiable
from PCM, reproduce strong baselines across the complete consumed challenge
matrix, and measure which effects are caused by codec history rather than
source content. Only a stable within-source mechanism should be allowed to
become a new preregistered candidate.

This is a research-direction review, not a candidate preregistration. It does
not authorize opening the future codec-only subset or release holdout, changing
feature version `0`, enabling a public verdict, or modifying Reklawdbox.

## Why accuracy is easy to misread

These projects answer different questions:

- binary lossy-history detection versus identifying one known codec among
  already-lossy inputs;
- excerpt, file, track, source-group, or album-level prediction;
- random held-out tracks versus unseen artists, domains, encoders, and codec
  parameters;
- ordinary CD material versus naturally band-limited, sparse, historical,
  denoised, resampled, or transformed genuine PCM;
- balanced research classes versus the low prevalence and high false-positive
  cost of a real music library.

Overall accuracy hides the distinction. For LossyTrace, supported-negative
source-group alerts and their confidence bound are the primary safety
measurement; recall is secondary and unsupported material must remain
explicit. A 98% balanced-test accuracy can still be unusable if its errors
concentrate on a common genuine-lossless domain.

There is also an identifiability boundary. The samples obtained by decoding an
MP3 are valid PCM samples and can be reproduced exactly by a different history,
for example by rendering or storing that waveform losslessly. Signal-only
analysis therefore cannot prove an unrestricted historical proposition. It can
only measure evidence under a specified source and processing model. This is a
logical boundary, not a weakness that a larger classifier automatically fixes.

## Cannam Vamp detector

### Published claim and implementation

[`cannam/vamp-lossy-encoding-detector`](https://github.com/cannam/vamp-lossy-encoding-detector)
reports "about 98%" accuracy on previously unseen files ripped from CD and
encoded either lossily or losslessly. The repository describes approximately
4,300 training examples made from three clips per track from a small collection
of ten named commercial albums. It includes MP3, AAC, Vorbis, and Opus settings
plus resampling, -3 dB gain, and time-stretch augmentation. It says evaluation
used an entirely separate dataset, but does not publish that dataset's size,
sources, class balance, confusion matrix, codec breakdown, raw predictions, or
confidence intervals.

The exact reviewed revision was
[`7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b`](https://github.com/cannam/vamp-lossy-encoding-detector/tree/7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b).
It is a four-convolution-layer spectrogram CNN using roughly one-second,
512-point STFT images. Each window is classified at 0.5; the full detector
labels a file lossy when at least 25% of its windows are labelled lossy. The
README itself warns that the window output tends to be overconfident, that
high-quality lossy encodings can be missed, and that historical recordings
with heavy denoising can be false positives. The repository contains the
inference implementation and weights, but not the training/evaluation pipeline
or corpus needed to reproduce the 98% figure.

### Retained LossyTrace result

LossyTrace already ran that exact revision and its `cf` output on a frozen
pilot of 112 full-track cases from eight independent source groups. The
unchanged file rule was the plugin's 25%-of-windows decision. The pilot
contained 64 controlled positives across eight codec/settings and 48 negatives
across untouched, gain-only, trim-only, dithered, ordinary low-pass, and sharp
low-pass PCM. It was development evidence; no sealed label was opened.

| Metric | Result | Two-sided 95% Wilson interval |
| --- | ---: | ---: |
| positive recall | 61/64 = 95.31% | 87.10-98.39% |
| negative specificity | 18/48 = 37.50% | 25.22-51.64% |
| negative false-alert rate | 30/48 = 62.50% | 48.36-74.78% |
| precision in this selected pilot | 61/91 = 67.03% | 56.86-75.83% |
| overall accuracy | 79/112 = 70.54% | 61.53-78.18% |
| balanced accuracy | 66.41% | not treated as a safety gate |

Every one of the eight source groups had at least two negative variants
alert. Positive detection was 8/8 for MP3-128, MP3-320, AAC-128, both Opus
settings, both Vorbis settings, and 5/8 for AAC-256. The negative alerts were:

| Genuine-PCM class | Alerts |
| --- | ---: |
| untouched lossless | 4/8 |
| gain only | 4/8 |
| trim only | 4/8 |
| dithered to 16 bit | 2/8 |
| ordinary low-pass | 8/8 |
| sharp low-pass | 8/8 |

The pilot is too small to estimate universal accuracy, but it is sufficient to
reject the detector for LossyTrace's zero-hard-negative-alert requirement. The
failure also directly matches the model's stated denoised/historical weakness:
the classifier responds to absent or sparse high-frequency structure whether
that structure was caused by a codec or by genuine content and production.

The retained private member
`external-c4dm-v1-8sources-fulltracks.json` has SHA-256
`cb322b253f291419f1232c1a66425cfe23b27566a991a851ddcfa3f165df6e4d`.
Its containing verified archive has SHA-256
`c79c23a93b7e9762b91bd8ad02f810da2087ded7966811fcb5b55d0af11eb5fd`.
Case identities, paths, and audio remain outside Git.

## Comparable published systems

| Work | Reported result | What the number actually supports | Important limitation for LossyTrace |
| --- | --- | --- | --- |
| Hennequin, Royo-Letelier, and Moussallam, [Codec-Independent Lossy Audio Compression Detection](https://doi.org/10.1109/ICASSP.2017.7952251) (2017) | 98.6% overall; 98.1% altered recall and 99.1% unaltered specificity | A spectrogram CNN can classify generated codec examples and a large curated music catalogue well under its study distribution. | AAC-320 recall was 2.3%. An unseen sample-rate path initially failed until it was added to training. Only one encoder per codec was used. The cleaning loop removed catalogue FLACs whose spectrograms looked lossy, which likely removed exactly the hard negatives LossyTrace must retain. |
| Kim and Rafii, [Lossy Audio Compression Identification](https://doi.org/10.23919/EUSIPCO.2018.8553611) (2018) | 99.6% digital and 92.4% analog-transfer accuracy | An inverse-decoder search can often identify which of five known lossy codec families produced already-lossy PCM. | The study used 20 source excerpts and 1,000 derived cases. It had no genuinely lossless class, so the result does not measure false accusations of codec history. Analog MP3 accuracy was 88% and fell to 70% at 320 kbit/s. |
| Lacroix et al., [Lossless Audio Checker](https://secure.aes.org/forum/pubs/conventions/?elib=17972) (2015) | 100% transcoding and upscaling, 91.3% upsampling | An early practical checker could recognize its tested manipulations. | Transcoding detection was AAC-specific and the convention manuscript did not establish universal codec/source transfer. Later LossyTrace testing of its successor quantization family is more informative for our task. |
| Derrien, [Detection of Genuine Lossless Audio Files](https://secure.aes.org/forum/pubs/journal/?elib=19892) (2019) and [companion results](https://potion.prism.cnrs.fr/JAES2018.html) | On a 100-album source collection, 0% false positives with AAC false negatives falling from 1.9-3.9% at the fast setting to 0% at the 64x64 setting | An AAC-specific quantization-lattice search is physically interpretable and can be highly accurate on matched CD/iTunes material. | The companion code is research/non-commercial, the validation used one AAC workflow, and source diversity is not equivalent to encoder/domain transfer. LossyTrace independently reproduced the equations: the fixed boundary detected 308/404 positives but alerted on 44/197 hard negatives; a boundary above all negatives detected only 17/404. This direction is already rejected. |
| Koops, Micchi, and Quinton, [Robust Lossy Audio Compression Identification](https://arxiv.org/abs/2407.21545) (ISMIR 2024) | Naive model: 99.79% on default settings, 81.85% after only codec cutoffs changed. Random-mask model: 98.4% overall, 96.8% lossy and 99.8% lossless on the cutoff-variation set. | The paper demonstrates that near-perfect random held-out results can be a codec-parameter shortcut, and that targeted augmentation can reduce a known shortcut. | The 10,000 private source tracks, same source library, FFmpeg codec implementations, and fixed codec families remain within one experimental universe. AAC at the 14 kHz condition was still 81%; quiet sparse genuine tracks caused the remaining true false positives. |

The most important modern result is Koops et al., not because 98.4% proves the
problem solved, but because its naive model fell from 99.79% to 81.85% after a
single hidden codec parameter changed. That is the cleanest published example
of the same shortcut problem seen repeatedly in LossyTrace.

Commercial or heuristic tools such as
[`Fakin' The Funk?`](https://fakinthefunk.net/en) should be treated as triage
utilities, not accuracy references. Its own
[`support answer`](https://fakin-the-funk.125.s1.nabble.com/false-results-td551.html)
says it detects unexpected frequency cutoffs rather than whether a codec was
used, and its site acknowledges possible false positives. No public
source-group benchmark, raw predictions, or confidence intervals are
available. Spectrogram viewers are useful for human inspection but do not turn
a cutoff into provenance.

This review searched current primary work through 2026-08-02. It found no
later primary study with a stronger cross-domain, cross-encoder evaluation of
the decoded-PCM task than the ISMIR 2024 robustness study. Recent practical
tools predominantly expose spectral-cutoff heuristics or unauditable verdict
engines; they do not change the scientific boundary above.

## What the projects teach us

1. **The negative set determines the apparent solution.** Ordinary CD tracks
   make high-frequency cutoff and spectrogram-hole detectors look excellent.
   Historical, denoised, sparse, tonal, low-pass, and resampled PCM reveal the
   ambiguity.
2. **A codec setting can become a label shortcut.** Encoder-default cutoff,
   sample rate, decoder, bitrate, and window alignment must each cross train,
   development, and transfer boundaries.
3. **Cleaning labels with the detector biases specificity upward.** Suspected
   precompressed negatives may need review, but genuine hard negatives must
   never be deleted merely because the candidate finds them difficult.
4. **Track-disjoint is necessary but insufficient.** Split by performer,
   album/session, source collection, encoder implementation, and codec
   parameter family as well as track.
5. **A softmax value is not calibrated uncertainty.** Cannam explicitly notes
   overconfidence. Reliability, Brier score, expected calibration error, and
   risk-coverage under domain transfer are needed before calling a score a
   probability.
6. **Codec identification is not lossy-history detection.** A method can choose
   the right codec among known lossy inputs while having unmeasured or unsafe
   specificity against genuine PCM.
7. **A physically grounded method can still be source dependent.** The
   Derrien, exact-hybrid, and codec-projection results rule out the idea that
   explainability alone guarantees transfer.
8. **A universal binary verdict is the wrong immediate objective.** The honest
   outputs are measurements, support conditions, and an abstaining research
   assessment tied to a declared evidence domain.

## Recommended next program

### Phase 1 - identifiability and baseline audit

Do not invent a new score. Write an explicit task contract for three different
claims:

1. obvious codec-artifact triage;
2. scoped prior-codec-history assessment under a declared source model; and
3. actual provenance verification using reference or chain-of-custody evidence.

Prove which claims cannot be distinguished from PCM alone and define the
allowed abstention states. Then replay the exact Cannam detector and the best
retained explainable baselines across the complete 2,261-case consumed
population, with no threshold changes. The purpose is a common failure atlas,
not candidate selection.

### Phase 2 - factorial challenge benchmark

Build a source-grouped matrix in which source content is crossed with, rather
than correlated with:

- multiple MP3 encoders and versions;
- CBR/VBR, bitrate, encoder low-pass, stereo mode, and resampling paths;
- gain, trim, leading silence, dither, container, and decoder implementation;
- genuine hard negatives: historical/denoised recordings, analog transfers,
  mastering filters, low-rate and sparse instruments, synthesized tones,
  speech/noise, and naturally bandwidth-limited full mixes.

Development sources may be consumed, but a new independent transfer set must
be sealed by source collection and encoder before any candidate exists. Do not
use the future SQAM or release sets as convenient development data.

### Phase 3 - mechanism discovery by paired effects

Use matched source/transcode pairs to estimate mechanisms before training a
classifier. For each measurement, fit a hierarchical or mixed-effects model
that separates codec-history effect from source group, domain, encoder,
bitrate, and transformation interactions. Require:

- consistent within-source direction across domains;
- at least 90% correctly directed supported source pairs overall, with a
  one-sided 95% Wilson lower bound of at least 85%, before any threshold is
  considered;
- codec-history variance materially larger than source and interaction
  variance;
- stable effect under unseen encoder/settings;
- no effect manufactured by support filtering; and
- a predeclared null/permutation analysis grouped by source.

This is a better discovery criterion than searching a threshold with high
pooled accuracy.

Two materially new mechanisms are worth studying, but only after Phases 1 and
2 freeze their evaluation:

1. **Masking-conditioned coefficient censoring:** measure whether local
   spectro-temporal holes occur where an explicit psychoacoustic masking model
   predicts codec coefficient suppression, rather than merely measuring holes
   or a high-frequency edge. This directly tests the mechanism that Cannam,
   Hennequin, and Koops appear to exploit while controlling for natural
   bandwidth.
2. **Transient pre-echo asymmetry:** measure energy/noise structure immediately
   before versus after isolated attacks at several scales, conditioned on the
   uncompressed transient shape. Transform codecs can spread quantization noise
   before attacks; the signed temporal asymmetry is different from the static
   edge, exact-zero, CNN, and projection-residual summaries already rejected.

These are hypotheses, not two independent evidence families. Cross-correlation
and shared-failure analysis must decide that later. Joint-stereo, frame-grid,
and raw cutoff variants are controls, not extra candidates.

### Phase 4 - candidate gate, only if discovery survives

Preregister at most two fixed representations and one aggregation policy.
Before inspecting candidate scores, freeze source families, encoder-held-out
folds, support, robustness transforms, calibration, runtime, and stop rules.
The existing zero-alert, Wilson, recall, domain, and performance gates remain
unchanged. A result that fails is retained as useful negative evidence.

Only a survivor may be frozen and evaluated once on newly sealed external
evidence. Even a transfer survivor remains ineligible for the public path until
it has an in-process implementation without an external encoder, second full
decode, redundant spectrogram, or more than 10% p95 overhead.

## Proposed persistent-goal objective

If this program is approved, use the following long-running goal rather than a
goal to "improve accuracy":

> Determine the identifiable boundary of prior-lossy-compression inference
> from decoded PCM, build a reproducible cross-domain and cross-encoder
> challenge benchmark, and discover whether any codec-history mechanism has a
> stable within-source effect larger than source and processing confounds.
> Reproduce the strongest learned and explainable baselines without tuning;
> preregister at most two new representations only if the paired discovery
> gates pass; open newly sealed external-transfer evidence only for a frozen
> survivor. Keep all public output verdict-free and treat a rigorous
> non-identifiability or negative result as successful completion.

## Immediate recommendation

Start with Phases 1-3 as one research goal. The first milestone should be a
path-free baseline/failure atlas and a frozen factorial benchmark schema, not a
new detector. This gives the next candidate a chance to answer the actual
question - history rather than content appearance - and gives us an early,
scientifically valuable stop if the task is not identifiable at the required
false-positive rate.

Do not spend the next cycle tuning Cannam, random-mask CNN thresholds,
high-frequency cutoffs, AAC quantization boundaries, exact-hybrid summaries, or
codec-projection residuals. Their failures are already informative enough.

## Review provenance

The reviewed PDFs were rendered and their result tables checked visually, not
only text-extracted. Retrieval hashes were:

| Primary artifact | SHA-256 |
| --- | --- |
| Hennequin et al. ICASSP 2017 paper | `f9e069ba11f269510cd4d1e01e1e0fd310f7926c1f80568a358bd80e70311dc9` |
| Kim and Rafii EUSIPCO 2018 paper | `c1d37f72a05269705bd1f7718014e577bd30ff375fe876cc6884d479454af736` |
| Derrien detailed companion results | `aecaf9dc47c59b187d12ed38b1d59e928f3f619aca722db7bf4a0bc55388cc90` |
| Koops et al. arXiv 2407.21545 | `870fc78368b3bfe610a0d0df7e7cec151b09e268385334f1701cf5b881fc8b06` |

The official Derrien companion code was inspected only to confirm the
algorithm and its research/non-commercial notice. It was not added to Git or
used as production source. Temporary paper renders, text extractions, and the
read-only Cannam checkout were removed after this review.
