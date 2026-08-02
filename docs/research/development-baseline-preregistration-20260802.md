# Factorial benchmark v2 development-baseline preregistration

Date: 2026-08-02

State: exact fixed, descriptive, and learned baseline protocols frozen before
any benchmark waveform is decoded for analysis; encoder and external transfer
remain sealed

## Question

How much of the apparent lossy-versus-PCM separation from prior systems
survives exact matched-reference comparisons, duplicate-PCM collapse, complete
source-domain folds, and the v2 hard-negative population?

This is a baseline and failure-atlas stage, not candidate selection. The
population is the 9,653-case mechanism-development partition: 4,988 controlled
positives and 4,665 negatives from 527 source groups and six source domains.
It contains 7,701 distinct decoded PCM sequences and 9,513 distinct retained
artifact byte sequences. Encoder-transfer and external-transfer waveforms,
features, scores, and labels remain unopened.

The machine-readable
[`development-baseline plan`](../../benchmarks/audio-integrity-v2/development-baseline-plan.json)
binds the private analysis and constructor manifests, exact implementations,
tool binaries, environment, model definition, metrics, outputs, and stop
conditions.

## Baselines

### Exact Cannam fixed rule

Replay repository revision
`7a70bd8d15e68b0b1942a9d3deac6ad4d8293b8b` and its published weights.
A window is positive at `cf >= 0.5`; a file is positive when at least 25% of
its windows are positive. The entire retained file is supplied without new
preprocessing. The continuous comparison score is the positive-window
fraction, which is not interpreted as a probability. Neither threshold may be
tuned.

### Feature-version-0 measurements

Run the exact current verdict-free LossyTrace measurements over the complete
file. These remain descriptive measurements: no classifier, threshold,
accuracy, calibration, or ensemble is constructed. Their purpose is to expose
support and matched-reference deltas across the new factor matrix.

### Koops-style CRNN replication

Run naive and random-high-frequency-mask training under identical six-fold
leave-one-source-domain-out evaluation. The model follows Koops, Micchi, and
Quinton's published two-second 44.1 kHz mono magnitude-spectrogram, four CNN
blocks, two-layer bidirectional LSTM, and two-output classification design.
The masked condition samples a separate uniform 14 kHz-to-Nyquist cutoff for
every training example and never masks validation or evaluation.

This is not an exact reproduction: the authors publish neither code nor
weights, and the paper does not specify convolution channel counts,
spectrogram hop defaults, optimizer, learning rate, batch size, or training
schedule. LossyTrace freezes its earlier local choices—channels
16/32/64/128, 1,024-point Hann magnitude STFT with hop 512, log and
per-example standardization, Adam at 0.001, batch 32, at most 30 epochs, and
patience five. Checkpoints minimize grouped inner-validation log loss, with
AUC only as a tie-break. The reported classification boundary is fixed at
0.5; AUC is diagnostic. Cross-entropy is the only training loss. No paired
ranking loss, resampling, class weight, or threshold search is allowed.

Every fold runs on deterministic one-thread CPU with seed 20260802. A canonical
representative of each unique decoded PCM participates once per epoch. This
avoids turning wrapper or recipe duplicates into extra training evidence, but
it also leaves the observed 4,964-positive/2,737-negative unique-PCM class
mix intact rather than manufacturing the paper's balanced private library.

### Retained explainable controls

The already-rejected exact-hybrid A0-A4 and codec-projection R1/R2 families
will be rerun only as raw paired controls over all development negatives and
all development MP3 positives. Their definitions and earlier support rules
are unchanged; no v2 threshold or support rule may be fitted. A v2 adapter
must be separately committed and hash-bound before these scores are opened.
The rejected AAC lattice result remains historical only because another run is
not justified by its retained-source terms or prior negative outcome.

## Duplicate PCM and wrapper invariance

Signal-only methods must return the same deterministic measurement for the
same decoded samples. The runners therefore score every distinct retained
artifact but treat exact decoded-PCM duplicates as one analysis value.
Represented WAV, FLAC, and AIFF artifacts with identical PCM must have exactly
equal feature values, continuous scores, support states, and window counts.
Any mismatch stops the run.

Case-level tables remain useful descriptions of the factor matrix, but the
primary paired calculation removes exact duplicate positive/reference PCM
pairs, computes positive minus exact matched-reference score, and takes one
median direction per source group. If observationally identical cells carry
multiple factorial aliases, attribution prefers the identity post-transform,
then a lexicographic post-transform, encoder-lineage, and encoder-setting
order; the alias count remains reported. The analysis then stratifies by
domain, codec, encoder, setting, and post-transform. A 90% positive direction with a
one-sided 95% Wilson lower bound of at least 85% is reported for comparability
with the identifiability contract; it cannot promote a baseline.

## Interpretation and stopping rule

All accuracy, precision, and error rates describe this selected development
population only. They are not real-library prevalence estimates, calibrated
history probabilities, independent validation, or evidence that unrestricted
history is identifiable.

The stage stops on any partition leak, hash drift, wrapper-invariance failure,
fold overlap, post-score protocol change, or private-data leak. A weak,
source-dependent, or null baseline result is successful evidence. Only after
the complete failure atlas is frozen may the study decide whether the two
predeclared physical mechanism representations are scientifically warranted.
