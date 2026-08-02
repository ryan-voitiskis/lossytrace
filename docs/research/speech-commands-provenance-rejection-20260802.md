# Speech Commands v0.02 provenance rejection

Date: 2026-08-02

State: provider-provenance rejection evidence only; corpus not allocated

## Outcome

Google Speech Commands v0.02 is removed from the Tier A source-candidate
inventory. Its distributed files are PCM WAV, but the primary paper states
that the open contribution site received OGG-compressed captures from the
WebAudioAPI, stored those OGG files, and later used FFmpeg to decode and
resample them into the released 16 kHz WAVs. The paper also states that the
majority of the dataset came through that path.

Other contributed material began as varying-rate WAV and followed a separate
resampling path. The documented release identity does not expose a per-file
origin-path field, pre-OGG PCM, exact OGG codec, encoder implementation, or
encoder settings. The corpus therefore cannot be a confirmed no-lossy
negative collection and cannot supply controlled positives with known codec
history.

This is a rejection of the corpus for this benchmark role, not a criticism of
Speech Commands as a speech-recognition dataset. The path-free evidence is
[`research/sources/evidence/speech-commands-v0.02-provider-provenance-rejection-20260802.json`](../../research/sources/evidence/speech-commands-v0.02-provider-provenance-rejection-20260802.json).

## Evidence boundary

The decision is grounded in version 1 of the primary
[`arXiv:1804.03209` paper](https://arxiv.org/abs/1804.03209), whose source
archive and `main.tex` were bound before interpretation:

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| arXiv source archive | 15,170 | `4d9cab440aae302461c96a5000efd416a06915cd9b11414fa4369240ad240d0a` |
| `main.tex` | 34,331 | `df5ffe756fad80f98e9685284a892bf5831ca920ed3f3f9b090c53a2d8025547` |

The official
[`Speech Commands launch post`](https://research.google/blog/launching-the-speech-commands-dataset/)
and TensorFlow's
[`_nohash_` speaker-grouping implementation](https://github.com/tensorflow/tensorflow/blob/master/tensorflow/examples/speech_commands/input_data.py)
remain useful provider context, but neither resolves the per-file capture
path. The rejection does not depend on opening the full archive or inspecting
any detector output.

The provider artifact was observed as:

| Field | Value |
| --- | --- |
| Filename | `speech_commands_v0.02.tar.gz` |
| Bytes | 2,428,923,189 |
| Provider MD5 / strong ETag | `6b74f3901214cb2c2934e98196829835` |
| Generation | `1523475715344020` |
| Last modified | 2018-04-11 19:41:55 GMT |

A resumable 227,831,808-byte partial is retained privately. It is explicitly
not scientific evidence: the complete artifact was not acquired or verified,
and no benchmark audio, source selection, or score was produced from it.

## Allowed future role

Speech Commands may only re-enter through a separate preregistration as
`tier_c_unknown`, `lossy_original_diagnostic` evidence. Such a diagnostic must
remain outside every negative-reference pool, controlled-positive pool,
accuracy denominator, candidate-selection rule, and external-transfer gate.
Its purpose could be to describe detector behaviour on mixed, unresolved
histories—not to estimate provenance accuracy.

## General lesson

Container format is not source history. A PCM wrapper establishes the current
representation, not the absence of an earlier perceptual encoding. Every
future Tier A candidate must bind its recording and release processing path
before group counts are allowed into the inventory. If that path is mixed and
not recoverable per file, conservative grouping cannot repair the label.

No full acquisition, benchmark derivative, mechanism score, candidate
decision, or transfer evidence was opened by this rejection.
