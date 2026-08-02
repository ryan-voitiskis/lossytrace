# Factorial benchmark v2 fractional-assignment preregistration

Date: 2026-08-02

State: source-blind assignment rules frozen before private assignment; no
audio, waveform statistic, codec output, mechanism feature, score, or unopened
label inspected

## Purpose

This checkpoint fixes which already-selected source groups will receive which
categorical benchmark cells. It sits after source, factor, exact-toolchain, and
public-decoder freezes and before case construction. The assignment may use
only private group identity plus partition, source collection, source domain,
and provenance tier.

The machine-readable rules are
[`fractional-assignment-rules.json`](../../benchmarks/audio-integrity-v2/fractional-assignment-rules.json).
Their SHA-256 is
`aec91fc4e31a080000769d8ea385a08d308014a939a3c1d4f69140fb11ca576f`.
They bind upstream commit
`9cc87b10dc5551a9d5da2dc844d5289a11106084`, the exact 793-group private
source allocation, corrected factor freeze, recipe-`004` toolchain result, and
public-decoder result.

The generator and validator are
[`freeze-audio-integrity-v2-fractional-assignment.py`](../../scripts/freeze-audio-integrity-v2-fractional-assignment.py).
The rules bind its exact SHA-256,
`80088fb1e2c503d16c3ea26c0a152f5a737e5ee808bb4a9ba5205539097ac1ca`,
so a replay cannot silently substitute a different assignment implementation.
Private source IDs and cell mappings stay outside Git. The public aggregate is
forbidden from containing group, case, partition-group, relative-path, or
audio-hash keys.

## Deterministic design

A domain-separated SHA-256 ranking orders groups independently for every
purpose. Quota selection is round-robin across source domains, with a separate
hash ordering within each domain. This makes small domains visible without
using duration, bandwidth, loudness, sparsity, or any other waveform property.

Development and encoder transfer receive:

- one anchor positive per source group per codec;
- exactly 120 development or 60 transfer source groups per nonanchor template;
- exactly 40 development or 20 transfer groups per nonidentity transform;
- one matched transformed positive for every codec on every transform-selected
  group;
- compatible decoder cycling by setting; and
- channel and wrapper cycling independent of expectation.

Every positive points to a deduplicated PCM reference identical on source,
channel treatment, transform, and wrapper. A case contains identity or one
nonidentity transform, never two. The container-only transform cycles WAV and
AIFF rather than being conflated with primary FLAC.

The corrected FFmpeg-native Vorbis transfer templates remain stereo-only. The
assignment validator rejects any mono Vorbis transfer cell and preserves the
explicitly narrower claim.

## External seal

All 164 external groups receive identity references, and each nonidentity
negative transform receives exactly 20 groups. A separate identity-only,
domain-balanced ranking reserves exactly 100 groups for a possible future MP3
positive and preassigns only channel and wrapper.

The reserve contains no codec setting, encoder, decoder, feature, or score. It
does not create an external positive. If and only if a representation survives
development and encoder transfer, a new lineage and exact setting must be
frozen separately before those reserved slots can be materialized.

## Replay gate

The committed algorithm must be applied twice to the private source
allocation. Both complete private assignments and both path-free run
aggregates must compare byte-for-byte equal. Only then may an attested public
aggregate be committed.

Passing this gate authorizes deterministic case construction with one
low-priority worker and the storage reserve. It does not authorize mechanism
scoring or opening encoder/external transfer.
