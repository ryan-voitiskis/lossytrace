# Factorial benchmark v2 analysis-manifest correction 001

Date: 2026-08-02

State: metadata-only tool-binding correction frozen after the first invocation
stopped before retained-artifact access; no feature or score opened

## Trigger

The original compositor assumed every expanded encoder setting named exactly
one `binding_tool_id`. Its first invocation rejected the Apple AudioToolbox AAC
setting before iterating any constructed artifact because that setting binds
both the FFmpeg command binary and the Apple verification tool.

No private manifest or run report was written. No retained artifact byte,
decoded PCM, feature, model output, or transfer score was read.

## Correction

The expanded setting already declares one exact `tool_id` used by its encoder
command and a non-empty set of additional exact `binding_tool_ids`. The
corrected compositor:

- uses `tool_id` for the factorial encoder registry's required binary binding;
- requires that tool to occur in `binding_tool_ids`;
- requires every additional binding tool to exist in the frozen toolchain; and
- retains all binding tools in the generated recipe's tool-ID set.

No source, cell, factor, recipe order, partition, provenance record, artifact,
validation profile, or evidence boundary changes. Two fresh complete replays
remain required.
