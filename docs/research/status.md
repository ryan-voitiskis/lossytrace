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
identity is complete. The identity-only
[`source-allocation procedure`](source-allocation-preregistration-20260802.md)
was then applied twice. The private candidate index and exact 793-member
allocation were byte-identical, the VCTK 28-per-gender cap held, and RWC found
a complete 85-family matching with 85 distinct normalized titles. See the
path-free [`source-allocation result`](source-allocation-result-20260802.md).
The subsequent [`factor-level freeze`](factor-level-freeze-20260802.md) fixes
a maximum 12-second identity-hashed excerpt, matched mono/stereo
preconditioning, 16 development and 8 encoder-transfer setting templates, five
history-decoder levels, nine PCM hard-negative transforms, and an ephemeral
one-worker storage boundary. The exact
[`toolchain preregistration`](toolchain-freeze-preregistration-20260802.md)
originally expanded those templates into 48 commands and 132 compatible
decoder paths while keeping source allocation and scoring closed. Its first
replay stopped because LAME CBR-96 stereo chose 32 kHz; the committed
[`correction`](toolchain-factor-correction-20260802-001.md) explicitly binds
all LAME settings to the frozen 44.1 kHz rate. The next replay found that
FFmpeg native Vorbis supports only two encoded channels. The separately committed
[`factor correction`](factor-level-correction-20260802-001.md) makes that
transfer lineage stereo-only, narrows the claim explicitly, and leaves 46
realizable expanded settings. Corrected
[`toolchain recipe 003`](toolchain-factor-correction-20260802-002.md) now binds
those 46 settings, 126 decoder paths, coarse bandwidth observations, and
transform/wrapper golden outputs. Its first complete replay exposed an
internal 40-versus-36 transform-path double count: wrapper rewriting already
has a separate 12-path section. Corrected
[`recipe 004`](toolchain-factor-correction-20260802-003.md) changes no command
or algorithm. Its two fresh complete replays were byte-identical: all 46
settings, 126 decoder paths, 36 ordinary transform paths, and 12 wrapper paths
were deterministic, while every cross-decoder comparison produced different
exact PCM. See the
[`exact-toolchain result`](toolchain-freeze-result-20260802.md). Fresh public
decoder wrapper equivalence is now separately
[`preregistered`](public-decoder-equivalence-preregistration-20260802.md) with
a source-bound public build and exact 12-path comparison. The public
0.1.0-alpha.1 binary was
[`hash-bound`](public-decoder-binary-binding-20260802.md) before execution, and
the two fresh
[`equivalence replays`](public-decoder-equivalence-result-20260802.md) are now
byte-identical, with exact public evidence across all 12 wrapper paths. The
exact-toolchain gate is complete. Fractional-assignment recipe `001` was
committed before execution and replayed byte-identically, but construction
review then found that target sample rate was absent from its cells and
matched-reference identity. Its
[`result`](fractional-assignment-result-20260802.md) is retained as rejected
evidence. The separately frozen
[`correction`](fractional-assignment-correction-20260802-001.md) makes sample
rate a first-class exact-match factor. Corrected recipe `002` required two
fresh private replays before construction. Those recipe-`002`
[`replays`](fractional-assignment-result-20260802-002.md) were byte-identical,
but construction-lineage review found that generated cells did not explicitly
name their identity recipe source. The separately frozen
[`correction`](fractional-assignment-correction-20260802-002.md) distinguishes
the shared identity source from a positive's matched transformed H0 and fixes
the manifest validator's corresponding role conflation. Recipe `003` now
required two fresh private replays. Those
[`replays`](fractional-assignment-result-20260802-003.md) are byte-identical:
793 groups map to 12,884 cells, all 6,356 positives have exact transformed H0
matches, and every generated H0/H1 names its identity PCM source. One-worker,
resumable case construction is now the next gate. No assigned audio was
generated by any assignment recipe.
Before audio generation, a separately frozen
[`construction-feasibility audit`](construction-feasibility-preregistration-20260802.md)
will replay exact source headers and transform minima twice. It cannot inspect
waveform samples or alter the assignment; any unsupported group stops
construction for an explicit correction.
Its first invocation stopped before source inspection because the plan omitted
the FFprobe tool ID. The separately frozen
[`configuration correction`](construction-feasibility-correction-20260802-001.md)
adds only that exact binding; recipe `002` still requires two complete replays.
Recipe `002` subsequently stopped on a selected `pcm_f32le` source because its
lossless whitelist enumerated only integer PCM. The separately frozen
[`codec-scope correction`](construction-feasibility-correction-20260802-002.md)
accepts `flac` or `pcm_*` while still rejecting compressed lossy codecs.
Recipe `003` now requires two complete replays.
Those
[`replays`](construction-feasibility-result-20260802-003.md) are byte-identical.
All 793 source headers have supported lossless codecs and channel counts, but
11 assigned groups violate the trim or 3-second-prefix minimum. Construction
is not authorized. The next gate is a separately frozen assignment correction
that may use duration only as the already-declared transform feasibility
predicate; it may not replace a source, inspect waveform content, or use a
score.
That correction is now frozen as fractional-assignment recipe `004` in
[`fractional-assignment-correction-20260802-003.md`](fractional-assignment-correction-20260802-003.md).
It derives eligibility for every group-transform pair from the already-bound
header evidence, then applies the unchanged recipe-`003` purpose-separated
ranking within eligible groups. Raw frame counts and sample rates cannot enter
the ranking or assignment output. The
[`recipe-004 result`](fractional-assignment-result-20260802-004.md) now records
two byte-identical assignments: 793 groups, 12,885 cells, 6,356 positives, and
6,529 references, with all quotas passing. A successor header-only feasibility
audit is now frozen as
[`construction-feasibility recipe 004`](construction-feasibility-correction-20260802-003.md).
It binds both the exact private assignment and its public attestation and must
pass twice before a separate construction recipe can be authorized. Those
[`two replays`](construction-feasibility-result-20260802-004.md) are now
byte-identical across all 793 headers with zero unsupported transform or
channel groups. The next gate is an exact, resumable, one-worker construction
recipe; no audio is yet generated or authorized outside that recipe.
Review of the construction boundary found that end-to-end source
preconditioning had not yet been synthetically replayed across native s16,
s24, and f32 PCM. A six-case, two-replay
[`preconditioning audit`](preconditioning-audit-preregistration-20260802.md) is
now complete. Its
[`six synthetic cases`](preconditioning-audit-result-20260802.md) are
byte-identical within and across two full replays for s16, s24, f32, mono,
stereo, native-rate, resampled, bounded-window, and long hashed-crop paths. The
next gate is an exact constructor and path-free disk/recipe preflight; no
benchmark waveform has yet been read.
That metadata-only
[`construction preflight`](construction-preflight-preregistration-20260802.md)
is now frozen for two replays. It validates all 12,885 recipe lineages and
requires the external output volume to cover a conservative retained-size
ceiling, 2 GiB workspace, and the 15 GiB reserve without reporting ambient
free bytes. Its
[`two replays`](construction-preflight-result-20260802.md) are byte-identical;
all 12,885 lineages pass, and the selected external volume covers the
31,917,486,459-byte retained ceiling plus workspace and reserve. The next gate
is the exact constructor, synthetic checks, and a separately committed audio-
generation authorization.
That exact
[`constructor`](construction-preregistration-20260802.md) is now frozen with
synthetic-only authority. The same checkpointed engine contains future smoke
and full paths, but both refuse to run until a committed successor plan binds
the preceding evidence. Thirteen synthetic cases cover every encoder,
history decoder, transform, and wrapper before any benchmark waveform may be
decoded.
No successor mechanism score or retained holdout has been opened.
