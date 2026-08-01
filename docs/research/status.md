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
