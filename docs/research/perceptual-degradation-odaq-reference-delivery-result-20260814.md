# ODAQ clean-reference private delivery result - 2026-08-14

**State:** exact 16-reference canonical integer-PCM delivery complete; two
private replays and out-of-band attribution verified byte-identical

## Outcome

The responsible-human authorization was committed at `6ca44f9` and passed
exact-head CI before the private runner was implemented. The runner was then
committed at `3357ac7`, passed 868 local tests with 12 expected skips, and
passed both jobs in
[exact-head CI run 31764324379](https://github.com/ryan-voitiskis/lossytrace/actions/runs/31764324379)
before any retained WAV payload was read.

The authorized execution reverified the exact acquired source inventory and
projected all 16 clean references twice, serially, into two fresh private roots
outside the repository. The complete replay trees, audio inventories, and
attribution attachments are byte-identical. Private paths and per-reference
hashes remain outside the committed result.

## Aggregate delivery evidence

- input inventory: 16 clean references, 54,633,154 bytes, 48 kHz stereo;
- source encodings: seven IEEE float32 WAV and nine extensible 24-bit integer
  WAV;
- output inventory per replay: 16 canonical RIFF/WAVE integer-PCM files,
  54,631,346 audio bytes;
- output encodings: seven signed 32-bit and nine signed 24-bit PCM files;
- output inventory SHA-256:
  `66e20ac42ae618eb54a09fa91423f339fdca84be3aa3d7a779b220b57faf2abe`;
- all 32 output files independently accepted by `ffprobe` as 48 kHz stereo
  `pcm_s24le` or `pcm_s32le`;
- frame range preserved from 360,701 through 576,008 frames;
- no output partials or unexpected source/output files; and
- one worker with the 15 GiB reserve preserved. About 79 GiB remained after
  execution.

The nine integer inputs received container-only canonicalization with their PCM
payload unchanged. The seven float inputs received the frozen deterministic
float32-to-signed-int32, nearest-ties-to-even projection. There was no dither,
gain, normalization, resampling, or channel transformation.

## Attribution

Each replay carries a byte-identical out-of-band attribution attachment with 16
opaque delivery mappings and the 30 frozen licence records referenced by those
mappings. The attachment is bound to the committed attribution audit and has
aggregate SHA-256
`9bf06ed7f7acc8979a5d58fca4f78e6dca31379da25d844b9f46da94eb0295a2`.
Audio metadata was not rewritten.

## Boundary preserved

Only retained clean-reference reading and the authorized delivery projection
occurred. No ODAQ processed condition, published score, metric, degradation
rating, listener response, or sealed evidence was opened or collected. No
public verdict was emitted.

These copies are development-only delivery plumbing from one provider. Their
determinism is not stimulus generation, perceptual truth, metric evidence,
listening evidence, independent transfer, or a validated full-reference
oracle.

## Next gate

The frozen 112-case retained-drift validation protocol is a different authority
boundary. It still requires a separately committed responsible-human
authorization before these delivery copies may be used for controlled drift
corrections or real-content oracle validation.

Machine-readable evidence is in
[`odaq-reference-delivery-result-20260814.json`](../../benchmarks/perceptual-degradation-v1/odaq-reference-delivery-result-20260814.json).
