# Factorial benchmark v2 factor-level correction 001

Date: 2026-08-02

State: capability correction frozen before a revised toolchain recipe and
before any complete replay, benchmark audio, source-to-cell assignment,
mechanism feature, score, or unopened label

## Observed stop

Corrected toolchain recipe `lossytrace-v2-toolchain-bindings-20260802-002`
passed the earlier LAME sample-rate boundary, then stopped at
`transfer-vorbis-ffmpeg-q2--mono`. FFmpeg 8.1.2 reported that its native
experimental Vorbis encoder supports only two channels and rejected the mono
stream before writing a bitstream.

This is an implementation capability boundary, not evidence about codec
history. The invocation emitted no aggregate, retained no synthetic output,
read no allocated source, and opened no score.

## Rejected alternatives

The correction does not:

- duplicate mono into a stereo bitstream and later call that a mono encoder
  setting;
- downmix only the positive after history decoding;
- replace the encoder with libvorbis, whose lineage is already used for
  mechanism development; or
- drop the failure from the record and continue with an incomplete nominal
  matrix.

The first two would change the meaning of the channel factor. The third would
destroy encoder-lineage separation. The fourth would hide a structural claim
limit.

## Corrected factor boundary

Factor freeze `lossytrace-v2-factor-levels-20260802-002` makes only the two
FFmpeg-native Vorbis transfer templates stereo-applicable. All 16 development
templates still cross mono and stereo. The six other transfer templates still
cross both, giving 32 development and 14 encoder-transfer concrete settings,
46 total.

The encoder-transfer partition must explicitly exclude a mono Vorbis transfer
claim. It can still test:

- within-source Vorbis history in mono and stereo during mechanism
  development through libvorbis;
- an independent FFmpeg-native Vorbis lineage in stereo during encoder
  transfer; and
- mono/stereo encoder transfer for MP3, AAC-LC, and Opus.

That is narrower than the original full interaction, but scientifically
honest. Any result must stratify the missing interaction and may not generalize
Vorbis encoder transfer to mono.

The corrected machine-readable factor file is
[`factor-levels.json`](../../benchmarks/audio-integrity-v2/factor-levels.json),
SHA-256
`4065553ef4fbe505ea0d79b149570bc1483396dbcc1de52597890e61f59481bd`.
Validation requires exactly the two named stereo-only templates, the 46-setting
count, and the corresponding transfer-claim exclusion.

## Next gate

Commit this factor correction independently. A subsequent toolchain recipe
must bind its exact commit and hash, remove the two unrealizable mono settings,
recompute compatible decoder-path counts, and itself be committed before the
next replay.
