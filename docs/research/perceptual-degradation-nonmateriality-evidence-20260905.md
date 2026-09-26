# Nonmateriality evidence-state successor — 2026-09-05

Status: synthetic decision semantics implemented and independently replayed.
This is not a new human-calibration rule, a validated uncertainty model, or an
oracle result. All predecessor plans, implementations and evidence are unchanged.

## The reproducible problem

The frozen listening classifier turns the absence of a material severity signal
into `audible_nonmaterial` when its audibility rule passes, or `transparent`
when its chance-equivalence rule passes. It does not require affirmative
severity evidence on the nonmaterial side of the boundary.

The [new replay](../../scripts/perceptual_degradation_nonmateriality.py) generates
the original synthetic listening fixture, retains its two subtle-only groups,
sets every synthetic SDG to -1, validates the resulting envelope, and runs the
unchanged primary classifier. Both fitted severity intervals are approximately
[-1.0736552735, -0.9263447265]. They cross the old -1 boundary. The old classifier
nevertheless emits `audible_nonmaterial` for one and `transparent` for the other.
The successor emits `indeterminate` with null material-condition labels for both.
This counterfactual does not edit or reclassify any retained result.

The legacy SDG fits remain explicitly named `legacy_sdg_diagnostic`; they are
not migrated into paired-rating observations. The numerical boundary is used
to expose the original decision logic, not to approve that boundary for a new
paired target.

## Separate evidence axes

The general methodological distinction is established: an unsuccessful
difference test does not establish practical equivalence, and meaningful
bounds need justification before outcome interpretation. See
[Lakens (2017)](https://pure.tue.nl/ws/portalfiles/portal/80918653/lakeequi2017.pdf).
That source does not validate LossyTrace's margins or crossed-effects intervals.

The successor tests this proposed decision structure:

| Evidence | Synthetic handling |
| --- | --- |
| Supported severity interval wholly in the impaired direction beyond the boundary | Material support |
| Supported severity interval wholly on the nonmaterial side | Nonmaterial support |
| Interval crosses or touches the boundary | Indeterminate |
| Missing estimate, inadequate support or nonconvergence | Indeterminate with its specific reason |
| Both required bridge methods support the same direction | Combined directional support |
| One bridge method supports materiality and the other nonmateriality | Explicit method conflict |
| One required bridge method is missing or unresolved | Indeterminate, not automatically a method conflict |

For paired grades, D = condition minus hidden-reference grade: more negative D
means more impairment. Interval endpoints reverse when expressing impairment
as -D. Positive differences are retained. Intervals are not clipped to response
limits and decisions use unrounded values. A 1e-9 tolerance accommodates only
floating-point model-mean roundoff at the response endpoints; it does not alter
materiality or equivalence comparisons.

Detectability remains a separate axis. Nonmaterial severity alone cannot produce
`transparent`; the diagnostic chance-equivalence rule must also pass. Similarly,
an audible result alone cannot produce a nonmaterial label. Conflicting evidence
or an unresolved required axis leaves the combined summary indeterminate.
Declared bridge methods cannot disappear simply because their estimate is absent.

## Paired integration and observed software limitations

The five unchanged paired-protocol scenarios now run through the bound Gaussian
and logistic solvers and into this adapter. A sixth declared synthetic case
ends half the pairs incomplete: its severity fit has only 12 listeners and is
marked insufficient, while all 288 locked choices remain visible to a separate
numerical probability preview. This is not a selected real-study missingness
policy; conditional selection of complete responses still needs investigation.

The all-incorrect `positive-difference` fixture causes the frozen logistic
solver to raise its nonconvergence error. That failure is retained explicitly,
without replacing its data or substituting a probability. Its signed severity
estimate remains +4, but its combined summary is indeterminate. Other numerical
errors are not swallowed. This is a limitation to address in a solver successor,
not evidence about how real listeners behave.

Code inspection explains this boundary case. The
[original solver](../../scripts/perceptual_degradation_listening_analysis.py)
penalizes listener and source effects but not the global intercept. With all
answers incorrect, decreasing that intercept keeps improving the Bernoulli
likelihood; no finite maximizer exists. Numerical probability clamping does not
create a finite optimum for that model. Merely raising the iteration limit is
therefore not a remedy. A future estimator needs an explicit boundary or
regularization strategy and an uncertainty/estimand audit, not a hidden fallback.

A 48-case synthetic bridge grid covers all three detectability states and four
states for each severity method. Only the three fully supported combinations
receive determinate summaries; six cases have explicit method conflicts.
These are software truth-table counts, not error rates or statistical power.
Two independent CLI runs produced byte-identical
[aggregate evidence](../../research/toolchains/evidence/perceptual-degradation-nonmateriality-synthetic-20260905-001.json).

## Scientific and execution boundaries

The -1 SDG, 10-point MUSHRA, audibility and support numbers are legacy diagnostic
coordinates only. They are not selected paired scientific thresholds. Model
variance components remain fixed numerical assumptions; their interval coverage
is unvalidated for the paired target. No nominal confidence guarantee, new
noninferiority margin, equivalence power, multiplicity rule or population-marginal
estimate is established here. Aggregate estimates cannot become per-source labels.

The adapter accepts only explicitly synthetic, aggregate model envelopes. Those
flags describe scope, not authentication or proof of provenance. Its CLI generates
fixtures internally and accepts no observed-input path, output path or live
response stream. No audio, codec output, metric score, listener response, sealed
label or source identity is accessed. The public CLI remains verdict-free.

Before scientific use, a separately frozen successor must justify the paired
materiality margin and target population, validate interval coverage and solver
behavior under crossed listener/source variation and missingness, establish
power and multiplicity control, and integrate qualified study delivery. This
work selects none of those answers. Source qualification, human calibration,
full-reference validation and every no-reference transfer gate remain open.

Reproduction:

```sh
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_nonmateriality.py'
python3 scripts/perceptual_degradation_nonmateriality.py --synthetic
```

The [plan](../../benchmarks/perceptual-degradation-v1/nonmateriality-evidence-plan.json)
binds predecessor hashes and closes all non-synthetic execution. The
[tests](../../scripts/tests/test_perceptual_degradation_nonmateriality.py) exercise
interval direction and endpoints, nulls, required methods, malformed values,
model failure, scope and authority tampering, exact replays and the old classifier.
