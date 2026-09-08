# Global-search workload result — 2026-09-08

State: **audited synthetic workload margin passed**. This is an engineering
qualification, not a perceptual-quality result.

The [frozen protocol](perceptual-degradation-global-workload-qualification-20260908.md)
was committed locally at `93c5607005801a4cce34d8454b2d20b2d26a8c4a` before the
single invocation. It was not externally published before observation.
The [complete synthetic evidence](../../research/toolchains/evidence/perceptual-degradation-alignment-global-synthetic-20260908-001.json)
retains all 16 planned slots and their stage CPU/wall times.

All 16 slots completed. Eight full-size global-pair comparisons covered
**30,784 candidate pairs**, with every native result byte-identical to v4.
Every completed evidence record repeated across the two rounds after excluding
only the six prospectively named timing fields. All inputs were unchanged,
both native paths recorded zero fallback, and all four replay edges passed.

| Construction | Full alignment, round 1 | Full alignment, round 2 | Alignment support |
| --- | ---: | ---: | --- |
| Quantized LCG | 100.820 s | 91.945 s | Supported |
| Dense floating-point LCG | 111.414 s | 114.841 s | Supported |
| Mixed scales | 112.027 s | 108.639 s | Supported |
| Sparse bursts | 28.915 s | 33.290 s | Unsupported: insufficient active audio |

Every full alignment finished under the prospective **120-second** margin
gate within the unchanged 180-second case limit. Sparse bursts correctly abstain:
their 2.4 active seconds do not satisfy the unchanged four-second minimum.

An independent saved-artifact audit reconstructed the result and all four
construction hashes, verified all 16 recorded input hashes, checked the first
round's earlier snapshot and confirmed exact four-JSON-plus-library retention.
It performed no native execution or alignment and retained no waveform/array.
The published auditor matches the helper used; nine constructed auditor tests
passed. The implementation/protocol also passed 47 focused tests.

## What this establishes—and what it does not

The native global implementation passed these exact workload and equivalence
checks. It is reasonable to test the full real-reference/codec path next.
It is not evidence that the earlier real-source hotspot has been fully
explained, nor a guarantee of codec throughput on other signals or machines.
All candidate lags, sample strides, numerical semantics and thresholds remain
unchanged; finite tests are not a universal equivalence proof.

The component comparisons always run Python before native, so timing ratios
do not isolate order, caching or scheduling. Full-alignment time excludes
construction, initial hashing, library loading and codec overhead. Native
accurate-sum work remains data dependent. The earlier v4 canary's eight timeouts
remain a valid frozen negative.

The next real canary needs a separate hash-bound scope and passing exact-head
CI under the standing technical authority. This synthetic batch is consumed
and must not be rerun. Metrics, playback/capture, human responses, source-trait
assignment, training and public verdicts remain closed. The objective is incomplete.
