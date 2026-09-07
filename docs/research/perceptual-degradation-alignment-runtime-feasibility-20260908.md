# Full-rate synthetic alignment: structural search is the measured bottleneck

Date: 2026-09-08. Technical development only; no real audio or perceptual score.

The unchanged aligner could not complete a constructed stereo identity within
180 seconds at the maximum planned geometry: 576,008 frames at 48 kHz. Both
uninstrumented rounds timed out. Stage-timed rounds localized about 83% of
observed alignment time to structural-window correlations, with the deadline
interrupting that work before even the first channel completed.

The [fixed protocol](../../benchmarks/perceptual-degradation-v1/alignment-runtime-feasibility-plan-20260908.json)
was committed locally as `d6b58b55ec055b35bbf11f5bf27aed1d1b3e8ee9` before
full-size alignment observation. Its tested instrumentation and source bindings
were unchanged during execution. The protocol and [result](../../research/toolchains/evidence/perceptual-degradation-alignment-runtime-synthetic-20260908-001.json)
are published together afterward. This is not a claim of prior external
preregistration or independent scientific validation.

## Observations

| Declared case | Round 1 | Round 2 |
| --- | ---: | ---: |
| Uninstrumented identity | timeout at 180.004 s | timeout at 180.011 s |
| Stage-timed identity | timeout at 180.005 s | timeout at 180.005 s |
| Structural-correlation time within timed identity | 150.742 s (83.7%) | 148.772 s (82.6%) |
| Sample-search correlation time within timed identity | 22.807 s | 25.145 s |
| Constant-envelope abstention | 1.052 s | 1.112 s |
| Topology rejection | 0.000092 s | 0.000116 s |

All eight planned slots are present. Four identities timed out with no completed
alignment record; four invalid-support controls completed and rejected as
declared. Constant envelopes retain undefined Pearson evidence and null common
summaries. Stereo-versus-mono topology rejects before channel analysis. The
controls' numerical alignment records are byte-identical across rounds.

Both timed identities interrupted the same stack: alignment, first channel,
structural audit, correlation. They completed 23,234 and 24,402 structural
correlations respectively before interruption. The partial counts and wall times
are observations, not deterministic numerical outputs. Whole round reports
differ, as expected; the protocol does not hide timing variation to manufacture
byte identity.

## Interpretation and limits

This turns the earlier static cost hypothesis into measured localization on one
declared full-size synthetic construction. It does not profile the earlier
private real-audio failures retroactively. The structural stage dominated the
work observed before censoring; the complete runtime, full-run stage shares
and second-channel timings remain unknown. No extrapolated completion time is
reported.

The 180-second clock measures alignment alone. Construction, import, process
startup and serialization are outside it; a separate 210-second worker timeout
bounds the whole child process. Even a pass here would be insufficient to qualify
the codec pipeline that shares its case budget with other operations.

Reversible wrappers delegate every original operation and search candidate.
Small-input tests establish byte-identical wrapped/unwrapped alignment records,
including invalid-correlation and signed-polarity behavior. Both full-size modes
timed out, so their complete numerical equivalence and instrumentation overhead
cannot be measured here. The uninstrumented failures establish that timing
instrumentation alone did not create the feasibility failure.

One artificial active family at one maximum-size geometry does not establish
natural-source coverage or prove that all shorter inputs fail. Fast rejection
controls test abstention paths; they do not qualify successful active alignment.
No alignment timeout is a severity label or evidence against perceptual estimation.

## Integrity and retained boundaries

A separate read-only audit checked all eight slots, native geometry, null
timeout outputs, expected guard reasons, stage count/time consistency,
completed-record byte equality and unchanged plan/predecessor hashes. It did
not invoke the runner's aggregate function or run another measurement.

The run retained exactly four no-clobber JSON files in its fresh output directory,
with 0600 file and 0700 directory modes. No waveform files were read or written.
The existing native runtime closure matched at the declared edge checks; no codec
encode/decode call was made. System-cache dependencies remain OS-build-bound,
not individually file-hashed. The work used one worker and preserved the 15 GiB
disk reserve.

The real-audio replay result, original alignment code, thresholds and prior
negative evidence are unchanged. No source trait, playback, metric, human
calibration, training, independent-validation or public-verdict gate opens.
The overall research objective remains incomplete.

## Next step

Optimize repeated structural-window correlations in a separately versioned
implementation. Preserve complete lag coverage, invalid-value semantics,
signed polarity, peak tie-breaking and support thresholds. Demonstrate
equivalence on declared small and full-size synthetic constructions before
proposing any new real-audio execution. Do not raise deadlines or narrow searches
to relabel this consumed checkpoint as a pass.
