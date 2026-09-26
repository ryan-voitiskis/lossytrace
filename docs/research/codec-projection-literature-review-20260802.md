# Codec-projection literature review - 2026-08-02

**Scope:** primary literature relevant to identifying prior lossy compression
from decoded PCM stored in a lossless wrapper. This review distinguishes that
problem from detecting double compression in a current MP3 bitstream.

## Findings

| Work | Evidence available to the method | Applicable result | Boundary for LossyTrace |
| --- | --- | --- | --- |
| Moehrs, Herre, and Geiger, ["Analysing decompressed audio with the Inverse Decoder - towards an operative algorithm"](https://aes2.org/publications/elibrary-page/?id=11346) (AES 112, 2002) | Decoded PCM | MP3 framing, window type, stereo mode, and quantization parameters can in principle be reconstructed from decoded audio. Framing is found by seeking the analysis conditions that expose quantization troughs. | This is the strongest physical basis for codec-conditioned PCM analysis. The paper also reports energy-dependent quantization recovery, PCM-rounding and imperfect-filterbank error, incomplete stereo-mode recovery, and substantial search cost. It does not establish a source-independent provenance detector. |
| Luo et al., ["Compression history identification for digital audio signal"](https://doi.org/10.1109/ICASSP.2012.6288233) (ICASSP 2012) | WAV PCM after MP3 or WMA decode | A 21-dimensional MP3-hybrid MDCT representation separated original WAV from decoded MP3/WMA in the authors' dataset and remained useful after random trimming. | Directly applicable input model, but the features are zero counts and frequency-band magnitudes followed by an SVM. The experiment used random clip splits, one software workflow, and music excerpts; it did not use source/partition-disjoint hard negatives. LossyTrace's exact-hybrid and learned experiments already show that this class of representation is content/source dependent. |
| Bianchi et al., ["Detection and localization of double compression in MP3 audio tracks"](https://doi.org/10.1186/1687-417X-2014-10) (EURASIP JIS 2014) | A current MP3 bitstream plus decoded PCM used to build a calibrated recompression | Misaligning decoded PCM, recompressing it at the known current bitrate, and comparing observed versus simulated quantized-MDCT histograms can reduce content effects in some double-compression settings. | The analysis still requires quantized MDCT coefficients and parameters from the current MP3 bitstream. It is not directly usable when only a FLAC/WAV/AIFF wrapper is present. It also fails when the later bitrate is not higher than the earlier bitrate and leaves encoder/VBR transfer open. It motivates calibration, not the proposed measurement itself. |
| Hennequin, Royo-Letelier, and Moussallam, ["Codec independent lossy audio compression detection"](https://doi.org/10.1109/ICASSP.2017.7952251) (ICASSP 2017) | Decoded PCM | A spectrogram CNN can learn marks of several codecs and bitrates without recovering a codec frame grid. | Directly applicable input model, but not the proposed physical family. It requires a learned spectrogram classifier and reported dataset-level performance rather than the grouped hard-negative evidence required here. Earlier LossyTrace CNN/CRNN experiments are rejected and are not revived. |
| Kim and Rafii, ["Lossy Audio Compression Identification"](https://doi.org/10.23919/EUSIPCO.2018.8553611) (EUSIPCO 2018) | Decoded PCM, including analog-transfer captures | Searching codec transform/window/framing conditions can identify the matching codec, and block aggregation can improve robustness to content. | Directly applicable inverse-decoder direction. LossyTrace already reproduced the MP3 long-block idea: one repeatable tonal PCM control raised the safe boundary and no scalar template survived every grouped fold. The paper used 20 source excerpts and did not establish a lossless-versus-MP3 safety boundary over source-disjoint hard negatives. |
| Koops, Micchi, and Quinton, ["Robust Lossy Audio Compression Identification"](https://arxiv.org/abs/2407.21545) (2024) | Decoded PCM | Small unseen codec-parameter changes can collapse apparently near-perfect classifiers. Random high-frequency masking reduces reliance on a default codec cutoff. | The failure analysis is directly applicable: cutoff, sparse, and quiet-content shortcuts must be explicit hard negatives. The proposed CNN remains outside this study, and random track splits do not replace source-domain transfer. |
| ISO/IEC, [ISO/IEC 11172-3:1993](https://www.iso.org/standard/22412.html) | Codec specification | Defines the MPEG-1 Layer III decoder-side framing and hybrid filterbank that motivate codec-conditioned analysis. | The standard defines decoding, not a unique encoder. LAME projection behavior is implementation- and setting-specific and must be bound independently. |

## What is genuinely applicable

The decoded waveform can retain codec-conditioned structure. Inverse-decoder
work supports searching for an MP3 framing/filterbank/quantization explanation,
and calibration work supports comparing an observation with a controlled codec
projection. Neither result implies that a scalar projection residual is
source-independent. PCM rounding, encoder decisions, gain, trimming,
resampling, sparse content, and naturally limited bandwidth can all dominate
the trace.

The new study therefore treats encode/decode cycles as a research oracle, not
as a public algorithm. Its two summaries are one codec-projection evidence
family. Multiple residual statistics cannot satisfy a two-independent-family
verdict requirement.

## What is not applicable

Methods that read side information, quantized MDCT values, scalefactors, bit
reservoir state, Huffman data, current MP3 bitrate, or the present MP3 frame
grid do not transfer directly to lossless-wrapper PCM. They may explain a
physical mechanism or inspire a controlled projection, but their published
accuracy is not evidence for the LossyTrace task.

## Existing local precursor

The retained exact-transform source includes
`run_recompression_calibration_probe.py`. It performs one FFmpeg encode/decode
cycle and a second cycle on a small, consumed MUSDB selection, then records
waveform and first-difference residual summaries. It explicitly states that no
candidate was frozen. Before this preregistration was frozen, its source was
reviewed to avoid silently recreating it, but its archived scores were not
opened. It lacks the full negative population, source-domain folds, fixed
support policy, robustness transforms, path-free aggregate schema, and
non-timing reproducibility gate required below.
