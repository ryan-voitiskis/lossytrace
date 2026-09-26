# Physical playback qualification result - 2026-08-13

## Outcome

The declared RME ADI-2 Pro FS to Adam Audio T7V chain passed the bounded
physical playback qualification. The browser audio context was running at the
required 48 kHz, macOS independently reported the RME as the default
two-channel USB output at 48 kHz, and no resampling was requested.

The responsible human confirmed:

- the left-only control played only through the left T7V;
- the right-only control played only through the right T7V;
- the session was quiet, used a fixed position, and had the declared effects
  off;
- a comfortable conservative level was set and held fixed; and
- no discomfort occurred.

This qualifies the declared physical playback plumbing. It is not an acoustic
SPL calibration, degradation rating, perceptual-quality result, or evidence
that any lossy condition is audible.

## Exact fixture evidence

The loopback session used manifest
`manifest-playback-qualification-0001` and player build
`player-lossless-qualification-v1`. The channel fixture passed browser
SHA-256 and PCM parsing at 1,152,044 bytes and 288,000 frames. The level
fixture passed at 3,840,044 bytes and 960,000 frames. Both were 48 kHz stereo
signed-16 PCM, and the browser reported no requested resampling.

The exact-head preparation commit was
`ce08bf4b8487abcdae8e1b48e757dfc2f115e967`; its
[CI run](https://github.com/ryan-voitiskis/lossytrace/actions/runs/31689599039)
passed before the observed session.

## Data and authority boundary

Only the two deterministic synthetic qualification signals were played. No
retained ODAQ reference, processed condition, score, metric, sealed evidence,
or degradation rating was opened or collected. After the checks, the
loopback server was stopped and the reproducible private fixture was moved to
recoverable Trash. The retained 16-reference corpus was untouched.

The next development step still requires a separate responsible-human
authorization to read and project retained references. Physical playback no
longer blocks that future gate, but conversion, study-stimulus generation,
metrics and listener collection remain unauthorized.
