# Single-file stress controls

This recipe binds the four separately reported controls named in the [September study](../../docs/research/music-verdict-successor-20260927.md). All four begin independently with the same verified negative source PCM, with identity preprocessing. Source eligibility and allocation are prerequisites for formal use. A constructed derivative cannot establish the source's prior history.

| Control | Native-domain operation |
|---|---|
| lowpass12k | Causal fourth-order Butterworth low-pass at 12,000 Hz. Cascade two FFmpeg double-precision direct-form-I biquads with Q 0.541196100146197 and 1.306562964876377, in that order. Start in the zero state. Preserve native frame count. |
| quiet | Multiply every channel sample by 0.01 (−40 dB). No normalization. |
| sparse | In every four-second period, retain the first native second and zero the rest. Apply the same gain to each channel. On either end of each retained second, ramp between zero and unity over round(rate × 0.010) frames, inclusive, with a half cosine. Truncate this periodic envelope at the actual file boundary. |
| short | Keep the first 20 native seconds, byte-exact, with no padding. The 30-second minimum makes unsupported the expected disposition. |

Preserve channel layout, sample rate and depth. For modified samples round to nearest even, saturate to native range, count clipped channel samples and use no dither. Write PCM as FLAC, verify decoded samples and retain the source and result hashes. Preserve the raw PCM and interval coordinates for the short control through the source binding. Each recipe is deterministic.

At evaluation, report four separate denominators, one expected result per allocated group per condition per model. Report flags, no evidence, inconclusive, unsupported and missing outputs on each full denominator. Report short-input routing failures explicitly. These controls have zero weight in training, selection, calibration, primary coverage and release decisions. The imposed temporal envelope tests one kind of sparsity. Naturally quiet/sparse performances remain in the primary population.

The implementation checkout must be fixed before construction. A generated-only smoke may verify native formats, sample changes, response and determinism. It uses zero formal sources, fits and evaluations. Formal construction still requires the separate execution freeze.
