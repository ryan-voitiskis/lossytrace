# ODAQ reference extractor preparation - 2026-08-04

**Status:** bounded extractor verified on synthetic ZIPs; live source track,
provider audio acquisition, processed conditions, scores, stimuli, metrics, and
listening remain unauthorized

## Result

The
[`reference extractor`](../../scripts/acquire-perceptual-degradation-odaq-references.py)
now implements the exact frozen-member delivery boundary without enabling it.
Before a member is opened it checks the derived `reference.wav` name, CRC32,
compressed size, uncompressed size, and ZIP compression method against the
committed freeze. It streams the member through a private partial file, verifies
the final CRC32 and SHA-256, parses the PCM-WAV geometry, flushes and syncs the
file, then atomically renames it to an opaque identifier.

The private acquisition journal supports restart and verifies every retained
file's size, hash, and PCM geometry before skipping completed work. Output must
remain outside the repository. The extractor rejects unsafe source identifiers,
non-empty unjournaled roots, unjournaled partial/final files, changed plans,
changed ZIP bindings, retained-file corruption, unsupported PCM, and any write
that would cross the 15 GiB reserve.

## Network and storage bound

Any future live run is limited to one worker, 64 KiB HTTP blocks, a 16-block
cache, and at most 56 MiB of cumulative Range responses. The bound exceeds the
46,721,638 frozen compressed reference bytes plus two blocks of conservative
rounding per member (48,818,790 bytes total), while remaining far below the
1,048,071,792-byte provider archive. The full archive may not be persisted.

## Test result

Thirteen focused tests pass. Synthetic PCM-WAV fixtures verify:

- reference-only selection when processed and score members coexist;
- opaque, atomic, byte-verified extraction and deterministic resume;
- exact-binding mismatch failure before a member write;
- disk-reserve failure before a member write;
- retained corruption failure on resume;
- tampered journal path rejection before retained-file access;
- repository-output and path-traversal rejection;
- range-budget coverage without permitting the full archive; and
- live-command refusal before provider access, including when a structurally
  valid authorization file is not separately committed and clean.

An actual CLI attempt using the current preparation plan as authorization also
failed at the local authorization gate. It made no provider request and created
no output root.

## Authorization boundary

Live mode pins the canonical metadata-freeze path and SHA-256, then requires a
separately committed and clean successor whose parent hash matches that exact
freeze, whose provider and reference arrays are unchanged, and which records
both the responsible-human choice of the narrow permissive track and a physical
playback declaration. Even that successor must leave
processed conditions, published scores, metrics, stimulus generation, and
listener collection closed at acquisition time.

No provider audio, retained audio, processed condition, listening score,
perceptual metric, stimulus, or listener response was accessed by this work.
