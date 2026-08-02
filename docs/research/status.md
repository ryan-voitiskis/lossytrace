# Research status

LossyTrace currently has a useful measurement and evaluation platform, but no
release-safe lossy-source verdict.

| Candidate | Outcome | Reusable result |
| --- | --- | --- |
| v28 | Rejected after external-transfer false positives | Conservative two-grid infrastructure |
| v29 | Development-only after the earlier gate was consumed | Multi-candidate MP3 confirmation and performance harness |
| v30 | Rejected | AAC phase and quantization diagnostics |
| v31 | Rejected for no useful incremental recall | MP3 frame evidence machinery |
| v32 | Rejected for zero supported DEMAND recall | Exact ISO Layer III hybrid-transform probe |
| v33 | Rejected for weak music AAC recall and eight SQAM invariance mismatches | Low-band MP3 tail-flatness diagnostic |
| v32 + v33 | Rejected post-hoc diagnostic | Evidence that the families are complementary, not a releasable policy |
| 2026-08-01 exact-hybrid A0–A4 | Rejected: every row had a source-domain false positive and only 14–23% supported MP3-128 recall | Reproducible exact replay and source-domain ablation harness |
| 2026-08-02 codec projection R1–R2 | Rejected: both rows had a source-domain false positive and zero supported MP3-128 recall | Deterministic two-cycle oracle, grouped analyzer, and path-free negative result |
| 2026-08-02 Cannam fixed-rule CNN | Rejected: 99.44% P1 recall but 67.53% negative-case false positives and alerts in 545/597 negative source groups | Exact-revision replay, duration audit, and path-free cross-domain failure atlas |

The v32+v33 diagnostic reached strong observed development recall and zero
supported-negative alerts, but failed eight SQAM AAC invariance groups. Those
cases are consumed evidence and cannot be used to tune a new candidate.

The release-held-out labels remain unopened. A future positive verdict needs a
materially new candidate, a freshly acquired independent transfer set, the
sealed release gate, and a separately versioned policy. Until then:

- evidence schema: `1`;
- measurement feature version: `0`;
- public verdict: disabled; and
- Reklawdbox integration: prohibited.

The latest frozen checkpoint also leaves the 280-case future codec-only subset
sealed. See
[`codec-projection-result-20260802.md`](codec-projection-result-20260802.md)
for the latest methodology, path-free result, evidence hashes, and stop
decision. The broader independent-validation checkpoint remains documented in
[`independent-validation-checkpoint-20260801.md`](independent-validation-checkpoint-20260801.md).

The comparative review of published detectors, the retained exact-revision
Cannam evaluation, and the recommended successor research program are in
[`lossy-detector-comparison-and-next-direction-20260802.md`](lossy-detector-comparison-and-next-direction-20260802.md).

The approved successor program is now governed by the
[`decoded-PCM identifiability contract`](decoded-pcm-identifiability-contract-20260802.md),
the
[`baseline failure-atlas preregistration`](baseline-failure-atlas-preregistration-20260802.md),
and the machine-validated
[`factorial benchmark v2 contract`](../../benchmarks/audio-integrity-v2/README.md).
The first baseline audit amendment records that the historical pilot used full
tracks while the retained cases are 30-second excerpts; its comparison stopped
before P1 and the corrected same-input replay was byte-identical. The completed
5,280-case P1 replay then rejected the fixed Cannam rule because 1,171/1,734
negative cases and 545/597 negative source groups alerted. See the
[`amendment`](baseline-failure-atlas-amendment-20260802-001.md) and
[`path-free result`](cannam-fixed-rule-failure-atlas-result-20260802.md).
The next milestone has inventoried implementation lineages and candidate
source collections without generating audio or freezing a selection; see the
[`factorial benchmark inventory`](factorial-benchmark-inventory-20260802.md).
Its deterministic synthetic plumbing audit verified ten retained encoder
bindings and 27 compatible decoder paths, rejected Apple MP3 encoding on the
bound OS build, and substituted a pinned BladeEnc transfer lineage. See the
[`toolchain probe result`](toolchain-probe-result-20260802.md).
The source-identity gate has now bound Lombard Grid, SONYC, SATP, RAVDESS,
TinySOL, FSDD, VCTK, and RWC to acquired archive bytes and path-free
evidence. The
[`RAVDESS audit`](ravdess-source-identity-audit-20260802.md) retained 24 actor
groups while recording one same-actor repeated-PCM pair and six stereo
outliers; neither was hidden by preprocessing. The
[`TinySOL audit`](tinysol-source-identity-audit-20260802.md) retained one
common-collection group, 2,273 non-retuned paired-master candidates, and 640
declared PCM-transform rows. A subsequent primary-paper audit found that most
Speech Commands contributions passed through OGG before the released PCM
WAVs. It was therefore
[`rejected as a Tier A candidate`](speech-commands-provenance-rejection-20260802.md),
not relabelled. The
[`source-partition correction`](source-partition-correction-20260802.md) moved
RAVDESS to encoder transfer and added six audited FSDD speaker groups, leaving
102 encoder-transfer groups and 164 external-transfer groups. The
[`VCTK audit`](vctk-source-identity-audit-20260802.md) found 58 released
speaker IDs behind the nominal 56-speaker label and preserved the 56-group
denominator through an unapplied, content-independent 28-per-gender cap. The
subsequent [`RWC audio audit`](rwc-source-identity-audit-20260802.md) bound all
five provider archives, reconciled all 328 annotation IDs, found 328 distinct
PCM payloads, and retained the conservative 85-family boundary. Source
identity is complete; source allocation, factors, tool bindings, and
fractional assignment remain separate freeze gates.
No successor mechanism score or retained holdout has been opened.
