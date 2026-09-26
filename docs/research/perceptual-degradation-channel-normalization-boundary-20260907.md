# Channel normalization and alignment support — 2026-09-07

Status: the declared 18-case synthetic audit is complete, with two full
byte-identical replays. It selects an information-preservation boundary:
alignment diagnostics do not authorize gain, polarity or channel changes.
No actual normalization policy or perceptual metric is validated. The plan
was written before synthetic execution and is published with its development
results; this is not independent preregistered scientific validation.

## What the existing implementation actually does

The [restart review](perceptual-degradation-strategic-review-20260905.md) raised
the possibility that independent channel corrections could remove differences
that the perceptual target ought to retain. Inspection of the bound alignment
code narrows that concern: it estimates and reports channel gain and polarity;
it does not apply those corrections or return corrected waveform samples.
All 18 executions leave their input arrays unchanged.

The existing score-free oracle also does not promote alignment support to a
quality verdict. Its original assembler accepts all 18 alignment records, but
returns `execution_blocked` for the 15 supported alignments and
`unsupported_alignment` for the other three. Every perceptual output stays
unavailable and support remains false. This is evidence about an existing
safety boundary, not a demonstrated current metric-normalization bug.

The new question is prospective: what information would a future gain-invariant
comparison discard, and what can the current alignment support record establish?

## Declared constructions and exact comparison

Two six-second, 2-kHz integer stereo families are generated in memory. A fixed
integer recurrence supplies pairs `(a,b)` for u, while v uses `(-b,a)`. Thus
u and v have exactly equal energy and zero whole-record cross product. The
first stereo reference is `(u,v)`; the second is `(u,(3u+v)/4)`. The second
family is deliberately correlated and has unequal channel energies. These are
structural numerical fixtures, not natural sources, full-band recordings,
independent source groups or listening stimuli.

Each family receives all nine declared matrices: identity, common half gain,
common polarity inversion, left-only half gain, right-only polarity inversion,
half gain with opposite channel polarities, a channel swap retaining the
declared `[L,R]` map, mid signal copied to both channels, and a zero right channel.
All are development constructions, not actual codec operations or human labels.

At the known zero lag, let x be the reference and y the constructed test:

```text
Common fit:       g   = sum_c dot(x_c,y_c) / sum_c dot(x_c,x_c)
Independent fit:  g_c = dot(x_c,y_c) / dot(x_c,x_c)
```

Report the squared residuals for y−x, y−g*x and y_c−g_c*x_c, each divided by
total reference energy. These fit the reference to the test, not the test to
the reference. They are exact rational signal calculations, not calibrated
quality or audibility scales. No fitted gain is inverted and no corrected
waveform is produced. In particular, a zero fit does not permit reconstruction
of a dropped channel.

Direct sample products and pointwise residual sums are checked independently
against matrix/Gram identities for every case. The original alignment receives
exact binary-float views of the same arrays and its unchanged limits. Its
estimated delays and gains remain separate from the known-zero-lag projections.

## Results that change the next action

For the equal-energy orthogonal reference, the exact residual ratios are:

| Construction | Unaltered | Common signed-gain projection | Independent signed-gain projection | Original alignment |
| --- | --- | --- | --- | --- |
| Identity | 0 | 0 | 0 | Supported |
| Common half gain | 1/4 | 0 | 0 | Supported |
| Common polarity inversion | 4 | 0 | 0 | Supported |
| Left half gain | 1/8 | 1/16 | 0 | Supported |
| Right polarity inversion | 2 | 1 | 0 | Supported |
| Half gain, opposite polarities | 5/4 | 1/4 | 0 | Supported |
| Channel swap, same declared map | 2 | 1 | 1 | Unsupported |
| Mid copied to both channels | 1/2 | 1/4 | 1/4 | Supported |
| Right channel zero | 1/2 | 1/4 | 0 | Unsupported |

Independent gains discard differences from both channel imbalance and relative
polarity. In the correlated family, right-polarity inversion exchanges mid/side
energy shares from 25/26 and 1/26 to 1/26 and 25/26, yet its independent-gain
residual is exactly zero. Common-gain projection retains residual 160/169.
This proves a loss of signal information, not that a listener must find the
change audible or materially worse. Common gain and global polarity are also
not assumed perceptually irrelevant merely because their fitted residuals vanish.

A degenerate independent fit assigns gain zero to a dropped channel and also
produces zero residual. The original alignment rejects both dropout cases with
`ambiguous_alignment_peak` and `gain_exceeds_limit`; the old oracle preserves
that rejection. Neither a zero fitted residual nor a standalone component
diagnostic may replace those support gates.

The correlated channel swap is alignment-supported, with correlation
0.948683298 in each channel. Its independent-fit residual is 1/10, and its
channel energy shares are reversed. Both dual-mono mixtures are also supported,
although their side energy becomes zero. Known channel remixing therefore
cannot be excluded merely by inspecting `supported`, even with unchanged
declared map labels. Additional topology/provenance and channel-preserving
evidence are needed before claiming that a metric view retains stereo information.

The orthogonal swap remains unsupported: its two channel estimates are +1 and
−1 samples, with lag spread 2.012318844. The aggregated common delay and drift
are zero even though `channel_alignment_disagreement` and
`clock_drift_exceeds_limit` remain in the reasons. Averaged diagnostics must not
override per-channel rejection. Its known-zero-lag coefficients are zero, so
they must not be substituted for the old aligner's nonzero-lag gain estimates.

## Two further limits exposed by the audit

For a zero test channel, the original low-level cosine helper returns −1 as an
invalid-energy sentinel. Its callers take an absolute value, producing a reported
channel correlation of 1 and minimum correlation of 1 in these unsupported
records. This is not a defined correlation with silence. The gain diagnostic is
−999 dB, another sentinel, and the combined support decision still abstains.
The bound code and results are preserved; a separately tested successor should
represent invalid correlation explicitly before downstream use of that field.

Whole-record channel geometry is also incomplete. For the orthogonal reference,
both channel swap and relative-polarity inversion preserve the reported energy
shares and zero cross product despite positive unaltered residual. These Gram
summaries cannot establish waveform identity or preserve all time/frequency
channel relations. They are not a validated spatial artifact profile.

## Selected boundary and remaining prerequisite

Alignment support remains a diagnostic property. It does not authorize sample
changes, prove channel fidelity, or establish that gain and polarity can be
ignored. Original channel relationships must remain available alongside any
future adjusted view. Before actual metric or listening preparation, a successor
must declare which differences belong to the target, which are documented
delivery nuisances, and how its view matches the human comparison. This audit
does not select common-gain correction as a replacement for independent gains.

The original alignment, oracle, thresholds, source outcomes and retained drift
negative are unchanged. No source, capture, real-audio, human, metric, training,
outreach, spending or public-verdict gate opens. The physical capture setup is
still missing, and the full research objective remains active and incomplete.

## Reproduction

```sh
python3 scripts/perceptual_degradation_channel_normalization_boundary.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_channel_normalization_boundary.py'
```

Two full CLI outputs are byte-identical. All 18 direct/Gram comparisons agree
exactly; all original alignment outcomes and oracle states are retained.
Twenty-five focused tests cover bindings, resource limits, strict integer shape,
exact matrix construction, zero energy/gain, input preservation, closed-form
residuals, all observed support outcomes, oracle abstention and the closed CLI.
The independent arithmetic uses the same mathematical definition but a different
calculation; it is not independent perceptual or population validation.

- [Declared plan](../../benchmarks/perceptual-degradation-v1/channel-normalization-boundary-plan.json)
- [Implementation](../../scripts/perceptual_degradation_channel_normalization_boundary.py)
- [Focused tests](../../scripts/tests/test_perceptual_degradation_channel_normalization_boundary.py)
- [Complete synthetic evidence](../../research/toolchains/evidence/perceptual-degradation-channel-normalization-boundary-synthetic-20260907-001.json)
