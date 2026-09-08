# Bounded native digital canary: partial completion, failed repeatability

Date: 2026-09-08. This is a technical negative, not a finding about perceived
sound quality or a final disposition of the research objective.

The [approved canary](perceptual-degradation-digital-canary-proposal-20260908.md)
ran once on its one metadata-selected full-length reference. Both prescribed
replay reports were retained. The [aggregate evidence](../../research/toolchains/evidence/perceptual-degradation-digital-canary-20260908-001.json)
records all 12 planned comparisons, with no substitution or additional run.

| Outcome | Replay 1 | Replay 2 |
| --- | ---: | ---: |
| Planned and attempted comparisons | 6 | 6 |
| Alignment timeouts | 6 | 2 |
| Completed comparisons | 0 | 4 |
| Completed control comparisons | 0 | 1 |
| Completed codec comparisons | 0 | 3 |
| Codec encode/decode pairs reaching alignment | 4 | 4 |
| Cases not started | 0 | 0 |

The invocation took 2,069.7 seconds, about 34.5 minutes, including its runner
preflight and report overhead. Completed cases took 146.1–167.9 seconds. The
eight failures expired during alignment under the unchanged 180-second case
budget; small teardown overhead is included in recorded case times.

## What passed, and what did not

All four codec conditions have matching recorded encoded and decoded SHA-256
values and packet records across replays. Corresponding source and input-adapter
hashes also match. That establishes limited codec-stage integrity on this one
development reference, not reliable end-to-end completion or perceptual quality.

The computational-completion gate failed. The preregistered repeatability check
also failed, even after excluding exactly the permitted per-case timing field:
case dispositions, available comparisons and partial native progress differ.
No condition completed alignment in both replays, so there is no paired completed
alignment with which to evaluate numerical repeatability. Do not relabel this
as demonstrated numerical nondeterminism or erase timeout diagnostics to create
a repeatability pass.

All four completed comparisons passed the unchanged technical alignment and
duration requirements. This is not a perceptual metric pass. The failed cases
have no completed alignment from which support can be recovered. Empty
unsupported-reason maps therefore do not mean all 12 comparisons were supported.

No native fallback candidate was recorded. The projection's
`no_native_fallback_all_cases` flag is nevertheless false because that conjunction
also requires every case to complete. It must not be read as evidence that a
fallback occurred. Likewise, process exit zero means the bounded reports were
written, not that the canary passed.

Severity, audibility, artifact profile and transparency remain null. The result
does not justify training, source-trait assignment, human calibration, independent
validation, a public verdict or rejection of perceptual estimation.

## Runtime qualification needs more than frame count

The earlier approximately 118-second full-size synthetic identity was a useful
construction-specific result. It did not establish enough runtime margin for
this real-source canary. Matching duration and channel geometry was insufficient
to predict completion under the same budget.

Static inspection shows that the [global refinement search](../../scripts/perceptual_degradation_alignment_v4.py)
still evaluates correlations in Python over a candidate inventory derived from
the envelope peaks. The native backend accelerates local drift/structural
searches, not every search stage. Candidate distribution is therefore a plausible
workload dimension for a future qualification. Neither the new dominant hotspot
nor the cause of the difference between replay runtimes was profiled here.
Timing alone cannot distinguish source-dependent work from host scheduling or
other runtime variation.

Next, preregister a score-free successor that varies search workload as well as
frame count and establishes runtime margin. A separate controlled-digital
alignment design is also worth assessing: these are known paired digital
interventions, not arbitrary recordings from independent clocks. Such a design
would need prospective justification and structural-negative tests; it is not
permission to force alignment, fit away artifacts, narrow this consumed search,
raise its deadline or rerun this reference under changed rules.

## Integrity and retained evidence

Execution used commit `48b1264bdf15f5c5667e2ae8423f35ccc0696d7f`, after its
[exact-head push CI](https://github.com/ryan-voitiskis/lossytrace/actions/runs/34185934712)
passed: 1,599 Python tests with 14 skips, plus Rust checks. The execution head is
distinct from the later report-publication head.

The [independent saved-artifact auditor](../../scripts/perceptual_degradation_digital_canary_artifact_audit.py)
and its [nine constructed filesystem tests](../../scripts/tests/test_perceptual_degradation_digital_canary_artifact_audit.py)
are byte-identical to private copies prepared and tested before observation.
The auditor independently reconstructed the aggregate, then cross-checked the
frozen summarizer. It verified identity/order and denominators, completed-case
native inventory consistency, exact projection bytes, selected-source preservation,
and the private retention boundary. A separate readback confirmed the first
report remained unchanged and stdout matched the saved projection. This audit does
not rerun alignment or independently validate perceptual performance.

Only the selected waveform was reopened by this successor and its post-run
audit. The other 15 waveforms were not reopened or claimed to have passed fresh
waveform-integrity checks. The 16-member metadata inventory and attribution were
verified. The private run retains exactly five JSON files and the bound native
library; no case scratch, encoded condition, input adapter or decoded PCM remains.
Only runner-owned temporary files were removed. The original reference and all
saved reports remain retained privately.

Native/source/resource checks passed at all four replay edges. These are edge
checks, not continuous attestation. No new compiler-dependency-closure or
cross-directory binary-reproducibility claim is made. Private paths, member IDs,
per-reference hashes, packet records and audio are not published in this result.

The one-shot authorization is consumed. Original proposals, implementations,
thresholds and earlier negative results are unchanged. No further real replay,
metric, playback, capture, listener response, training, outreach or spending is
authorized by this result. The public CLI stays verdict-free, and the overall
research objective remains incomplete.
