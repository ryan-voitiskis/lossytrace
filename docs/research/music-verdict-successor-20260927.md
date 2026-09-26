# Finished-music verdict study: successor design

Date: 2026-09-27. Study ID: `music-verdict-v1`.

Status: prospective design freeze and source-feasibility work. **Not an execution
authorization record, a fitted detector, or a completed negative experiment.**
No new real-audio acquisition, training, calibration, or evaluation has run.
The specification is committed before source allocation or model execution
and byte-bound by `research/music-verdict-v1/design-freeze.json`. Exact data,
toolchain, recipes and executable bindings remain a
separate required execution freeze. An insufficient source pool is a feasibility
blocker, not evidence that the proposed CNN fails.

## Starting point and correction to the proposal

The starting release is `v0.1.0-rc.1` at
`4ca4384dfa897bf68f968deddb6a72e083f3ea90`. Its public output is measurements
only. Its draft PR remains unmerged. The new work is on a separate branch;
neither the release nor the historical experiments are revised.

The initial conversational proposal understated the work already done.
[The original research record](original-reklawdbox-plan.md) documents both
content-residual CNN inputs and within-source paired CRNN ranking. The latter
produced 86/404 detections with 48/250 negative alerts; adding disjoint sparse
training later produced 20/404 with 11/250 alerts. The wider domain-ablation
study also failed. Thus matched sources, residual features, GroupNorm, or a
smaller network are **not new discoveries**. Mere repetition is not justified.

The new hypothesis is narrower and explicitly unproven: **training the same
classifier on codec/negative pairs across matched, label-preserving processing
interventions, with a penalty on score changes under those interventions, may
permit useful selective classification of finished music.** This tests nuisance
consistency, not just within-source ranking. It does not assert a new physical
codec fingerprint or erase earlier failure on sparse and isolated sources.
The population change is declared before any successor scores, not selected
from the domains where Lossprint happened to perform well.

## Product question and supported population

The intended product is local review/triage of complete music mixes delivered
as PCM WAV or FLAC, mono or stereo, 44.1 or 48 kHz, 16- or 24-bit, at least
30 seconds. Include acoustic, electronic, vocal, instrumental, quiet/sparse
passages, intentionally band-limited production, and mastered and unmastered
mixes. A quiet passage within a song must not cause the song to be removed
from the evaluation. Exclude isolated-note datasets, speech-only collections,
multichannel audio, other rates and shorter clips from the claimed population,
but describe this scope honestly. Genre/content membership is user-declared;
the system cannot silently certify that arbitrary input is in-distribution.

The positive target is a complete mix passed through one of the specified
lossy codec settings and decoded to PCM, including specified subsequent
processing. Partial-track encodes, lossy samples inside an otherwise clean
mix, analogue recapture and unknown multi-generation chains are outside this
first validation claim, not certified negatives. A universal claim that audio
has *ever* passed through any lossy codec is not the estimand.

Proposed outputs are `likely_lossy_derived`, `no_evidence_detected`, and
`inconclusive`, with a separate `unsupported` reason. The second outcome never
means never-lossy. No automatic deletion, retagging, family or bitrate claim.
Expose raw score as a score; any probability is explicitly conditional on the
declared validation population and prior, not a universal provenance certainty.

## Source gate before expensive model work

1. Obtain public metadata or user-authorized retained metadata, not waveforms,
   first. Never inspect another project's files or historical sealed audio.
2. A negative needs a documented recording/render-to-distribution chain with
   PCM/lossless stages and no unresolved codec stage. Original project exports
   with auditable inputs or documented direct PCM recordings can qualify.
   Neither a WAV suffix, commercial master label, spectrum, model score nor
   absence of a codec mention qualifies a source. Provider statements are
   evidence with limitations, not mathematical proof of all prior history.
3. Record recording artist/performer, session, work/remix lineage, upstream
   collection and processing chain. Build connected components of shared
   artist, session and source-work identities across datasets. Unknown session
   or lineage cannot be assumed independent. Keep provider/production-chain
   strata explicit, and reserve at least one entire provider/production chain
   for fresh evaluation.
4. Audit overlaps against consumed source identities without opening sealed
   scores or audio. Existing development can be reused only as labelled
   development if its provenance is independently sufficient; otherwise it is
   an unknown-history diagnostic, not a clean negative. A new dataset name is
   not evidence of new recordings.
5. Record source terms and separate permission for research, derivative audio,
   and distributing trained weights. Do not infer an audio license from a
   paper's license. Unresolved weight rights block release, not automatically
   all private research. No outreach, account creation, expenditure or legal
   workarounds under this study.
6. Target at least 100 training, 40 model-selection, 100 calibration and 300
   fresh evaluation components. All four splits are disjoint by the component
   rule. All evaluation components must be unconsumed; at least three
   production/provider strata and at least 30 evaluation components per stratum.
   These are minima, not a claim that this corpus is already available.
7. Before selection, fix deterministic identity-hash ordering and quotas in
   an allocation file. Select one representative complete mix per component
   for calibration/evaluation. Different encodes, windows, wrappers and mixes
   of that recording never increase the independent sample count. No spectral
   screening of putative clean masters.

The 300 evaluation minimum is tied to the proposed 1% group false-alert ceiling:
with zero alerts in 300 independent groups, the one-sided exact 95% binomial
upper bound is about 0.994%. With 45 groups it is about 6.44%, regardless of how
many encodes/windows are made. This bound still assumes suitable independent
sampling and does not establish representativeness of arbitrary music libraries.

## One candidate and one inexpensive comparator

Both consume audio only at inference; no filenames, provenance fields, tags,
encoder settings or reference counterpart are model features.

### Candidate: matched-intervention CNN

- Native-rate STFT, 2,048-sample Hann windows, hop 512, no resampling merely
  to satisfy the frontend. Four-second windows, up to 24 evenly spaced over
  the first 120 seconds; record every analysed interval. Incomplete windows
  are not padded into fake evidence. At least six windows are required.
- Mid/side log-magnitude inputs (side zero for mono), plus a constant sample
  rate channel. Normalize by joint window RMS with a fixed epsilon, not a
  corpus-fitted spectral cutoff. Exact constants belong to the execution freeze.
- Four convolution blocks, channel widths 16/32/64/96, two 3x3 convolutions
  per block, GroupNorm, GELU, 2x2 average pooling, global average pooling and
  a 64-unit hidden classifier with one logit. No recurrent or pretrained model.
  Parameter ceiling 300,000. Report actual count before training.
- A training item is a matched quartet: `x`, `C(x)`, `N(x)`, `N(C(x))`, where
  `C` is codec round trip and `N` is non-codec processing. Crops refer to the
  same source interval after deterministic delay accounting. Some `x` are
  themselves preprocessed PCM, to cover processing before as well as after
  encoding. Provenance and labels never change merely because processing
  removes detectable traces.
- Loss: class-balanced binary cross entropy on all four items plus 0.1 times
  the mean squared logit difference between `x`/`N(x)` and
  `C(x)`/`N(C(x))`. No paired-ranking term and no high-frequency mask.
- Single seed 20260927, AdamW, learning rate 0.001, weight decay 0.0001,
  effective batch 16 quartets, at most 20 epochs. Choose minimum source-balanced
  model-selection BCE, tie to earliest epoch. No hyperparameter/architecture
  sweep. One pre-score synthetic implementation repair is allowed with a new
  execution binding; scientific retries or another seed are not.

### Comparator: measurement logistic regression

Use only the current feature-v0 numerical measurements, with missing-value
indicators. Exclude hashes, format/codec debug strings, duration, paths and
source labels. Standardize and impute using training only. One L2-regularized
logistic model, fixed penalty 1.0 with a mean-BCE objective; intercept unpenalized.
Freeze the exact ordered feature list and solver before fitting. Use the same
source allocations, cases and file-level accounting as the CNN.

These are study specifications, not implemented/trained models. Do not silently
substitute a pretrained semantic audio model, Jev/Kev or an ensemble.

## Factorial cases and decision policy

Primary codec matrix: MP3 CBR 128/192/320 kbps and AAC-LC 128/192/256 kbps,
using one pinned encoder implementation per family. Decoder and encoder bytes,
delay handling, and actual generated bitrate measurements must be frozen.
This is not validation of all implementations or families. Additional codecs
require a successor, not a post-result expansion of the claimed scope.

For each source, include identity and these five non-codec conditions on both
negative and positive paths: -6 dB gain; 16-bit TPDF requantization; a
44.1/48-kHz round trip; 16-kHz low-pass; and a fixed EQ/dynamic-range-processing
chain. Negative controls traverse the same PCM read/write path. Retain encoder
delay/cropping/wrapper checks. No edge, silence-padding or format shortcut.
Six positive settings by six postprocessing conditions plus six negatives give
42 primary cases per source. Stronger 12-kHz low-pass and short/quiet/sparse
controls are a separately reported stress panel, not used for tuning or to
inflate primary counts. Exact filters, dithering seeds and processing order
must be executable and frozen before construction.

Aggregate CNN window logits by their arithmetic mean. Fit scalar temperature
on source/class-balanced calibration cases only. For each model choose the
high threshold immediately above the largest negative calibration score;
scores at/above it flag. Choose the low threshold immediately below the
smallest positive calibration score, capped below the high threshold; scores
at/below it mean no evidence detected. The interval between abstains. If a
threshold cannot be represented or the policy is degenerate, record failure,
not a relaxed threshold. Use unsaturated logits for threshold calculations.
Thresholds are selected once and frozen before fresh evaluation. Temperature
does not improve ranking or guarantee deployment calibration.

## Gates and reporting

Preselect the CNN as the candidate for promotion; the comparator is reported
but is not a fallback selected after viewing fresh results. If the comparator
is preferable, that is a finding for a later authorized decision, not permission
to choose the winner on the final set. No post-score changes to this contract.

All conditions below must hold for the candidate:

- One-sided exact 95% upper bound on **group-any-negative-alert probability**
  <= 1%. One alert on any of a group's six negatives counts as one group alert.
- For each codec setting, a group detection succeeds only if at least five of
  its six positive processing cases are flagged. Each setting must have a
  one-sided exact 95% lower bound >= 70% successful groups. Unsupported,
  inconclusive and missing outputs count as misses, never disappear.
- At least 70% of the negative cases receive `no_evidence_detected`, and at
  least 70% of positive cases receive `likely_lossy_derived`, using equal
  group weights. Report those separately; class prevalence cannot conceal
  an abstain-everything or no-evidence-everything policy.
- No eligible provider/production stratum with >=30 evaluation groups has
  >5% observed group-any-negative alerts or <50% detected positive cases.
  Small strata are reported, never silently discarded or relabelled safe.
- Group/class-balanced Brier score <=0.15 and 10 equal-width-bin calibration
  error <=0.10 under an explicitly artificial 50:50 class prior. Report bin
  counts, uncertainty, prior sensitivity and calibration limitations; these
  gates do not certify the probability of an individual file's whole history.
- End-to-end released-candidate path on the current machine: warmed median
  <=5 s, p95 <=10 s per 120 seconds inspected; cold startup <=15 s; peak RSS
  <=1 GiB. Use at least 30 complete five-minute music files, 3 warm repetitions,
  WAV/FLAC pairs, whole-file hashing included. No guessed GPU speed. Report
  storage/cache conditions and all unsupported inputs.
- Exact input preservation, deterministic replay within frozen numerical
  tolerances, equal-PCM wrapper agreement, no source-group leakage, no
  inference-time counterpart, reproducible model/artifact bindings and a
  separate saved-output audit all pass.

Publish group-weighted and case counts, confusion tables including abstention,
per-recipe and per-stratum results, source provenance limitations, calibration
curves, both model costs, and a comparison of their detection at their own
preselected operating points. Multiple encodes are not independent trials.
An upper confidence bound is not a guarantee under deployment distribution shift.

## Resource and stopping boundaries

Metadata discovery so far is preliminary, not a retrospectively preregistered
search. Continue with at most 12 additional targeted search queries and 20
additional primary provider records. Maintain a source ledger including
unavailable pages and unresolved terms; do not claim exhaustive absence.

Following source qualification and execution freeze only: maximum 100 GiB new
downloads and 200 GiB total new working data on the user-designated external
volume, 24 machine-hours total, a single training process, no paid compute,
and no playback/capture. Before starting, check headroom and preserve existing
data. A larger corpus/resource requirement needs a decision before access.

Stop scientific execution if provenance, independent count, license, grouping,
technical integrity or compute gates fail. Budget exhaustion is not a model
failure. Report the specific blocker and preserve partial engineering work.
Do not proceed with convenient but unknown-history negatives.

If fresh validation passes, implement the structured verdict/evidence contract,
test CLI behaviour and reproducibility and prepare a new RC. Publishing,
merging, outreach, spending and downstream integration remain unauthorized.
If the executed experiment fails, preserve its negative findings and keep the
current verdict-free inspector. Source infeasibility alone does not complete
the requested model comparison.

## Required execution-freeze checklist

- Qualified source ledger; exact private inventory and content commitments;
  consumed/sealed exclusion evidence; component graph; deterministic allocation.
- Executable transformation recipes and tools, frontend constants, feature
  list, numerical policy, model parameter count, dependencies and license review.
- Synthetic technical tests for alignment, no shortcuts, grouping, thresholds,
  missing outputs, metric denominators, bounds and privacy.
- Clean committed execution head, passing exact-head tests, bound runner hashes,
  runtime/resource preflight, and a unique no-clobber output directory.
- No successor real-audio predictions before these items are satisfied.

## Metadata-only tooling and current verification

`python3 scripts/music_verdict_study.py` reproduces the zero-alert sample-size
calculation without opening any data. `--inventory <private.json>` checks a
curated schema-version-1 object containing `sources`. Each source requires
`source_id`, `partition`, globally reconciled nonempty `artist_ids`, `session_ids`
and `lineage_ids` arrays, `provider_id`, `audio_sha256`, boolean `consumed`,
`sealed` and `real_finished_music`, `provenance_status`, `rights_status`, and
nonempty `provenance_refs` and `rights_refs` arrays. Include all known performers,
not only the credited front-person. The byte hash is an additional duplicate
edge, not proof that different hashes mean independent music.

The preflight rejects split-crossing transitive components, duplicate IDs,
missing metadata, sealed/consumed validation sources, unqualified labels,
insufficient independent groups and lack of a held-out provider. It emits
aggregate counts only. It **does not verify the truth of the curator's evidence
or grant execution readiness**, even when all metadata assertions pass.
Research-only rights are reported separately from rights to distribute weights.

The new focused suite passes 23 synthetic tests, including exact-bound checks,
shared secondary performers, transitive grouping, copied/renamed sources,
duplicate JSON keys and privacy-safe error output. The preservation check
confirms all 980 historical research files are unchanged. These are engineering
checks, not validation of any real source or model.
