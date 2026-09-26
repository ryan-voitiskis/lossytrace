# Source-trait exact-member metadata audit - 2026-08-17

**Status:** bounded metadata-only audit complete. One naturally clipped exact
metadata candidate was identified; the SONYC quiet route was rejected under
the metadata-only rule. No audio sample, audio descriptor, provider score,
processed condition, codec, perceptual metric, playback, response, sealed
evidence, model, validation claim or verdict was accessed or produced.

## Outcome

The two missing source-trait routes resolved differently.

SONYC-Backgrounds remains a strong provenance-bearing collection, but it
cannot nominate an exact naturally quiet member from metadata alone. The
versioned CC BY 4.0 release documents 550 identifiable WAV members across 15
sensor groups, identical microphones and gain settings, lossless FLAC sensor
upload, and PCM-WAV distribution. Its exact-member fields are sensor, date,
quantized hour, instance and provider split. None is an absolute-level field.
The release's `background` status comes from fault and event-classifier
selection, not an absolute-level threshold, and the public record does not
exclude member-level post-capture attenuation. Calling any member `quiet`
would therefore require evidence outside this authorization.

The bounded Freesound search found one exact naturally clipped metadata
candidate: [sound 610933](https://freesound.org/people/unfa/sounds/610933/).
Its public record is CC0 1.0 and documents a physical recording chain at
192 kHz/24-bit, no processing or editing, and transient pops clipped because
the microphone gain was too high. The listed original upload is FLAC.
Freesound's official [API documentation](https://freesound.org/docs/api/resources_apiv2.html)
defines `type` as the original uploaded file type and its
[FAQ](https://freesound.org/help/faq/) states that an original download is
returned without transcoding or editing. This clears the frozen pre-audio
rights, lossless-origin, capture-chain, transformation and intentional-waveform
exclusion gates.

That is an exact **metadata candidate**, not clipped-trait truth. The frozen
plateau or saturation descriptor obligation was deliberately not run. No file
was downloaded, selected for a partition or allocated to a study.

## Consequence for the source manifest

The seven-trait candidate count moves from five to six:

- naturally clipped now has one exact metadata candidate;
- quiet still has none; and
- the earlier shared sparse/tonal candidate still does not provide independent
  sparse and tonal contrasts.

The truth-bearing source manifest therefore remains unfrozen. Scientific
coverage remains absent, and the objective audit remains incomplete.

## Attribution and grouping boundary

The clipped candidate is CC0, so attribution is not legally required. The
prepared optional credit is: `Sound 610933 by unfa on Freesound.org, CC0 1.0`.
Any later allocation must group the item conservatively with the uploader and
recording session rather than treating related uploads as independent.

The rejected SONYC route retains its existing CC BY 4.0 dataset attribution
record, but no SONYC member was nominated or acquired.

## Next gate

For quiet, either obtain provider clarification that establishes exact-member
level and gain-preservation metadata or separately authorize a frozen bounded
descriptor scan. The SONYC metadata-only route is exhausted.

For clipped, separately authorize acquisition of the exact member and the
frozen plateau or saturation confirmation before assigning the source trait.
Independent sparse and tonal exact-member contrasts and all partition
allocation remain separate gates.

Machine-readable artifacts:

- [audit plan](../../benchmarks/perceptual-degradation-v1/source-trait-exact-member-metadata-audit-plan.json)
- [path-safe report](../../research/toolchains/evidence/perceptual-degradation-source-trait-exact-member-metadata-audit-20260817-001.json)
- [validator](../../scripts/validate_perceptual_degradation_source_trait_exact_member_metadata_audit.py)
