# Source-condition linkage and evidence units — 2026-09-05

Status: synthetic-only linkage implemented and replayed twice with identical
bytes. It connects the existing paired assignment/response reducer to stable
comparison cases and checks the consumer boundary. It does not replace the
legacy full-reference evaluator, estimate a population target, select an
inferential method, or open a scientific execution gate.

## Why this successor is needed

The [target-semantics successor](perceptual-degradation-target-semantics-integration-20260905.md)
already prohibits broadcasting aggregate treatment results to individual
sources. That prohibition remains correct; this checkpoint does not claim to
have discovered or repaired an observed instance of that broadcast. There is
no live human-to-oracle adapter yet.

Inspection of the paired fixture exposed another necessary distinction. Its
concealed candidate IDs are generated using the scenario, listener and source,
so the same declared source/condition comparison receives different aliases in
different listener presentations. That is useful presentation isolation, not a
stable identity suitable for source-condition calibration. It is not a defect
in the existing synthetic player.

The [independence audit](perceptual-degradation-independent-groups-20260905.md)
also shows why source and leakage-group counts must not be treated as evidence
of independent sampling. This successor connects these boundaries to an actual
synthetic response flow rather than attaching another confidence interval to
the same undeclared population.

| Unit | What the new fixture records | What it does not establish |
| --- | --- | --- |
| Presentation | Assigned listener trial and concealed candidate aliases | A new source or stable comparison |
| Reference/condition case | Stable pair shared across assigned listeners | A population-valid perceptual label |
| Source group | Related synthetic comparisons across scenarios | Independent source sampling |
| Leakage group | Two synthetic source groups kept together | A sampling frame, independence or population weight |
| Population | Unspecified; inference outputs remain null | Generalization from these counts alone |

## Implemented boundary

The registry is generated before responses are resolved. Its explicit lookup
joins each assignment to a stable case, reference, condition, source, analysis
group and leakage group. The adapter never parses an opaque presentation ID
to infer its identity. These relationships are declared fixture facts, not
verified audio identity or permission to assign real sources to groups.

The bound paired reducer still verifies each response's assignment, trial,
presentation and concealed role mapping. Wrong or duplicate responses and
altered registry relationships are rejected. The complete planned registry is
retained even when an entire case has no responses.

Each case summary keeps three distinct quantities:

- The observed paired mean over completed assigned listener pairs, using the
  signed condition-minus-hidden-reference tick difference. Positive values and
  incorrect choices remain included.
- The correct-choice fraction over all locked choices, including trials whose
  paired ratings are incomplete. Its denominator is separate from the number
  of complete pairs.
- The corresponding finite planned-panel mean or fraction, which remains null
  whenever its assigned measurements are missing. Missing values are not zeros.

These are exact finite-fixture summaries, serialized as reduced rational
strings. No probability model, confidence interval, materiality boundary,
equivalence decision or statistical support cutoff is applied. Even complete
panels leave population probabilities, population severity, uncertainty,
material/audible labels and independent-unit counts null.

The consumer preflight routes only these finite case summaries. It checks
identity, count consistency, exact bounded tick support, missingness and the
absence of scientific labels. All four aggregate targets from the bound
target-semantics report are rejected. Requests for scientific source labels,
population generalization or legacy full-reference evaluation are also rejected.
This is a narrow synthetic integration check, not a generic observed-data
validator or an authorization mechanism. A flag or opaque ID cannot establish
real provenance or independence.

## Observed synthetic results

Across the five unchanged paired scenarios, 24 synthetic listeners each judge
12 source cases: 1,440 complete presentations, 60 stable comparison cases,
12 source groups and six declared leakage groups. Within each scenario there
are 288 condition aliases and 288 hidden-reference aliases, but only 12 stable
conditions and 12 stable references. The same source and listener identities
are reused across scenarios; scenarios are not actual codec conditions.

All five complete fixtures retain the original paired arithmetic. Their case
means are respectively 0, 0, −0.5, −1 and +4. The +4 fixture retains every
incorrect choice and is not clipped to zero.

Three declared missingness variants use the choice-correlated fixture:

| Variant | Result per affected case |
| --- | --- |
| Incorrect-choice trials retain choice but omit both grades/submission | 24 locked choices, 12 completed pairs; observed paired mean −2, planned paired mean null; correct-choice fraction remains 1/2 |
| One entire case has no responses | All 12 planned cases remain; the absent case has 24 missing choices/pairs and null means, while 11 complete cases retain −1/2 |
| All responses absent | All 12 planned cases remain with null means and fractions, not negative labels or a zero-valued outcome |

The change from −0.5 in the complete panel to −2 among the remaining completed
pairs is a consequence of this explicitly outcome-dependent synthetic omission.
It is not an observed human bias, a correction method or an admissible
complete-case estimate of the original full panel. This checkpoint exposes the
missing target; the earlier bounded-missingness audit is not silently selected
or transplanted into this adapter.

Two full final CLI replays are byte-identical. During implementation review,
consumer-side count, rational-value and null-label validation was strengthened;
every reported scientific/synthetic value stayed identical, apart from the
implementation hash. The first focused test invocation preceded creation of
the golden report and failed only because that file was absent; the complete
focused suite passed after the two verified replays supplied it.

## Implication for the research direction

There are two different design tasks ahead, not one interchangeable analysis:

1. A source-conditional listener target holds the exact reference/condition
   comparison fixed and specifies which listeners, playback setting and
   averaging rule it concerns. Repeated judgments supply listener evidence for
   that comparison; they do not create more source diversity. The old aggregate
   support requirement of 12 sources cannot simply be applied to a one-source
   case, nor can its interval be copied to every case.
2. Population-level validation specifies which new sources and listeners are
   represented, how they are selected, which observations share dependence,
   and which weights define the reported quantity. Leakage isolation is
   necessary for the existing transfer design but is not a sampling argument.

The next statistical amendment must resolve both explicitly, including
missingness, appropriate response-level scoring, target uncertainty and
prospective acceptance criteria. This adapter deliberately does not select
those choices by encoding them as unexplained defaults.

No retained audio, capture, listener collection, metric execution, sealed
evidence or training was accessed. The authorized clean capture still needs
the physical setup declaration and execution checkpoint. Source qualification,
human calibration, a full-reference pass and independent no-reference
validation remain outstanding. The original objective is active and incomplete.

## Reproduction and artifacts

```sh
python3 scripts/perceptual_degradation_case_linkage.py --synthetic
python3 -m unittest discover -s scripts/tests -p 'test_perceptual_degradation_case_linkage.py'
```

The CLI accepts no observed-input or tuning option. The public report contains
only scenario/variant counts and histograms, never participant, assignment,
stimulus, source or case rows. Every predecessor remains unchanged.

- [Declared plan](../../benchmarks/perceptual-degradation-v1/case-linkage-plan.json)
- [Implementation](../../scripts/perceptual_degradation_case_linkage.py)
- [Tests](../../scripts/tests/test_perceptual_degradation_case_linkage.py)
- [Aggregate synthetic evidence](../../research/toolchains/evidence/perceptual-degradation-case-linkage-synthetic-20260905-001.json)
