# Factorial benchmark v2 fractional-assignment correction 001

Date: 2026-08-02

State: corrected recipe frozen before replay; no benchmark audio, waveform
statistic, feature, score, or unopened label was inspected

## Trigger

Construction review found that recipe `001` omitted
`target_sample_rate_hz` from assignment cells and from the reference
deduplication identity. The frozen encoder settings use 44.1 kHz for MP3, AAC,
and Vorbis, but 48 kHz for Opus. A positive at either rate could therefore
point to the same nominal reference when group, channel, transform, and
wrapper happened to agree.

The two recipe-`001` replays remain valid evidence that the algorithm was
deterministic, but their claim that every positive had an exact matched PCM
reference is false. The assignment is not constructible and must not enter an
accuracy denominator. This was detected before any assigned audio was
generated or any score was opened.

## Corrected recipe

Recipe `lossytrace-v2-fractional-assignment-20260802-002` makes target sample
rate a first-class cell factor and part of the matched-reference identity.
Positive rates come from the exact frozen encoder settings. Standalone base
and external hard-negative cells use a deterministic cycle over 44.1 and
48 kHz; each external transform has an exact 10/10 split. The deferred MP3
external-positive reserve fixes 44.1 kHz while leaving encoder, setting,
decoder, feature, and score unset.

The corrected rules SHA-256 is
`bd0c611f66efb20c7e1da5537150ddf678a42b61f924b3640180aad30b236bd2`.
They bind generator SHA-256
`5759206092b37b7ec7310ff7b7062089297b9e4bffdfad6bfd3e56705f13bbed`
and upstream checkpoint
`4a7b2a3bb63532706a0f08c9c56e827667966ae2`.

## Replay gate

Commit this correction before execution. Then rerun the complete private
assignment twice and require byte-identical private outputs and path-free run
aggregates. The validator must also establish that every positive matches its
reference on group, partition, channel, target sample rate, transform, and
wrapper. Only a fresh recipe-`002` result may authorize construction.
