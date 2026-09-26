# Source-trait provider-capability screen - 2026-08-14

**Status:** a bounded official-record screen found a plausible provider-level
route for the missing quiet source-trait negative, but no exact quiet member
and no naturally clipped candidate. SONYC's calibrated, common capture chain
can support a later quiet audit. Freesound exposes a later item-search
mechanism, but its provider schema does not establish capture-chain clipping.
No audio, exact sound record, exact member metadata, metric, score, listener
response or sealed evidence was opened.

## Proof boundary

The frozen
[`source-trait identifiability contract`](perceptual-degradation-source-trait-identifiability-20260814.md)
requires more than a waveform descriptor. A quiet member needs absolute PCM
level and nonzero activity measurements plus a preserved source-gain record
and exclusion of later attenuation. A naturally clipped member needs plateau
or saturation support plus a source- or capture-chain clipping record and
exclusion of intentional flat-top waveforms.

This screen inspected provider-level primary records only. It did not search
the Freesound catalogue, inspect an exact public sound record, select a member,
open audio or assign either trait. Its failure to find a collection-level
naturally clipped candidate is a bounded result, not a claim that none exists
anywhere.

## Quiet route: SONYC-Backgrounds

The official
[`SONYC-Backgrounds` record](https://zenodo.org/records/5129078) describes
10-second WAV recordings from the SONYC acoustic sensor network and licenses
the collection under CC BY 4.0. The already bound
[`SONYC source-identity audit`](sonyc-source-identity-audit-20260802.md)
records identical microphones and gain settings for the collection. The
primary
[`SONYC system paper`](https://www.justinsalamon.com/uploads/4/3/9/4/4394963/bello_sonyc_cacm_2018.pdf)
documents calibrated MEMS hardware with a 32--120 dBA dynamic range, random
10-second capture and lossless FLAC upload.

That evidence makes SONYC a plausible preserved-level provider route. It does
not identify a naturally quiet member. Absolute level, nonzero activity and
the absence of any post-capture attenuation remain unobserved. The disposition
is therefore `provisional_quiet_provider_capability_exact_member_audit_required`,
not a quiet candidate or trait assignment.

## Clipped route: Freesound search only

The official
[`Freesound API v2 documentation`](https://freesound.org/docs/api/resources_apiv2.html)
supports text search across names, tags, descriptions and original filenames;
filters on file type and item-level licence; and authenticated download in the
original uploaded format and quality. Those fields could support a later
bounded search for a CC0 or CC BY WAV/AIFF item whose uploader explicitly
documents capture overload.

They do not establish that such an item exists or is eligible. Tags and free
text are not structured capture-chain provenance, a lossless container does
not prove absence of prior lossy coding, and provider-level fields do not
exclude an intentionally flat-topped source. No catalogue query or exact sound
record was opened. The disposition is therefore
`search_mechanism_only_no_naturally_clipped_candidate_identified`.

## Consequence and next gate

The missing-trait bottleneck is now asymmetric:

- quiet has a provenance-bearing provider route but still requires separately
  authorized exact-member metadata and transformation-provenance inspection
  before any audio descriptor pass; and
- naturally clipped still lacks a candidate. A later metadata-only search must
  first require explicit capture-chain clipping, permissive item rights,
  original lossless upload and intentional-waveform exclusion. If those cannot
  be established before audio access, the route must be rejected.

No source-trait manifest, source successor or metric successor is selected.
No human collection, no-reference work or public verdict is authorized. The
public CLI is unchanged.

Machine-readable artifacts:

- [`provider-capability observation`](../../research/toolchains/evidence/perceptual-degradation-source-trait-provider-capability-screen-20260814-001.json)
- [`validator`](../../scripts/validate_perceptual_degradation_source_trait_provider_capability_screen.py)
- [`tests`](../../scripts/tests/test_perceptual_degradation_source_trait_provider_capability_screen.py)
