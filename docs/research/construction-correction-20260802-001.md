# Factorial benchmark v2 construction correction 001

Date: 2026-08-02

State: constructor authority expanded from synthetic fixtures to exactly the
frozen 202-cell score-blind smoke selection before benchmark waveform access;
full construction, features, scores, and unopened labels remain unauthorized

## Trigger

The two complete 13-case constructor reports are byte-identical. Their
path-free attestation has SHA-256
`0ff79ee2a54c416bb486320c295eabdff96bfffcb391edc60c7a28ae718b8590`.
It covers every frozen encoder implementation, history decoder, transform, and
wrapper using the exact render function that will process benchmark cells.

## Narrow authority change

The constructor code and every upstream binding remain byte-for-byte
unchanged. This correction authorizes `scope=smoke` only. The code continues to
reject `scope=full`.

The 202 cells were selected before waveform access and without scores by the
minimum frozen recipe digest independently across:

- all 46 expanded encoder settings;
- every compatible history-decoder and codec combination;
- every positive transform and codec combination;
- every partition, transform, wrapper, and expectation combination; and
- every native source codec, channel treatment, and target-rate combination.

Deduplication leaves 108 controlled positives and 94 negatives across 100
development, 68 encoder-transfer, and 34 external-transfer cells. External
transfer still contains negatives only; the 100 future-positive reservations
remain uninstantiated.

## Replay contract

The smoke must render into two separate empty external roots. Each cell must
pass exact recipe, wrapper, and canonical PCM validation and atomically commit
its artifact and private checkpoint. The two sorted private manifests and two
path-free run reports must match byte-for-byte.

The run stops on an out-of-scope cell, binding change, wrapper/PCM mismatch,
checkpoint mismatch, artifact disagreement, reserve breach, feature or score
read, external-positive construction, private-path leak, or public verdict.

Only a committed result from both smoke roots may support a later full-build
correction.
