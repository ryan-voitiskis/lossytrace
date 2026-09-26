# LossyTrace 0.1.0-rc.1

This release candidate is a **verdict-free inspector and research benchmark**.
It does not fulfill the original objective of detecting whether audio ever
passed through a lossy codec. No historical encoder/codec or bitrate estimator
is shipped, and no measurement certifies clean or never-lossy provenance.

## What is available

- The Rust library and `lossytrace analyze` CLI report schema-version-1,
  feature-version-0 experimental measurements. Input audio is not modified.
- `lossytrace explain` describes every field, missing/support states, downmixing
  limits and alternative explanations without opening audio.
- The source release preserves benchmark construction recipes, source-group
  protocols, all previous negative results and sanitized aggregate evidence.
  Private corpora, private manifests and per-case outputs remain excluded.
- Native archives target Apple Silicon macOS and Linux x86-64, with packaged
  smoke-test records, checksums, dependency inventories, SBOMs and notices.
  Unmodified MPL-covered dependency source archives are included.

## Why this is not a detector

The pinned Lossprint external baseline passed software qualification, then
failed the prospectively fixed challenge. All 1,386 calls completed and their
replays and lossless wrappers agreed. It detected 317/381 controlled positives,
but also flagged 53/336 benchmark negatives across 6/30 source groups. Four of
six domains failed the safety gate. These related, consumed-development cases
do not estimate deployment error prevalence. Codec-family correctness among
detected positives was 281/317; source-bitrate accuracy could not be evaluated.

No model or threshold was tuned to repair that result, no failed groups were
discarded, and no sealed evidence was opened. Lossprint weights/code are not
bundled. The authorized fallback keeps useful inspection and reproducibility
tools while making the unmet detection objective explicit. Human listening,
audibility prediction and the former perceptual-degradation objective remain
outside this RC's claims.

Full protocol, counts and limitations:
[challenge result](https://github.com/ryan-voitiskis/lossytrace/blob/codex/codec-history-rc/docs/research/lossprint-challenge-result-20260927.md).
The bundle's `build-info.json` identifies its exact source commit; use that
revision when reproducing evidence rather than assuming the branch is fixed.

## Verification and limitations

The RC workflow requires two clean native builds and two deterministic archive
constructions to agree on each hosted runner. Packaged-binary tests cover help,
the embedded guide, generated PCM replay, WAV/AIFF and WAV/FLAC comparisons,
read-only input handling and invalid invocations. Publication additionally
requires green CI for the exact commit. These are software checks, not renewed
detector validation. Rebuild evidence covers two directories on the same
runner/compiler, not bit-for-bit equality across arbitrary hosts or toolchains.

The tested native environments are macOS 15 arm64 and Ubuntu 24.04 x86-64.
Archives are not Developer-ID signed/notarized, and other platforms are not
qualified. The inspector downmixes to float32 mono, analyzes at most 120
seconds by default, and retains known content-dependence and invariance
limitations. Sparse, silent or low-rate material can yield unavailable fields.
Do not use measurements for automatic deletion, retagging or authenticity
claims. No stable release, registry publication, main-branch merge or
Reklawdbox integration is part of this release candidate.
