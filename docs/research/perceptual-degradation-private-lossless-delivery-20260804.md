# Private lossless listening delivery - 2026-08-04

**State:** implementation prepared; browser delivery and physical playback are
not yet qualified; human collection remains unauthorized

## Purpose and boundary

This layer delivers private, hash-bound lossless PCM-WAV stimuli to a local
qualification page without committing audio, paths, assignments, responses,
or metric scores. It advances the listening infrastructure only. It does not
authorize a listening study, make a perceptual-quality claim, or qualify the
DAC, transducer, output mixer, room, level, latency, switching, or listener.

The existing synthetic player remains historical dry-run evidence. This is a
separate application so that adding local file delivery does not silently
change the exact sources bound by the synthetic observations.

## Runtime inputs

The operator supplies one private JSON delivery map outside the repository.
It contains:

- schema and state identifiers;
- an opaque manifest identifier;
- one session sample rate, either 44.1 or 48 kHz;
- `human_collection_authorized: false`; and
- one to twelve opaque stimulus identifiers with absolute private paths,
  SHA-256 digests, PCM format bindings, and channel counts.

The private map and every audio file must resolve outside the repository. The
server never prints a path. A browser-visible session projection contains only
opaque IDs, hashes, byte lengths, and audio geometry. It excludes condition
recipes, source roles, metric scores, private paths, identity, and responses.

This map is a delivery binding, not the final listening stimulus manifest. A
future study still requires the separately frozen source/condition manifest,
licence records, partitions, trial allocation, and responsible-human approval.

## Accepted audio

Version 1 deliberately accepts only RIFF/WAVE integer PCM with:

- mono or stereo channels;
- 16-, 24-, or 32-bit signed PCM;
- 44.1 or 48 kHz sample rate;
- internally consistent RIFF length, chunks, byte rate, block alignment, and
  non-empty frame-aligned payload; and
- a total size no greater than 32 MiB per stimulus.

FLAC is valid in the general stimulus schema but is not accepted by this
delivery implementation. Supporting it would require a separately bound,
deterministic decoder. WAVE_FORMAT_EXTENSIBLE and floating-point WAV are also
unsupported in version 1 rather than silently delegated to a platform decoder.

Every file is read and hashed before server startup. It is read and hashed
again immediately before each response so file replacement after startup
fails closed. The loopback server listens only on `127.0.0.1`, exposes an
exact static-file allowlist, has no POST or upload route, suppresses request
logging, and sends no-store and same-origin security headers.

## Browser decoding and playback boundary

The browser receives bytes from the same loopback origin and verifies:

1. successful non-redirected response;
2. `audio/wav` content type;
3. exact byte length;
4. exact SHA-256 through Web Crypto;
5. RIFF/WAVE and PCM geometry; and
6. exact agreement with the declared sample rate, channel count, and depth.

JavaScript converts integer samples to planar float32 itself. It does not call
`decodeAudioData`, create a media element, or accept a sample-rate mismatch.
The player requests an `AudioContext` at the session sample rate and rejects a
context that reports another rate. Audio buffers are created at that exact
rate. This proves the bound byte-to-Web-Audio-buffer path; it does not prove
that an operating-system mixer or physical device performs no later
conversion.

The qualification UI has verify, play, left-only, and right-only controls. It
has no form, rating, persistence, microphone, identity, upload, or response
submission path. Operator audibility statements remain out-of-band plumbing
checks and are not listening truth.

## Reproducible dry-run fixture

Tests construct a tiny deterministic PCM-WAV and delivery map inside an
ephemeral directory outside the repository. They validate server projection,
byte serving, mutation failure, private-path redaction, authorization failure,
sample-rate failure, JavaScript parsing, sample conversion, and forbidden API
absence. The fixture is deleted with its temporary directory and is never
committed or added to the retained corpus.

## Remaining qualification

Before `player_implementation_frozen` or `playback_qualification_frozen` can
become true, evidence must still bind and verify:

- a headed browser version and binary;
- successful same-origin fetch, SHA-256, PCM parsing, exact-rate context, and
  left/right playback using the ephemeral fixture;
- actual lossless study stimuli and source-by-source licences;
- a declared device, DAC/interface, amplifier, transducer, operating-system
  effects configuration, level-calibration method, and ambient-noise class;
- loop/switch discontinuity and latency behavior for the final trial player;
  and
- all unresolved privacy, retention, withdrawal, compensation, eligibility,
  and responsible-human fields in the listening gate.

Until those conditions are separately frozen, recruitment, participant
contact, human collection, response storage, and public interpretation remain
false.
