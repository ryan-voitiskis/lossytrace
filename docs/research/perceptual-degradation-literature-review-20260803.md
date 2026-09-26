# Perceptual-degradation literature and implementation review - 2026-08-03

**Scope:** full-reference estimation of audible, material degradation in audio
caused by controlled lossy coding. This is not a codec-history or provenance
study. Published subjective scores and correlations were reviewed; no retained
LossyTrace waveform was scored and no sealed label was opened.

## Decision

The first oracle will expose exactly two primary metric families:

1. **ViSQOL Audio v3.3.3**, pinned to Git commit
   `c3aa2e498e0f7f14202643594335a0b9ee40bdd9`, as an Apache-2.0 full-reference
   similarity family.
2. **A BS.1387-derived research proxy**, pinned initially to GstPEAQ 0.6.1 at
   Git commit `c6e8b23d3374dbc937ef9f7cfbdb3b3f4c864352`, run only as an isolated
   subprocess and named `gstpeaq_proxy` in evidence.

The proxy is not a conforming implementation of Recommendation ITU-R
BS.1387, and the recommendation itself states that protected technology may
require prior consent or a licence. The proxy therefore has a hard legal and
redistribution gate before execution. It will not be linked into, shipped
with, or represented as part of the public LossyTrace library or CLI. Failure
to clear that gate pauses metric execution and requires a score-blind,
committed amendment; it does not silently authorize a substitute.

The raw outputs do not define perceptual truth. Human listening evidence does.
No weighted combination, impairment threshold, or probability interpretation
is eligible until it is calibrated on preregistered development listening data
and then passes fresh grouped validation.

## Standards and listening methods

### ITU-R BS.1387-2

[Recommendation ITU-R BS.1387-2](https://www.itu.int/rec/R-REC-BS.1387)
defines a full-reference perceptual measurement framework. Its objective
difference grade (ODG) is associated with the BS.1116 subjective difference
grade scale from `0` (imperceptible) to `-4` (very annoying). The
recommendation focuses on high-quality impairments and warns that aggregate
correlation can hide degradation-specific failures and outliers.

The recommendation requires reference and system-under-test signals to be
aligned to within 24 samples over the measurement interval but does not
standardize the synchronization mechanism. That makes deterministic alignment
and explicit support reporting part of the LossyTrace oracle, rather than a
preprocessing detail. Individual model output variables (MOVs) can help
describe masking, modulation, noise-to-mask behavior, bandwidth, and probable
distortion type, but they remain outputs of one BS.1387-derived family.

Reviewed official PDF: 2023-05 edition, 100 pages, SHA-256
`ffe3ce073c483fb29c573a3158aa73c6536856468a9539e8b292ef9a0389f135`.

### ITU-R BS.1116-3

[Recommendation ITU-R BS.1116-3](https://www.itu.int/rec/R-REC-BS.1116)
is the appropriate basis for small impairments near transparency. It calls for
expert and trained listeners, a double-blind triple-stimulus presentation with
a hidden reference, close synchronization and rapid switching, declared
high-quality reproduction, controlled sessions, and fatigue management.

LossyTrace will use a BS.1116-style block for subtle codec conditions. A
separate randomized detection response will be collected before the impairment
grade so that audibility is not inferred from annoyance or from a MUSHRA score.

Reviewed official PDF: 2015 edition, 32 pages, SHA-256
`2622d08779de8b46bde0fcac9b2e3acbd9a2cea60e25605c0ee4162e5e9b81e4`.

### ITU-R BS.1534-3

[Recommendation ITU-R BS.1534-3](https://www.itu.int/rec/R-REC-BS.1534)
defines MUSHRA for intermediate-quality audio. It requires listener training,
hidden references and anchors, randomized presentation, suitable excerpts,
and reporting of reproduction and screening. The current method recommends a
hidden 3.5 kHz anchor and a hidden 7 kHz anchor, no more than 12 signals in a
trial, short loopable excerpts, and statistical reporting rather than only
means.

LossyTrace will use MUSHRA-style blocks for intermediate and severe conditions.
Published ODAQ follow-up evidence shows that calling out anchors during
training can alter ratings. Conditions will therefore be described neutrally
and consistently; anchor identity remains hidden during scoring.

Reviewed official PDF: 2015 edition, 36 pages, SHA-256
`0a751fa8941e72178de216c3008bc55affd456e2551cbaed67d7934c334f430f`.

## Objective metric evidence

### ViSQOL Audio

The [ViSQOL repository](https://github.com/google/visqol) is Apache-2.0 and
includes its audio model. Audio mode expects 48 kHz input, downmixes
multichannel material to mono, and is intended for treatment-level rather than
single-file conclusions. Its documentation recommends excerpts of roughly
8-10 seconds with limited silence and warns that a single score is not
meaningful.

Sloan et al., ["Objective Assessment of Perceptual Audio Quality Using
ViSQOLAudio"](https://doi.org/10.1109/TBC.2017.2704421), evaluated full-band
codec conditions using MUSHRA-derived data including TCDAudio14, AACvOpus15,
and CoreSV14. This is relevant codec evidence, but the public implementation's
model was trained on related subjective collections. Those collections cannot
be treated as fresh independent evidence for ViSQOL.

ViSQOL is selected because it is reproducible, openly licensed, directly
applicable to full-reference music coding, and independent in implementation
from the BS.1387-derived proxy. Its mono downmix is a known blind spot, so the
oracle must also report channel and stereo residual evidence and must not use
ViSQOL alone to support a stereo-image conclusion.

### BS.1387-derived family and GstPEAQ

GstPEAQ is distributed under the GNU Library General Public License v2. Its
[own documentation](https://github.com/HSU-ANT/gstpeaq) says it implements the
older BS.1387-1 Basic and Advanced models but does not meet the recommendation's
allowed tolerance. Kabal et al., ["An Examination and Interpretation of ITU-R
BS.1387"](https://www.dafx.de/paper-archive/2015/DAFx-15_submission_65.pdf),
found that the open implementations they examined were non-conforming and
should not be treated as reference implementations for standardized
comparisons.

The frozen name `gstpeaq_proxy` is deliberate. It may be useful as a
deterministic research measurement and for MOV-style artifact summaries, but
its ODG is not official PEAQ. The proxy is research-only, subprocess-isolated,
version- and binary-hash-bound, and subject to the legal gate above.

### Domain dependence and the 2f model

Torcoli, Kastner, and Herre, ["Objective Measures of Perceptual Audio Quality
Reviewed: An Evaluation of Their Application Domain
Dependence"](https://doi.org/10.1109/TASLP.2021.3127050), compared metrics over
audio-coding and source-separation listening tests. Their 2f model uses two
PEAQ Basic MOVs, ADB and AvgModDiff1, and was strong across the combined
domains. The accompanying [SEBASS resource](https://www.audiolabs-erlangen.de/resources/2019-WASPAA-SEBASS)
warns that different PEAQ implementations materially shift 2f output.

The 2f score is therefore not a third independent family and will not be
applied to GstPEAQ MOVs as if they were interchangeable with PQevalAudio. Its
published performance is supporting literature, not permission to mix
implementations.

Torcoli et al., ["The Challenge of Developing Perceptual Audio Quality
Measures"](https://publica.fraunhofer.de/entities/publication/5f0fd89a-9f80-4dcf-8091-e99867c1e419),
also showed that metric performance varies substantially by isolated coding
artifact and that parametric coding remains difficult. This supports human
calibration, artifact-stratified reporting, and explicit abstention rather
than a universal score.

### New learned metrics not selected

- **NOMAD** is a non-matching-reference speech-quality method trained and
  evaluated primarily on speech and enhancement degradations. It is not yet a
  mastered-music codec oracle. Reviewed PDF SHA-256:
  `18257f2cbce054e1fa20661c5701f741eb783523360e2d516961a3193df95e6e`.
- **DeePAQ** adapts the MERT music foundation model with LoRA using ViSQOL and
  bitrate surrogate labels. Its paper reports about 460 hours of internal
  CD-quality training material, 95 million model parameters, and good
  cross-test correlations. The training corpus and fitted weights are not
  publicly bound in the paper, and the targets are weak surrogates rather than
  new human labels. It is not selected for the deterministic oracle or as
  independent no-reference evidence. Reviewed PDF SHA-256:
  `fca29a2a24037cc4922eba5db3ed18f275e3ca8b1743859be9932eb70e97f22a`.

## Public subjective-data audit

### ODAQ

[ODAQ](https://doi.org/10.5281/zenodo.10405774) contains 240 samples, 26 expert
listeners, and 6,240 individual ratings. The expanded ratings release
[adds 16 listeners](https://doi.org/10.5281/zenodo.13377284), for 42 listeners
and 10,080 ratings. Audio licenses are mixed by source; score and metadata
tables are CC BY 4.0. One nominal reference source is itself an AAC-LC 256
kbit/s file and must be excluded from any clean-reference subset.

ODAQ's coding-like conditions are simulated low-pass, tonality-mismatch,
unmasked-noise, spectral-hole, and pre-echo degradations. They are excellent
for artifact coverage and human calibration but are not actual MP3, AAC,
Vorbis, or Opus encoder outputs. ODAQ can be development evidence only. Any
source used for metric selection or thresholding stays outside final
validation.

The stereo extension [ODAQ v1.5](https://doi.org/10.5281/zenodo.17162670)
adds 176 samples and 16 expert listeners. It is useful for a later stereo
stress phase, not required to start the monaural/timbral calibration.

No ODAQ archive was downloaded in full during this review. Archive central
directory and licence members were inspected with bounded HTTP ranges to
protect the 15 GiB workspace reserve.

### CoreSV 2014 public multiformat test

The [CoreSV test](https://listening-test.coresv.net/results.htm) publishes
paired lossless/lossy tracks, parsed ratings, and raw participant logs for 40
items across Opus 1.1, Apple AAC, aoTuV Vorbis, LAME MP3, and two FAAC anchors.
It contains genuine traditional-codec conditions and useful near-transparent
examples.

It was an at-home public ABC/HR exercise with uneven per-item participation,
38 contributors, bespoke screening, and mixed source origins including
commercial album excerpts. Per-track redistribution rights are not clearly
bound on the results page. LossyTrace may use public aggregate scores for
literature comparison and may stage locally eligible items only after a
source-by-source licence audit. It is not primary calibration evidence and is
not an independent release gate.

### ViSQOL and codec-verification collections

TCDAudio14 and AACvOpus15 are described in the ViSQOL literature and cover
real codecs under trained MUSHRA-style listening. The underlying public-data
and source-licence boundary is not sufficiently clear for LossyTrace to adopt
them as new independent evidence. MPEG USAC verification results are useful
published comparison evidence but are not an open, source-disjoint corpus for
this study.

## Consequences for the program

1. Open human data are sufficient to test infrastructure, artifact behavior,
   and some actual-codec ranking, but not to establish the requested modern,
   grouped source/domain/codec/encoder transfer claim.
2. A new listening program is likely required. Before asking for material
   participation, the repository must contain the protocol, playback software,
   stimuli manifest, power analysis, privacy statement, and dry-run evidence.
3. Audibility and impairment severity are separate targets. Neither is a
   codec-history probability, and annoyance is not used as a synonym for
   audibility.
4. A full-reference oracle estimates perceptual difference. The statement that
   a difference was *caused by coding* is valid only for a controlled paired
   construction. It cannot be inferred universally from an unknown waveform.
5. Transparent lossy encodes remain non-degraded examples. Bitrate, codec
   identity, or lossy ancestry may not serve as a degradation label.
6. Natural bandwidth limitation, sparse and tonal audio, resampling, gain,
   production processing, clipping, and stereo changes remain visible controls
   or unsupported cases; support rules may not remove them merely because they
   are difficult.
