# Factorial benchmark v2 preconditioning-audit result

Date: 2026-08-02

State: six synthetic cases are byte-identical within and across two complete
replays; the exact preconditioning module is frozen for a successor
construction recipe; no benchmark source waveform, benchmark case, feature,
score, or unopened label was read

## Replay result

The committed plan has SHA-256
`20e8675da9ef07bd2aa42a2b107bc348994d7b1cb2a1b60305737dfb38dd3113`.
Both complete path-free run reports have SHA-256
`66e3c81189eaa9df25130644b58068b4e962a8fbfeca0e86e674c383e6dad5df`.
The attested result is
[`preconditioning-observed-20260802-001.json`](../../research/sources/evidence/preconditioning-observed-20260802-001.json),
with SHA-256
`50883fbc74e897c7048b95148765651790cf8fb24b7335f29b7cd08fa6b93456`.

Every case was executed twice inside each replay. Output WAV bytes and decoded
signed-s16le hashes matched exactly. The two full reports also match
byte-for-byte.

## Covered paths

The evidence covers native `pcm_s16le`, `pcm_s24le`, and `pcm_f32le`; mono and
stereo input; mono and stereo target treatments; native-rate and 44.1/48 kHz
resampled paths; bounded provider windows; and the identity-hashed long-window
crop.

The long s24 stereo case selected native frames 21,211 through 550,411 and
produced exactly 576,000 mono frames at 48 kHz. The bounded f32 stereo case
produced exactly 167,580 mono frames at 44.1 kHz. Native-rate cases retained
their exact declared frame counts. These are deterministic plumbing facts, not
detector measurements.

The path-free result contains only synthetic fixture identities and hashes. It
contains no benchmark group, member, artifact, path, feature, score, or label.

## Disposition

The preconditioning module may now be bound by an exact benchmark-construction
recipe. That recipe must still preregister its disk bound, content-addressed
or recipe-addressed output layout, atomic checkpoints, codec-intermediate
retention policy, per-cell integrity record, wrapper/analysis-decode checks,
one-worker execution, and resumability validation before benchmark audio is
generated.
