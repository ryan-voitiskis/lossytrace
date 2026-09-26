# Factorial benchmark v2 analysis-manifest correction 002

Date: 2026-08-02

State: metadata-only decoder-scope correction frozen after replay stopped on
the first negative cell; no feature or score opened

## Trigger

The first invocation under correction 001 rehashed two retained artifacts
totalling 2,210,488 bytes. It then attempted to materialize the second cell,
which was a negative PCM reference, and stopped because that assignment row did
not repeat `analysis_decoder_id`.

This omission is intentional in the assignment schema: all cells inherit the
single globally frozen canonical lossless-PCM decoder, while controlled
positives also carry the field as explicit construction lineage. No private
manifest or run report was written, and no artifact was decoded for analysis.
No feature, model output, or transfer score was opened.

## Correction

The compositor now obtains `analysis_decoder_id` once from the frozen
toolchain's global `analysis_decoder_binding` and materializes it for every
case. If a cell explicitly names an analysis decoder, the compositor requires
exact equality with the global binding. An absent per-cell value inherits the
global value; a conflicting value stops the run.

No source, artifact, PCM, factor, recipe, partition, provenance record,
validation profile, or evidence boundary changes. Two fresh complete replays
remain required.
