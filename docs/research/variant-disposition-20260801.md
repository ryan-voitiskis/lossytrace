# Existing detector evidence and disposition

**Scope:** consumed development and external-transfer evidence only
**Decision:** no prior policy is eligible for promotion

The earlier work produced roughly 33 research checkpoints, not 33 production
candidates. Most checkpoints were threshold, representation, or transfer
experiments around a small number of signal families. Treating them as a large
candidate pool would overstate both their independence and their evidence.

## What the variants established

| Family or checkpoint | Reproducible finding | Disposition |
| --- | --- | --- |
| Feature-v0 edge, hole, and rupture conjunction | The original rule detected 4/320 controlled positives at 0/240 pilot alerts. A nested exact-grid search reached 20/320 at its strict zero-alert setting. | Keep the support and measurement plumbing; the measurements are not a useful classifier by themselves. |
| External C4DM detector | Detected 61/64 sampled positives but labelled 30/48 sampled negatives, including low-pass controls. | Reject. It violates the primary safety requirement. |
| Random-fold CNN ensembles | Reached high in-domain AUC and useful recall, then collapsed across sparse and source-domain transfer. | Reject random-fold performance as evidence. |
| Leave-one-domain CNN/CRNN variants | The five CNN representation/training variants produced 24–99 false positives out of 530 negatives. The paper-aligned CRNN reached AUC 0.5155 with 27/250 false positives; paired and broader training remained source-specific. | Reject blind universal classification. The models learned content/source identity more readily than codec history. |
| Long-block framing | Detected 180/192 public controlled positives at a zero-public-negative boundary, but one repeatable tonal NSynth PCM control raised the boundary and reduced combined recall to 133/404. No scalar template was safe and useful in every grouped fold. | Retain as a diagnostic; reject as a policy. |
| AAC quantization error | The published fixed boundary detected 308/404 positives and alerted on 44/197 negatives. A boundary above all observed negatives detected 17/404; grouped shape rules still produced false alerts. The companion-code terms also prohibit commercial use. | Negative scientific evidence only; do not add the private probe or companion source to the product. |
| Explainable SQAM candidate | The frozen transfer produced 2/140 PCM false positives, 85.4% supported recall at 55.0% coverage, and four AAC invariant-group mismatches. | Reject. Preserve the normalization and one-use gate lessons. |
| v28 conservative two-grid edge | Strong scoped recall, but the MUSDB transfer produced 3/600 false positives, all on deliberately bandwidth-limited PCM controls. | Reject the policy. Reuse its two-grid and performance infrastructure. |
| v29 verified MP3 confirmation | The observed screen had 0/796 supported-negative alerts, 73.7% positive coverage, and 80.3% supported recall. On the frozen independent DEMAND/MAESTRO transfer it kept 0/144 false positives but detected only 1/18 supported Apple AAC and 7/18 supported MP3 cases. | Reuse the confirmation and support machinery, not its policy or thresholds. |
| v30 AAC phase | Added five supported PCM false positives for one incremental true positive over v29. | Reject. |
| v31 MP3 frame evidence | Added zero false positives but no incremental MP3-128 detection on the independent corpus. | Reject as non-useful. |
| v32 exact MP3 hybrid sparsity | Outside its 24-group selection subset it detected 125/126 MUSDB MP3-128 and 120/126 Apple AAC-128 cases with zero supported-negative alerts. It detected 0/17 supported DEMAND cases in both target classes. | Keep the exact ISO Layer III hybrid front end as the one defensible research direction; reject the locked statistic and rule. |
| v33 exact hybrid tail flatness | Recovered all 17 supported DEMAND cases in both target classes with zero supported-negative alerts, but detected only 76/150 MUSDB Apple AAC cases and changed decisions in eight SQAM AAC invariant groups. | Keep only as evidence that content normalization and phase aggregation need work; reject the rule. |
| v32 + v33 union | Reached 150/150 MUSDB MP3, 146/150 MUSDB Apple AAC, and 17/17 supported independent cases in each target class with zero supported-negative alerts. It retained all eight SQAM invariance mismatches and was assembled post hoc. | Diagnostic only. It is not a frozen candidate and must not be renamed v34. |

## Shortlist

Only one direction remains defensible: the exact MP3 hybrid-transform
measurement, narrowed to detecting MP3-like transform history and kept behind
the experimental evidence contract. Its ISO Layer III analysis basis is more
specific than a spectral cutoff, and the retained evidence shows both a real
signal on music and a clear source-content failure that can be tested directly.

The earlier v29 periodicity confirmation can remain a diagnostic or support
guard, but it is not counted as a second independent evidence family and its
policy is not a candidate. AAC, Opus, and Vorbis remain out of scope for a
positive assessment unless a future independently supported family emerges.

## Fixed ablation sequence

The exact-hybrid direction gets one controlled ablation table rather than a new
sequence of numbered policies:

1. **Front-end replay:** reproduce the archived v32 coefficient summaries on a
   fixed observed subset with the exact pinned implementation.
2. **Scale normalization:** compare per-granule RMS normalization with robust
   subband-relative normalization; do not change the support population.
3. **Phase and time aggregation:** compare the locked single-bin aggregate with
   median-of-regions and phase-stable summaries designed before examining the
   failed SQAM case values.
4. **Content guard:** add one predeclared tonal/sparse support guard and measure
   its effect on every source-domain fold.

Each row reports support, source-group false positives, MP3-128 recall, gain and
trim stability, and leave-one-source-domain-out behavior. A row is discarded
immediately if any observed source-domain fold produces a hard-negative alert
or if it merely trades the MUSDB and DEMAND failures. Threshold sweeps over the
consumed SQAM mismatch cases are prohibited.

If none of these ablations is both safe and useful across observed domains, the
recommended decision is to keep LossyTrace as a verdict-free measurement and
evaluation toolkit and stop candidate tuning until a materially new signal or
new data source is available.
