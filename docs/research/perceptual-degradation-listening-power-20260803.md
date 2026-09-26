# Perceptual-degradation listening power report - 2026-08-03

**Status:** score-blind design simulation complete; no listener count frozen and
no recruitment or collection authorized

## Question

This simulation asks how much controlled listening evidence is needed to apply
the preregistered audibility, equivalence, SDG-severity, and MUSHRA-loss gates.
It uses no audio, metric score, published row-level score, retained label, or
listener response. Its purpose is to reject underpowered designs before any
outcome can influence sample size or thresholds.

## Model and multiplicity

Each design is evaluated with 20,000 deterministic Monte Carlo replicates.
Audibility is simulated with listener and source random intercepts on the logit
scale plus Bernoulli residual variation. Severity uses listener, source, and
continuous residual components. The standard deviations are declared in the
bound simulation code and should be stress-tested against pilot evidence only
through a later score-blind amendment.

Intervals use a normal planning approximation with familywise alpha `0.05`
across four primary decision families, producing a one-sided threshold of
`2.2414027276`. This is a power-planning approximation, not the final
hierarchical analysis and not a substitute for source-group bootstrap
validation.

The frozen decision targets are unchanged:

- audible: lower bound above `0.5` and point estimate at least `0.75`;
- chance-equivalent: the multiplicity-adjusted interval lies wholly inside
  `[0.45, 0.55]`;
- material subtle impairment: the SDG interval lies below `-1.0`; and
- material intermediate/severe impairment: the MUSHRA loss interval lies
  above `10` points.

## Results

Powers below are evaluated at true audibility `0.80`, true SDG `-1.25`, true
MUSHRA loss `15`, and true transparent-condition response probability `0.50`.
Judgments are totals for one aggregate condition stratum, not the entire study.

| Design | Class | Listeners | Sources | Judgments | Equivalence | Audible | SDG material | MUSHRA material |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| d24-s12-j4 | candidate | 24 | 12 | 96 | 0.000 | 0.860 | 0.495 | 0.677 |
| d48-s24-j8 | candidate | 48 | 24 | 384 | 0.000 | 0.976 | 0.856 | 0.962 |
| d72-s36-j12 | candidate | 72 | 36 | 864 | 0.000 | 0.997 | 0.971 | 0.997 |
| d96-s48-j12 | candidate | 96 | 48 | 1,152 | 0.000 | 0.999 | 0.994 | 1.000 |
| d240-s120-j15 | feasibility stress | 240 | 120 | 3,600 | 0.850 | 1.000 | 1.000 | 1.000 |

All candidate designs have zero equivalence power because their
multiplicity-adjusted interval cannot geometrically fit inside the ten-point
probability band even when the estimate is exactly `0.50`. The stress design
shows that the target is mathematically attainable, but only at 240 trained
listeners, 120 source groups, and 3,600 judgments for each transparent
aggregate stratum under these assumptions. That is not an operational study
proposal, especially when multiple codec, domain, encoder, bitrate, and
negative-control strata must remain separate.

The point gate at true audibility `0.75` has at most roughly 50% power by
construction; a truth exactly on a decision boundary cannot be made reliably
positive by increasing sample size. Likewise, severity exactly at SDG `-1.0`
or MUSHRA loss `10` should remain indeterminate rather than being forced into a
material label.

## Decision

No candidate listener count is frozen. Human collection and recruitment remain
unauthorized. The current equivalence target is scientifically protective but
operationally dominant; relaxing it after outcomes are seen is forbidden.

The next score-blind design step may do one of the following:

1. define a scientifically coherent transparent aggregate stratum across many
   source groups while preserving codec, encoder, domain, and partition
   reporting;
2. increase source coverage and balanced incomplete-block allocation, then
   resimulate realistic total workload and multiplicity;
3. justify a different equivalence estimand or hierarchical partial-pooling
   decision before any pilot outcome is opened; or
4. retain the interval and accept that individual transparent-condition truth
   will often be `audibility_indeterminate` with explicit abstention.

Option 4 is a valid rigorous outcome. A study that cannot establish
transparency must abstain; it must not silently call the encode degraded or
weaken the transparent-lossy safety requirement.

## Reproducibility and limits

The machine-readable report binds the seed, variance assumptions, design grid,
replicate count, targets, powers, and fail-closed decision. Re-running the
bound code is byte-deterministic on the standard Python runtime.

This calculation does not yet model listener dropout, training failure,
missing trials, device-class interaction, bridge-mapping uncertainty, or the
full grouped-transfer allocation. It corrects across four primary decision
families but not the larger number of condition-level contrasts, so its
positive power estimates are optimistic while the failed equivalence result
remains decisive for the tested candidates. Those omissions make it
preparation evidence, not authorization. A final power amendment must include
them together with the actual frozen stimulus and playback design.
