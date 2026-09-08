# V5 digital canary: repeatable technical pass

Date: 2026-09-08. **All twelve comparisons passed the bounded primary technical
gate.** This is not a finding about perceived quality or completion of the
research objective.

The [frozen v5 canary](perceptual-degradation-digital-v5-canary-proposal-20260908.md)
ran once on the same metadata-selected largest development reference. The
[complete aggregate evidence](../../research/toolchains/evidence/perceptual-degradation-digital-v5-canary-20260908-001.json)
preserves all planned cases and distinguishes this result from the earlier
v4 negative.

| Outcome | Replay 1 | Replay 2 |
| --- | ---: | ---: |
| Planned/completed comparisons | 6 / 6 | 6 / 6 |
| Supported controls | 2 | 2 |
| Supported codec comparisons | 4 | 4 |
| Timeouts or unstarted cases | 0 | 0 |
| Local/global fallback candidates | 0 / 0 | 0 / 0 |
| Combined case wall time | 472.069 s | 469.355 s |

Individual cases took **77.3–79.7 seconds** under the unchanged 180-second case
limit. The combined case time was 941.423 seconds (15.7 minutes); this excludes
preflight and report overhead and is not the whole invocation's wall time.

## What passed

Both complete private replay records matched byte-for-byte after excluding
exactly each case's declared timing object. Alignment results, input/codec
hashes, packet records and local/global native inventories all remain in that
comparison. All six condition pairs completed in both rounds. Four codec pairs
also have matching encoded/decoded hashes and packet records.

Both controls and all eight codec comparisons were technically supported and
duration-eligible. All four replay-edge checks passed. Across both rounds,
1,627,488 local and 92,352 global native candidates were recorded, with no
fallback or short global overlap. These are computational work counts, not
independent statistical observations.

The frozen independent auditor reconstructed the aggregate and verified
identity/order, completed candidate accounting, the exclusive launch marker,
selected-source preservation and exact retention. Separate readback confirmed
the first report's earlier snapshot, stdout/projection equality, empty stderr
and private file modes. Only the selected waveform was reopened; the other
15 were checked through the bound metadata inventory, not reread as waveforms.
The run retains five JSON files and the native library, with no derived audio
or case scratch. Original reference bytes are unchanged.

Execution used `524cd679569ec8306d9025bb77c69b610b06de75` after
[exact-head CI](https://github.com/ryan-voitiskis/lossytrace/actions/runs/34201628376)
passed: 1,697 Python tests with 14 skips, plus Rust checks. The runner and
independent auditor were committed before observation; their 49 constructed
tests and nine standalone accounting checks passed before this batch.

## What this does not establish

This is one consumed development reference, not fresh grouped validation.
Technical support and duration eligibility are not perceptual metrics.
Severity, audibility, artifact profile and transparency remain null; no
listener responses or perceptual scores were collected. The public CLI remains
verdict-free.

The earlier v4 canary's eight timeouts remain a valid frozen negative. V5
preserves its search/numerical model and thresholds through the separately
qualified implementation change. The nonrandomized historical timings do not
isolate implementation effects from host/runtime variation, and neither the
synthetic qualification nor this canary proves equivalence on every input or
platform.

A single-case runtime pass does not make the old full-cohort budget feasible.
At this observed mean, a hypothetical 320 equally costly comparisons would
take about seven hours before overhead; other references may cost differently.
That is conditional planning arithmetic, not measured cohort throughput.
Do not restart the consumed full-cohort runner or enlarge this batch's limits.

## Next decision

The immediate engineering blocker is cleared for this bounded canary. Further
technical coverage can use the standing authority, but needs a separately
frozen scope and a budget informed by observed workload. Preserve the complete
development history and do not count repeated use as independent evidence.

The scientific priority remains a small, interpretable perceptual-development
study: matching targets to human judgments and testing within-source impairment
ordering and false material alerts. Metric selection/execution and human
collection still require their separate gates. No capture, playback, training,
source-trait promotion, outreach/spending, merge/release or public verdict is
authorized by this result. The broader objective remains incomplete.
