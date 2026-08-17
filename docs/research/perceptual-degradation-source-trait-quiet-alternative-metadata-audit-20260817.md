# Alternative-provider quiet metadata audit - 2026-08-17

**Status:** bounded metadata-only audit complete. One exact quiet metadata
candidate was identified. No audio sample, audio descriptor, provider score,
processed condition, codec, perceptual metric, playback, response, sealed
evidence, model, validation claim or verdict was accessed or produced.

## Outcome

The alternative-provider search identified
[Freesound sound 426894](https://freesound.org/people/danner/sounds/426894/)
as an exact quiet metadata candidate. Its public record:

- describes a distant, quiet, consistent city ambience recorded from a
  rooftop;
- identifies the Tascam DR100mk2 and its built-in cardioid microphone
  configuration;
- records capture gain `M9` and the 80 Hz capture high-pass setting;
- states that no processing was applied;
- lists the original upload as 96 kHz, 24-bit stereo WAV; and
- assigns CC0 1.0 rights.

Freesound's official
[API documentation](https://freesound.org/docs/api/resources_apiv2.html)
defines the listed type as the original upload type, and its
[FAQ](https://freesound.org/help/faq/) states that the original download is
returned without transcoding or editing. Together, these records clear the
frozen pre-audio identity, rights, original-lossless, quiet-scene,
capture-chain, preserved-gain and no-post-capture-attenuation obligations.

This does **not** establish quiet-trait truth. The uploader's scene description
cannot substitute for the frozen absolute-level and nonzero-activity
measurements, and neither measurement was authorized or run. The file was not
downloaded, selected for a partition or allocated to a study.

## Rejected routes

Five nearby public records were rejected before audio access:

- sounds 348829 and 761024 lack capture-gain and complete transformation
  records;
- sound 171740 states that no processing was applied but does not record the
  capture gain required by the frozen preserved-gain rule; and
- sounds 846064 and 857163 explicitly document normalization or gain changes.

This preserves the rule that a `quiet` title or tag, a lossless container, or
a recorder name cannot independently establish the required provenance.

## Relationship boundary

[Sound 427932](https://freesound.org/people/danner/sounds/427932/) is a related
quiet city-ambience record from the same uploader and similar elevated Berlin
capture context. It remains in the same conservative contributor/location/
recording-family group and is not an independent contrast.

The candidate is CC0, so attribution is not legally required. The prepared
optional credit is: `Sound 426894 by danner on Freesound.org, CC0 1.0`.

## Consequence and next gate

All seven required source-trait classes now have a candidate record, up from
six. That is candidate arithmetic only. Quiet and naturally clipped descriptor
confirmation remain closed, sparse and tonal still lack independent exact
contrasts, and relationships and partition allocation remain unfrozen. The
truth-bearing source manifest therefore remains unfrozen.

The next quiet gate requires separate authority to acquire the exact member
and run only the frozen absolute-level and nonzero-activity confirmation.
Naturally clipped confirmation, independent sparse/tonal records and allocation
remain separate gates.

Machine-readable artifacts:

- [audit plan](../../benchmarks/perceptual-degradation-v1/source-trait-quiet-alternative-metadata-audit-plan.json)
- [path-safe report](../../research/toolchains/evidence/perceptual-degradation-source-trait-quiet-alternative-metadata-audit-20260817-001.json)
- [validator](../../scripts/validate_perceptual_degradation_source_trait_quiet_alternative_metadata_audit.py)
