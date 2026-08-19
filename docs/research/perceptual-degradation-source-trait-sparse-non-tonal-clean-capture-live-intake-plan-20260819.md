# Perceptual-degradation sparse non-tonal clean-capture live-intake plan - 2026-08-19

**Status:** frozen before any live manifest, capture execution or audio access.

The user explicitly authorized conducting or arranging one safe clean capture
under the existing acquisition specification. This checkpoint records that
authority while preserving two narrower boundaries: external outreach is not
authorized, and payment or purchase is not authorized.

The live-intake runner accepts exactly one UTF-8 JSON manifest from an absolute,
regular, non-symlink path outside the repository. The manifest must explicitly
declare that it is not synthetic, remain at or below 65,536 bytes, contain no
audio path or payload, and pass the already-frozen eight metadata gates in their
original order. The runner does not resolve, inspect or open an audio file.

Two private replay reports must be byte-identical and remain outside Git. A
future public projection contains only the eight aggregate gate states and the
non-claim boundary; it excludes the manifest hash, declared audio hash, exact
identity, source group, rights-holder identity, filename, capture location and
channel details. Publication still requires a separate independent audit.

Read-only local device enumeration found an RME ADI-2 Pro input and Apple's
built-in microphone. Device visibility does not establish a complete physical
capture chain. The built-in microphone cannot satisfy the frozen provenance and
processing-control requirements without evidence of its complete transducer and
signal-processing path. The RME route still needs the exact attached microphone,
preamp or line-stage, channel mapping, firmware, gain, placement and event
details before an exact capture-execution checkpoint can be frozen.

No live manifest was read, no delivery was accepted, no recording was made, no
audio was accessed, and no source trait or manifest row was assigned.

Artifacts:

- [machine-readable live-intake plan](../../benchmarks/perceptual-degradation-v1/source-trait-sparse-non-tonal-clean-capture-live-intake-plan.json)
- [live-intake implementation](../../scripts/perceptual_degradation_source_trait_sparse_non_tonal_clean_capture_live_intake.py)
- [focused tests](../../scripts/tests/test_perceptual_degradation_source_trait_sparse_non_tonal_clean_capture_live_intake.py)
