# ODAQ clean-reference acquisition result - 2026-08-13

## Outcome

The authorized bounded acquisition completed all 16 exact clean
`reference.wav` members. The private retained inventory contains 54,633,154
bytes and has path-free inventory SHA-256
`d7f244da55b510b639300d55271b1ebd5fb9f7454b258bec30588bf18eefde2f`.
No audio or private path is committed to the repository.

The exact-head acquisition implementation was commit
`d94947177ffe2aad9744133d052b256181c1267e`; its
[CI run](https://github.com/ryan-voitiskis/lossytrace/actions/runs/31686727214)
passed before the successful resume.

## Observed reference formats

All 16 members are stereo at 48 kHz. Seven are 32-bit IEEE-float RIFF/WAVE;
nine are 24-bit integer PCM in WAVE_FORMAT_EXTENSIBLE containers. Frame counts
range from 360,701 to 576,008. These facts describe the clean provider files;
they do not assign impairment, quality, or codec history.

The version-1 private browser delivery layer accepts integer PCM only. The
seven float members therefore require a separately frozen deterministic
float-to-integer conversion before a common browser-delivery population can
exist. This acquisition did not convert audio or generate stimuli.

## Integrity and access evidence

A second pass independently checked all 16 retained files against the private
journal and committed authorization: byte length, SHA-256, CRC-32, frozen
membership, aggregate inventory hash, and FFmpeg codec/rate/channel/frame
geometry all matched. The retained partial directory was empty and no
unexpected WAV was present.

The successful resume made 372 bounded Range requests totaling 24,268,401
response bytes, below the frozen 58,720,256-byte cap. This count covers only
the successful resume, not the earlier fail-closed format-discovery attempts,
so it is not presented as an all-attempt transfer total. The full provider
archive was not persisted.

The two stopped partials and the superseded empty journal remain in a private
audit quarantine outside the research corpus. They are not included in the
16-reference inventory and no private quarantine path is published.

## Boundary and next gate

Processed ODAQ conditions, published listening scores, metric scores, stimulus
generation, perceptual metrics, sealed evidence, and listener responses all
remain unopened or unauthorized. The one-provider development-only and
attribution limits remain in force; this inventory cannot support independent
transfer or final validation.

The next permitted repository step is a score-blind preparation plan for
deterministic integer-PCM delivery, attribution attachment, and physical
playback qualification. Actual conversion, stimulus generation, and listening
remain blocked until a separately committed successor authorization exists.
