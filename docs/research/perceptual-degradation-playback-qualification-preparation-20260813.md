# Physical playback qualification preparation - 2026-08-13

## Prepared signals

Two deterministic, synthetic 48 kHz stereo PCM-WAV fixtures are ready for the
declared RME ADI-2 Pro FS to Adam Audio T7V chain:

- a six-second channel check with a 440 Hz left signal and 660 Hz right signal,
  each peaking at -30 dBFS; and
- a twenty-second identical-stereo level signal containing only 500 Hz, 1 kHz
  and 2 kHz components at -30 dBFS steady-state RMS.

Both use smooth fades. The level fixture peaks below 0.062 full scale. This is
a conservative digital source level, not a sound-pressure-level calibration;
the acoustic level still depends on the RME and monitor settings.

Two generated replays were byte-identical. Their WAV hashes are
`9ad35f025a79d5373e7f3ba12c37531ac12879a8fbcca59dd322dec8899f93d2`
and
`3f6c800d6cd2800b1f5bd5d56747cd817cc7b13947bf8170226efed9f422fc7a`.
The bound loopback server accepted the private map and parsed both WAVs through
the existing integer-PCM contract. Synthetic replay files were moved to
recoverable Trash.

## Exact operator check

The future observed session is limited to these steps:

1. Set the RME/macOS output session to exactly 48 kHz; leave all declared
   effects off.
2. Use a quiet session and fixed listening position. Start with the RME or
   monitors low.
3. Start the exact-rate browser audio context and confirm it reports 48,000 Hz.
4. Verify the channel fixture, then play **Left only** and **Right only**. Each
   must come from only the corresponding T7V.
5. Play the level fixture and raise the hardware level only to a comfortable,
   conservative level. Keep it fixed for later testing. Never raise it to hear
   a subtle detail; lower it or stop immediately for discomfort.
6. Report only whether those checks passed. Do not give a degradation rating.

The earlier “funky sounds” confirmation is useful plumbing evidence but is not
reused as this exact-rate, channel, level or room observation.

## Boundary

No retained ODAQ reference, processed condition, score or sealed evidence is
used by this fixture. It collects no identity, rating or response. A successful
check qualifies only the declared physical playback plumbing; it is not
perceptual validation and does not authorize study stimuli.
