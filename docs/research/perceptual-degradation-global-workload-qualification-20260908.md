# Native global search and workload qualification — 2026-09-08

State: protocol prepared before full-size synthetic observation. No further
retained reference or codec has been accessed under this successor.

The [standing development authority](perceptual-degradation-standing-development-authority-20260908.md)
permits further bounded technical attempts without another permission question
for each shot. The [frozen workload plan](../../benchmarks/perceptual-degradation-v1/alignment-global-workload-plan-20260908.json)
first tests an implementation-preserving optimization. Earlier canary results,
their consumed authorizations, implementations and limits remain unchanged.

## The change being tested

V4 moved local-window correlations into native code but retained Python global
refinement. V5 adds an opt-in native global search. It evaluates every original
lag and sampled value, using the same normalization, accurate-sum algorithm,
signed correlation, invalidity rules and tie selection. Scientific thresholds,
gain/delay/drift policy, duration requirements and input samples are unchanged.

The new C file includes the unchanged PSF-licensed local/summation kernel and
adds normalization of both global vectors plus independent dot/energy sums.
The bridge packs at most 1,048,576 frames per input. Ineligible type/size or
arithmetic capacity/environment failures use original Python semantics. There
is no FFT, approximate pruning, changed decimation or automatic native build.

Exact candidate tests cover random vectors, extreme scales and cancellation,
zero/constant/polarity cases, numeric-invalid precedence, unsampled invalid
values, floor-stride boundaries, clipped/empty overlap, exotic-type fallback,
ties/threshold neighbors and unchanged inputs. Complete small alignments match
v4 after removing only the record-kind tag. AST checks constrain the alignment
change to the global dispatch; local searches inherit the original bridge.
Finite tests are not an all-input or all-platform proof.

## Fixed experiment

Each family has a Python-versus-native global component comparison and a full
native stereo identity. Run the eight listed slots twice, in fixed order,
with a fresh isolated child per slot and one worker: 16 slots total.

| Synthetic family | Workload purpose |
| --- | --- |
| Prior quantized LCG | Continuity with the earlier construction |
| Dense floating-point LCG | Different mantissa distribution |
| Per-sample mixed scales | Broader exponent and partial-sum work |
| Sparse bursts | Explicit zero-energy and activity-support paths |

Every construction has 576,008 frames per channel at 48 kHz. The component
comparison uses the left channel, the unchanged 801 coarse lags and all fine
candidates chosen from eight separated peaks. Eight valid peaks imply 3,848
fine candidates; peak position and overlap still matter. This experiment does
not claim candidate count alone explains the earlier runtime failure. Accurate
summation also has data-dependent internal work, which is not separately
instrumented by this protocol.

The primary qualification requires all slots to complete, exact global
candidate equality, complete evidence repeatability, unchanged inputs, zero
fallback and all four replay-edge checks. Every full native observation must
finish within **120 seconds**, under the unchanged **180-second deadline**.
The 120-second margin was selected prospectively, not after seeing these
workloads. Sparse-burst alignment may abstain on activity/window support;
computational completion does not imply perceptual support.

CPU and wall time are recorded separately. Delegating wrappers time global
and local native searches; remaining time covers the other alignment work.
Construction, initial hashing and library loading are outside the alignment
clock, while a separate 210-second bound covers each whole child. Component
comparisons always run Python before native, so timing ratios do not isolate
order, caching or scheduling. Record conversion is outside both component
stage timers. No codec-overhead or real-source throughput guarantee follows.

Timeouts, partial progress, failures and unstarted cases remain in the full
denominator. Completed evidence excludes exactly six declared timing fields
for replay comparison; numerical records, input hashes and counters remain.
No paired-completion claim is made for a case that times out. A resource/edge
stop persists into the second round. No automatic retry, new signal, narrowed
search or deadline change occurs within this batch.

## Execution and evidence boundaries

Commit the tested protocol locally before full-size observation, from a clean
external working checkout. This is local preregistration, not a claim of prior
external publication. The public-only protocol commit may be transferred to
the external checkout without copying unrelated/private local Git history.
Before publishing protocol/result commits, run the full local CI-equivalent
suite, staged/privacy audit and deterministic SBOM, then verify exact-head CI.

Check the 15 GiB workspace and output-volume reserve before launch, each case
and each replay edge. Use a fresh outside-repository output directory and an
exclusive launch marker. Retain four private JSON reports plus the hash-bound
native library; no constructed arrays or waveform files are retained. Bind
global/included C sources, bridges, compiler/version/flags, OS/architecture and
binary. Compiler dependency closure and cross-directory binary reproducibility
are not claimed. Codec tools are checked only through installed metadata.

An independent readback must reconstruct the result before publication. If
qualification passes, freeze a separate bounded v5 real-reference/codec canary
under the standing authority and wait for exact-execution-head CI before access.
If it fails, preserve the negative and use it to design a new prospective
development batch. This protocol itself authorizes no real audio, codec,
playback, capture, metric, listener response, source assignment, training or
public verdict. The research objective remains incomplete.
