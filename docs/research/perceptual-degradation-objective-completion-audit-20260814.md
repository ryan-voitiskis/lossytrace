# Perceptual-degradation objective completion audit - 2026-08-14

**Status:** the full objective is incomplete. This score-blind audit adds no
source-member selection, audio access, metric authority, score access,
recruitment, collection, no-reference training, final recommendation, or
public verdict.

## Outcome

Four of fourteen objective requirements are currently supported by direct
bound evidence:

1. the estimand is controlled perceptual degradation rather than codec-history
   inference;
2. the declared RME ADI-2 Pro FS / Adam T7V 48 kHz playback chain passed its
   qualification prerequisite;
3. the public CLI remains feature-version-zero experimental measurement with
   verdicts disabled; and
4. the contract accepts a rigorous negative result as successful completion.

Ten requirements remain incomplete or unevaluated. Green tests and synthetic
replays do not reduce that count because they do not provide listening truth.

## Requirement audit

| Requirement | Current evidence state |
| --- | --- |
| Degradation-not-history estimand | satisfied contract boundary |
| Declared playback chain | satisfied prerequisite |
| Truth-bearing source manifest | incomplete |
| Controlled human calibration | not authorized or collected |
| Perceptual metrics and proxy legal gate | blocked by legal and execution gate |
| Human-calibrated full-reference oracle | synthetic plumbing only |
| Transparent lossy treated as non-degraded | policy frozen; truth absent |
| Difficult natural and production negatives | specified; not scientifically evaluated |
| Source/domain/codec/encoder grouped transfer | not evaluated |
| No-reference estimator | not started by design |
| Severity/audibility/artifact/support/uncertainty outputs | schema ready; values unavailable |
| Public CLI verdict-free | satisfied current boundary |
| Rigorous negative accepted | satisfied success criterion |
| Final research recommendation | absent |

The score-free oracle envelope and 10,000-replicate grouped evaluation code are
replayable. Their own claim boundaries correctly say that the full-reference
scientific gate has not been evaluated and no-reference work is ineligible.
The output schema can abstain and represent severity, audibility, artifact
profile, support, and uncertainty, but current records contain no perceptual
values.

## Blocking sequence

The evidence dependencies remain ordered:

1. freeze a feasible truth-bearing source/provider/domain manifest;
2. complete the remaining stimulus, privacy, power, allocation, and authority
   gates and collect controlled human calibration;
3. resolve the GstPEAQ proxy legal/conformance boundary and execute the frozen
   primary metric families if permitted;
4. pass the deterministic human-calibrated full-reference gates;
5. pass fresh grouped source-, domain-, codec-, and encoder-transfer gates;
6. only then freeze, train, and independently validate a no-reference
   estimator; and
7. freeze exactly one final recommendation.

The nearest authority-dependent decision remains unchanged: qualify additional
permissive providers or explicitly narrow the primary-domain claim. Exact
member selection and audio acquisition are premature under either path.

## Negative-result boundary

No final recommendation is yet justified. The frozen terminal choices remain:

- `reject_perceptual_estimation`;
- `retain_full_reference_only`;
- `continue_no_reference_research`; or
- `freeze_blind_final_validation`.

The first two are valid successful outcomes if the evidence rejects the
broader estimator. Neither green plumbing nor current infeasibility alone is a
final negative result because the human-calibration experiment has not been
run on an adequate source population.

## Determinism and bindings

Two fresh audits were byte-identical at SHA-256
`b678fd9be29317e265882a27a1b8b25077acd902b4e7ccb03256265b9047beba`.
The report binds plan SHA-256
`b4943e7d5404f61797c664999d5e9e2da408acd2751cc2505eaa3fecfa08f43d`
and implementation SHA-256
`4094321065c464028352fd75b462a909b00fbbae730152875a33026f61d5032f`.

Machine-readable artifacts:

- [`audit plan`](../../benchmarks/perceptual-degradation-v1/objective-completion-audit-plan.json)
- [`audit report`](../../research/toolchains/evidence/perceptual-degradation-objective-completion-audit-20260814-001.json)
- [`audit implementation`](../../scripts/perceptual_degradation_objective_completion_audit.py)
