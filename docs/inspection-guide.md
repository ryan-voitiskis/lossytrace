# Reading a LossyTrace inspection

LossyTrace reports experimental measurements, not whether a file has ever
passed through a lossy codec. No public history detector has passed the
project's validation gates. A suspicious measurement is not proof of lossy
history; an absent measurement is not proof of a lossless history.

Run `lossytrace analyze track.flac --pretty` to inspect a file, or
`lossytrace explain` to print this guide without opening audio. These commands
do not modify the input audio. Analysis reports JSON; this guide is plain
Markdown, not an additional analysis result.

## Start with scope and support

- `schema_version`: version of the JSON envelope, currently 1.
- `state`: currently `experimental_measurements_only`.
- `public_verdict_enabled`: currently false.
- `feature_version`: currently 0, an experimental measurement definition,
  not a calibrated classifier or stable cache contract.
- `input_sha256`: fingerprint of the entire input file's bytes, not a decoded
  PCM fingerprint, proof of provenance, or similarity score. Retagging or
  rewrapping can change it without changing the audio samples.
- `analyzed_sample_count` and `analyzed_duration_seconds`: the mono analysis
  sample count and duration, not necessarily the complete track.
- `truncated_by_limit`: whether the decoder stopped at the requested sample
  limit without establishing end-of-file. The default limit is 120 seconds;
  `--max-seconds 0` requests the whole file. Reaching the exact limit can set
  this flag even if no additional samples remain.

The current analysis averages decoded channels into mono and uses float32
samples. Opposite-polarity channels can cancel. These measurements do not
preserve all stereo information or all high-resolution sample precision.
This public inspector is not the separate stereo research alignment runner.

## Source facts describe the present file

Inside `source_facts`:

- `sample_rate_hz`, `channel_count`, and `declared_bits_per_sample` describe
  the decoded stream or its declared format. Missing declarations remain null.
- `codec_debug` is a decoder-library diagnostic identifier, not an estimate
  of a previous encoder or codec.
- `container_extension` comes from the filename. It is not independently
  verified provenance or proof of the container's contents.

A FLAC wrapper, a high sample rate, or a 24-bit declaration cannot establish
that earlier processing was lossless. Conversely, limited bandwidth or few
effective bits do not by themselves establish deception or a codec history.

## Activity and usable measurement support

Inside `compression_trace`:

- `analyzed_frame_count`: STFT frames supplied to the measurement.
- `active_frame_count`: energetic, sufficiently non-sparse frames used.
- `active_duration_seconds`: active frame hops expressed as seconds. It is
  not a listener-validated duration or an independent observation count.
- `high_band_supported_frame_count`: active frames with enough upper-band
  support to search for an edge.
- `median_active_bin_fraction`: median fraction of bins above the measurement's
  relative power floor. It is not a probability of prior compression.

Support is technical eligibility for a measurement. It is not confidence in a
history claim. Silence, short duration, sparse content and low sample rates can
make some measurements unavailable.

## Spectral measurements and alternative explanations

| Fields | What they describe | Why they are not a codec verdict |
| --- | --- | --- |
| `spectral_edge_hz`, `spectral_edge_drop_db`, `spectral_edge_persistence`, `spectral_edge_spread_hz` | Frequency, drop, recurrence and spread of a detected downward spectral step | Recording bandwidth, filtering, mastering and sample-rate conversion can also produce edges. |
| `spectral_hole_ratio`, `isolated_hole_ratio` | Deep local spectral deficits, including deficits isolated in frequency | Tonal or sparse sources and other processing can also produce gaps. |
| `band_rupture_score` | Adjacent-band spectral discontinuity | A content-dependent measurement, not a calibrated probability or quality score. |
| `transform_alignment_score`, `transform_alignment_block_samples`, `transform_alignment_phase_samples`, `transform_alignment_small_coefficient_fraction` | Contrast and associated settings from an experimental MDCT-grid search | Source structure can produce apparent alignment. The winning grid does not identify a historical encoder. |

Fields bounded between 0 and 1 are still measurements, not probabilities.
Several fields from the same spectral calculation are not independent
corroboration. Do not combine them into an improvised vote or threshold rule.

## Null, zero and conclusions

`null` means the measurement was not produced: support can be insufficient,
or no qualifying feature can have been found. It does not mean zero damage.
A numeric zero is a measured value under this implementation, not proof that
no codec was used. No combination currently warrants an authentic, clean,
lossy-derived, fraudulent, transparent or perceptually degraded label.

Use a report to record observations and identify questions for investigation.
Establish actual history with trustworthy source records or a documented
processing chain where available. Do not delete, replace or retag recordings
automatically on the basis of these measurements. Human listening can address
perceived differences; it cannot certify a file's processing history.
