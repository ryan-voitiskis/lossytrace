# Factorial benchmark v2 explainable-control adapter preregistration

Date: 2026-08-03

State: frozen before any A0-A4 or R1/R2 score is opened on factorial v2

## Purpose and non-candidate boundary

This adapter reruns the already-rejected exact-hybrid A0-A4 and
codec-projection R1/R2 families as explainable raw-score controls on the
factorial v2 mechanism-development population. It asks whether either old
physical feature has a stable within-source effect under the larger source and
processing matrix. It does not revive either family as a candidate.

No v2 threshold, support rule, classifier, calibration, score combination, or
edge conjunction will be fitted. The output reports support, distributions,
paired positive-minus-reference direction, source-domain reversals, and
within-family correlations. All seven rows remain non-promotable even if a
descriptive comparison is favourable. Encoder-transfer and external-transfer
features and scores remain sealed, and the public verdict remains disabled.

## Fixed population

The only authorized partition is `mechanism_development`. Selection includes:

- all 4,665 negative factorial cases;
- all 1,367 controlled-positive cases whose codec family is MP3; and
- no AAC, Vorbis, encoder-transfer, external-transfer, or holdout case.

The resulting 6,032 factorial cells contain 4,090 unique decoded PCM sequences
and 5,895 PCM/lossless-wrapper representatives across all 527 source groups.
There are 1,391 PCM identities represented through more than one lossless
wrapper.

The runner scores one stable representative for every exact
decoded-PCM/lossless-wrapper pair. It propagates measurements to factorial
aliases only after every WAV, FLAC, and AIFF representation of identical PCM
has exactly equal non-timing output. Any artifact-hash drift, inventory drift,
or wrapper mismatch stops the run.

## Frozen measurements

### A0-A4 exact hybrid

The implementation, formulas, support rules, phase offsets, and source
preparation remain those in the
[`exact-hybrid preregistration`](exact-hybrid-ablation-preregistration-20260801.md):

- start at 5 seconds and decode at most 20 seconds;
- mono 44.1 kHz floating-point PCM;
- pinned ISO Layer III analysis filterbank and long-block hybrid MDCT;
- A0 archived phase-zero statistic;
- A1 subband-relative statistic;
- A2 five-region time median;
- A3 median over at least six of eight fixed phases; and
- A4's unchanged content guard.

The v2 population contains short material for which the fixed five-second
start supplies no supported granule. The bound oracle's exact error
`no supported exact-hybrid granules` is mapped only to an explicit unsupported
result with all A0-A4 scores absent. It is never discarded, imputed, or treated
as a successful negative. Any other oracle error stops the run.

The old fixed edge corroboration (`spectral_edge_drop_db > 3.0` and
`spectral_edge_persistence >= 0.0015`) is joined from the already-frozen
feature-version-0 private report and summarized separately. It is not used to
filter the primary raw paired calculation and no edge or A-row threshold is
selected.

### R1/R2 codec projection

The implementation, formulas, canonicalization, support rules, LAME CBR-128
projection, and two controlled codec cycles remain byte-bound to the
[`codec-projection preregistration`](codec-projection-preregistration-20260802.md)
and `research/codec-projection/oracle-v1/config.json`:

- R1 is `e2 / (e1 + e2)`;
- R2 is the absolute, per-channel-demeaned cosine recurrence between the two
  cycle residuals;
- each case score remains the median of supported one-second blocks; and
- short, quiet, clipped, or insufficient-residual material remains explicitly
  unsupported.

R1 and R2 are two summaries of one codec-projection mechanism, not independent
corroboration. The fixed oracle is research-only and product-ineligible because
it invokes an external encoder and performs two extra codec cycles.

## Analysis fixed before execution

For each A0-A4 and R1/R2 score separately, the path-free analyzer reports:

- factorial-case, unique-PCM, and source-group support;
- support and score distributions by expectation and source domain;
- negative history-class and positive encoder slices;
- positive score minus exact matched-reference score after exact-PCM-pair
  deduplication and stable identity-first factorial attribution;
- one median delta and direction per source group;
- the 90% positive-direction and 85% one-sided Wilson-lower comparison;
- whether every source domain is strictly above 50% paired direction; and
- Pearson and Spearman correlations within A0-A4 and within R1/R2, both for
  supported unique-PCM scores and paired source-group deltas.

The direction comparison is descriptive and cannot promote a retained
baseline. Missing support remains visible in both the denominator and the
paired eligible-group count. Accuracy, precision, false-positive rate, and
calibration are unavailable because no v2 classification boundary exists.

## Determinism, checkpoints, and compute

Every source artifact, private manifest, parent plan, feature report, oracle
source, Cargo input, helper, adapter, analyzer, and runtime binary/toolchain is
hash-bound. Per-artifact measurements and timings are written atomically to
separate private checkpoint trees. Timing is excluded from the reproducible
measurement and public aggregate. Rerunning with identical commitments must
produce byte-identical non-timing reports irrespective of completion order.
If a restart leaves a timing row without its authoritative atomic measurement
checkpoint, only that generated timing row is discarded and the measurement
is repeated under the same binding.

At most six concurrent workers may be used. Concurrency affects only runtime
and progress order; the final report is sorted and deterministic. This caps
long-running work near 60% of the present ten logical CPUs while allowing the
user-authorized machine utilization.

Private identities, paths, audio hashes, raw measurements, commands containing
paths, timings, and binaries stay outside Git. The committed aggregate rejects
private keys and absolute paths.

## Stop conditions and next decision

Stop without score repair if any bound hash, selected inventory, resume
commitment, formula replay, support state, or wrapper-invariance check differs.
Do not open encoder-transfer or external-transfer evidence.

After both controls and the learned failure atlas are frozen, decide whether
the full baseline evidence warrants either of the two separately predeclared
new physical representations. At most those two representations may then be
preregistered. If the paired discovery gates do not justify them, close with a
rigorous non-identifiability result instead; that is a successful scientific
outcome.
