# Perceptual-degradation sparse non-tonal successor metadata audit - 2026-08-19

**Status:** five exact Freesound routes were audited from public/provider
metadata only. None qualifies for audio access under the frozen successor
contract.

All five records expose a provider-original CC0 WAV route, but each fails at
least one pre-access requirement:

- `866967` identifies a balloon impulse and a complete recorder/microphone
  chain, but is only 1.414 seconds and discloses normalization plus fades.
- `273338` is a 5.954-second unprocessed booklet impact with a known recorder,
  but the microphone for one of its two channels is explicitly uncertain.
- `710084` is a 4.264-second rifle shot with an exact mid-side microphone chain,
  recorder and field reference, but its provider record does not state the
  transformation history.
- `73385` is only 1.091 seconds and describes its processing as “probably”
  absent, which is not an exact history.
- `728514` belongs to a designed-impact pack and lacks an explicit capture chain
  and transformation record.

The previous Freesound snap abstention remains frozen. No candidate was
downloaded, previewed, substituted or selected, and no descriptor was computed.
The duration rule was frozen for this successor search as a conservative
metadata margin; it is not a descriptor result or source-trait truth.

The next gate remains metadata-only: locate one different exact member with
permissive rights, a provider-original lossless WAV, a complete all-channel
capture chain, an explicit no-processing or trim-only history, and metadata
support for one natural transient lasting at least two seconds. That exact
member must be bound in a new checkpoint before audio access.

Artifacts:

- [frozen metadata audit plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-successor-metadata-audit-plan.json)
- [path-free metadata result](../../research/toolchains/evidence/perceptual-degradation-source-trait-sparse-non-tonal-successor-metadata-audit-20260819-001.json)
- [deterministic audit implementation](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_successor_metadata_audit.py)
