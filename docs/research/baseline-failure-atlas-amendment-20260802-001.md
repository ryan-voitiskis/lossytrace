# Baseline failure-atlas amendment 001 - 2026-08-02

**Frozen:** after the retained pilot comparison stopped and before any P1 case
was scored

**Scope:** pilot reproducibility interpretation and duration reporting only

**Unchanged:** detector revision, weights, plugin output, 0.5 window threshold,
25% file threshold, P1/P2 populations, metrics, hard-negative treatment, and
holdout boundaries

## Trigger

The preregistration assumed that 104 case IDs shared by the historical
112-file Cannam pilot and the retained compact corpus were full-duration
lossless-wrapper equivalents. The newly bound replay showed that premise was
false:

- all 104 historical inputs had 148-675 plugin windows, with median 498;
- all 104 retained compact inputs had 30-32 windows, with median 30; and
- the compact-corpus manifest explicitly fixes a 30-second analysis maximum.

The replay therefore compared full tracks with retained excerpts. It was not a
valid same-input environment regression.

## Observed stop

The comparison stopped before P1 as required. Across the 104 shared case IDs:

- controlled-positive decisions were 61/64 in both reports;
- negative positive-decisions changed from 22/40 to 23/40;
- one `gain_only_pcm` negative crossed the fixed file boundary, from a
  historical full-track positive-window fraction of 0.195279 to 0.266667 on
  the 30-window excerpt;
- the median absolute positive-window-fraction difference was 0, the mean was
  0.036523, and the maximum was 0.729032; and
- all 104 window counts differed.

This is evidence that the plugin's file aggregation is duration/excerpt
sensitive. It is not evidence of model, host, or threshold drift.

## Reproducibility correction

The invalid historical comparison remains retained as an audit result and is
not relaxed to permit one mismatch. Instead, the environment gate is corrected
to a same-input replay:

1. score the frozen 104-case retained manifest;
2. replay from case/audio/tool-bound partials without changing inputs; and
3. require byte-identical deterministic raw output.

That corrected gate passed. Both raw reports had SHA-256
`d7a23b1ffada9745ac4dcea2c61e43874aaf09f1a2ee91b3d9b06970496f5f24`.

P1 may proceed because it is explicitly a new fixed-rule measurement of the
complete retained files, not a reproduction of the historical full-track
accuracy. P1 results must report plugin window-count distributions and fixed
duration bands so excerpt length cannot remain hidden in a headline metric.

## Evidence commitments

| Artifact | SHA-256 |
| --- | --- |
| historical private archive | `c79c23a93b7e9762b91bd8ad02f810da2087ded7966811fcb5b55d0af11eb5fd` |
| historical 112-case report member | `cb322b253f291419f1232c1a66425cfe23b27566a991a851ddcfa3f165df6e4d` |
| retained 104-case replay manifest | `94341638e2a89932157bf5c78558d9f1f20d4f07c41c9bfbeee3be9a337f9d9e` |
| first retained replay raw report | `d7a23b1ffada9745ac4dcea2c61e43874aaf09f1a2ee91b3d9b06970496f5f24` |
| invalid-duration comparison report | `abd6baa1b470214f0c29060baa5f89e241a7a27b8c41b96334cbf6f2c5ee298b` |
| exact Cannam plugin binary | `9e989b81061fcc5b6186f7a0ed2534400f6b8de1e1ee711a1f76aee1c547c9e6` |
| Vamp host binary | `a9c197e1d10a4d03748ad2b9a3712013cf9ac8c46dd797dbba44f7f809904a64` |

The future SQAM codec-only subset and release holdout remained unopened. No
candidate, support rule, threshold, or public behavior changed.
