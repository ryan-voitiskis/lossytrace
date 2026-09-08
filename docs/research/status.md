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
| 2026-08-03 naive/masked CRNN | Baseline failure: naive alerted on 518/527 negative groups; masking collapsed to 527/527 and only 59.20% paired direction | Deterministic six-domain folds, restart-safe checkpoints, and path-free learned-baseline failure atlas |
| 2026-08-03 v2 retained controls | Protocol stop: A0-A4 could not complete the fixed-duration population; complete R1/R2 scores remain uninterpreted | Hash-bound stop record, 5,735 atomic exact checkpoints, and byte-identical 5,895-case projection replay |

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
Those
[`constructor replays`](constructor-synthetic-result-20260802.md) are now
byte-identical for all 13 cases, including codec bitstreams, each PCM stage,
and final wrapper bytes. The next permitted authority change is limited to two
separate 202-cell smoke roots; full construction remains stopped.
The separately committed
[`smoke correction`](construction-correction-20260802-001.md) now authorizes
exactly those 202 cells: 108 positives and 94 negatives selected without
scores across all declared construction categories. The same code still
rejects full scope, and the two smoke roots must yield byte-identical private
manifests before authority can expand.
Those two
[`smoke replays`](constructor-smoke-result-20260802.md) are now byte-identical
across all 202 retained artifacts, private checkpoints, and canonical
analysis-PCM hashes. The smoke gate passes. The separately committed
[`full-build correction`](construction-correction-20260802-002.md) binds the
public result and private-manifest hash and now authorizes exactly the frozen
12,885-cell one-worker build. That
[`full construction`](constructor-full-result-20260802.md) is now complete:
6,356 controlled positives and 6,529 matched negatives have exact retained
artifact and canonical analysis-PCM attestations. Feature extraction and
scoring remain blocked behind a separately frozen plan. The separately frozen
[`analysis-manifest gate`](analysis-manifest-preregistration-20260802.md) has
now also completed after three documented metadata-only corrections. Its two
fresh full replays are byte-identical and the path-free
[`result`](analysis-manifest-result-20260802.md) validates all 12,885 cases
against the structural, mechanism-development, and encoder-transfer profiles.
No waveform was decoded for analysis, no score was opened, and encoder and
external transfer remain sealed. The next authority change is limited to a
separately frozen mechanism-development baseline and feature plan.
That
[`development-baseline plan`](development-baseline-preregistration-20260802.md)
was prepared with exact tool and implementation bindings. It limits the
first analysis pass to the fixed Cannam rule and feature-version-0
measurements, followed by matched naive/masked CRNN source-domain folds. Exact
decoded-PCM duplicates are one analysis unit, every represented wrapper is an
invariance check, and no baseline can be promoted by this stage. The fixed
runs are now complete and documented in the
[`development fixed-baseline result`](development-fixed-baseline-result-20260802.md).
Cannam reached 91.82% recall but 64.05% negative false positives and only
46.68% matched-reference positive direction. No feature-version-0 measurement
met the 90% direction plus 85% one-sided lower-bound gate; the nearest,
spectral-edge height, had incomplete support and reversed on NSynth train.
The naive/masked CRNN folds are now complete and documented in the
[`development CRNN baseline result`](development-crnn-baseline-result-20260803.md).
Naive reaches 98.30% recall only by producing 95.48% negative-case false
positives and alerts in 518/527 negative source groups. Random high-frequency
masking does not improve robustness: it labels every case positive, alerts in
all 527 negative groups, and reaches only 59.20% paired positive direction
with a 55.64% one-sided Wilson lower bound. The frozen
[`v2 explainable-control adapter`](explainable-control-v2-adapter-preregistration-20260803.md)
then stopped under its own rules. A0-A4 produced only 5,735/5,895 authoritative
checkpoints because the bound oracle treated every remaining three-second
artifact as insufficient PCM before reaching the adapter's single authorized
unsupported state. R1/R2 completed, passed wrapper invariance, and replayed
byte-identically, but their scores remain uninterpreted because the frozen
analyzer requires both complete reports. The
[`protocol-stop report`](development-explainable-control-protocol-failure-20260803.md)
records the failure without a post-score support or analysis change. No
retained transfer score has been opened.

The completed interpreted atlas has no representation meeting the frozen 90%
paired-direction and 85% one-sided lower-bound gate without a source-domain
reversal. The
[`decoded-PCM identifiability result`](decoded-pcm-identifiability-result-20260803.md)
therefore closes this program as a conditional negative: no new representation
is preregistered, no transfer score is opened, and the public library remains
verdict-free at feature version 0.

## Perceptual-degradation program - 2026-08-04

The successor program targets audible, material degradation rather than codec
history. Its frozen
[`research contract`](perceptual-degradation-contract-20260803.md),
[`literature review`](perceptual-degradation-literature-review-20260803.md),
alignment/schema fixtures, listening protocol, allocator, power analysis, and
synthetic player all preserve the public feature-version-0, verdict-free
boundary. Retained waveforms, sealed labels, provider audio, human responses,
and public metric execution remain unopened or unauthorized.

ViSQOL Audio v3.3.3 has been built and replayed only on the four frozen
synthetic cases in two independently bound environments. The different binary
builds produced exactly zero numeric delta in MOS-LQO, similarity, all 32
frequency-band similarities, and all 12 patch similarities. This establishes
synthetic execution determinism, not perceptual validity or human calibration.
The BS.1387-derived proxy remains blocked by its legal/conformance gate.

The private
[`lossless delivery layer`](perceptual-degradation-private-lossless-delivery-20260804.md)
now accepts only bounded, hash-bound integer PCM-WAV outside the repository. A
loopback-only server projects opaque IDs and PCM geometry without paths,
recipes, roles, scores, identities, or responses. Chrome 150 successfully
verified a deterministic ephemeral 48 kHz stereo fixture, exposed exactly
192,000 PCM frames without requesting resampling, and exercised Play, Left,
and Right with no console error or browser storage. The generated WAV, private
map, and new browser snapshots were moved to Trash after observation.

That result closes only the byte-to-Web-Audio delivery dry run. It is not an
audibility result, a listening response, physical playback qualification, or a
frozen listening player. The next gate is a score-blind source-and-licence
manifest plus the declared physical playback chain. Actual study stimuli,
licences, player switching/loop behavior, DAC/transducer/level/room evidence,
privacy operations, responsible-human approval, recruitment, and response
storage all remain incomplete. No no-reference estimator is eligible until
fresh listening evidence calibrates and independently validates the
full-reference oracle.

A second bounded ODAQ metadata audit retained the creator, title, source, and
licence fields that the first score-blind audit had intentionally omitted. It
made four Range requests totalling 151,153 bytes and again opened only the
licence and disclaimer members: no WAV, score row, or archive payload was
opened. The 16 selected development groups bind 128 WAV members and comprise
15 CC BY sources plus one CC0 source. Nine sources have complete direct
attribution fields. Seven Fraunhofer-derived mixes retain their raw `n/a`
titles and descriptive source fields, but the audit also binds the two
explicitly referenced preceding source rows for each mix: 14 dependency
records covering Blender Studio/Foundation, Netflix, Nina Paley, and
Freesound material under CC BY or CC0. All 16 development attribution notices
are therefore ready without rewriting the provider metadata. The whole-study
licence gate remains unfrozen: ODAQ is one-provider, simulated-artifact
development evidence—not real codec, grouped-transfer, or final-validation
evidence—and no audio acquisition is authorized.

The subsequent
[`source/condition qualification`](perceptual-degradation-source-condition-qualification-20260804.md)
binds only the existing path-free source inventory, allocation aggregates,
codec templates, toolchains, and ODAQ attribution evidence. It identifies
actual-codec, transparency-candidate, natural-hard-negative, and grouped
transfer candidates across four codec families without opening audio, scores,
private identities, or sealed evidence. Its version-2 listening schema calls a
nominal high-quality encode a `transparency_candidate`; codec settings cannot
assign transparency before the frozen listening analysis, while the historical
version-1 files remain byte-bound to their player observations. The listening
manifest remains unfrozen because independently grouped mastered-music breadth,
licence and attribution operations, six production/multi-generation recipe
families, private excerpt selection, and fresh final-validation evidence are
still missing.

The next score-blind
[`production and generation control preregistration`](perceptual-degradation-production-generation-control-preregistration-20260804.md)
freezes four exact signed-16 PCM recipes for clipping, equalization, limiting,
and stereo width plus eight two-generation codec paths. The codec paths cover
same-setting repetition and a balanced cross-codec cycle across MP3, AAC-LC,
Opus, and Vorbis using already-bound encoder and decoder commands. Recipe names
and settings remain controlled-condition metadata, never impairment or
transparency targets. The implementation and its execution authority are now
hash-bound before observation. A pre-execution correction makes the 44.1/48 kHz
transition explicit: decoded PCM is preconditioned with an exact dither-free
bound FFmpeg resampler before the next encoder input, because not every frozen
encoder command forces its declared input rate. No codec command, PCM
transform, or synthetic replay has yet been observed under that authority. The
next gate is two fresh byte-identical path-free reports covering the 12
synthetic-only cases. Actual stimuli, audio access, metrics, listener evidence,
and all perceptual truth remain unopened and unauthorized.

After commit `9b6d2ba613e89b418030b0fedf0f6a73f7137fb7` passed exact-head
CI, the authorized synthetic replay ran exactly twice in fresh temporary
directories. Both 12-case reports were byte-identical with SHA-256
`099b5ac6eff9a705dfa4575a55ea827d56808890b92932f4379e187854178137`.
All four production controls exceeded the frozen changed-frame support floor;
all eight two-generation codec paths completed, and only the two declared
44.1/48 kHz transitions resampled. Generated PCM and bitstreams were removed
after checking; the full reports were moved to recoverable Trash and are not
part of the research corpus. The retained
[`path-free replay result`](perceptual-degradation-production-generation-synthetic-replay-20260804.md)
binds the aggregate observation without assigning perceptual truth. These
recipes are now eligible for future manifest construction, while actual audio
acquisition and stimulus generation remain unauthorized pending source breadth,
licence/attribution, excerpt, and physical-playback gates.

The subsequent
[`mastered-music and playback qualification`](perceptual-degradation-mastered-music-playback-qualification-20260804.md)
uses current primary-source metadata without acquiring or previewing audio. RWC
provides the strongest mastered reference, with five lossless professional
subcollections but only one provider stratum. Fresh, composition-disjoint
MAESTRO material can add a separate high-fidelity piano domain, and mshoxxDB
can add a small mono electronic-production calibration stratum. MusicNet and
MedleyDB remain deferred pending item-level provenance/licence or provider
consent; FMA and MTG-Jamendo cannot become clean lossless references. The
current output is only the built-in MacBook Pro speakers at 44.1 kHz, with no
qualified transducer, ambient-noise class, system-effects state, or level
calibration. The next gates therefore require responsible-human NC/SA delivery
decisions and a declared physical playback chain. The earlier synthetic-sound
audibility confirmation is not reused as either qualification or listening
truth.

A metadata-only
[`permissive listening-source fallback`](perceptual-degradation-permissive-listening-source-fallback-20260804.md)
now binds the 16 CC BY/CC0 clean ODAQ references already covered by complete
attribution records. The exact population contains nine music and seven
movie-like soundtrack excerpts, co-located into 13 conservative upstream work
groups. This path avoids a noncommercial or ShareAlike determination for
development listening, but it remains one ODAQ provider stratum. ODAQ's
published processed conditions remain simulated coding-like artifacts or
source-separation/remix outputs, not actual codec labels. Audio, scores,
processed conditions, metrics, and listening remain closed. A responsible
human must still choose this narrower path or the wider NC/SA source track and
declare a qualified playback chain; neither path supplies fresh final
validation by itself.

The successor
[`ODAQ reference-acquisition metadata freeze`](perceptual-degradation-odaq-reference-acquisition-freeze-20260804.md)
ran twice in fresh temporary directories and produced byte-identical plans at
SHA-256 `1a39f50013a4274f60ca7c1771ebad22dcafda6950db87d2ffe4acdfb58ab0e7`.
Each replay made three bounded Range requests totalling 85,617 bytes and opened
only the ZIP central directory. Exactly 16 clean `reference.wav` members are
bound by public identity, CRC32, sizes, ZIP method, family code, and licence
records: 46,721,638 compressed bytes and 54,633,154 uncompressed bytes. No ZIP
member payload, audio, processed condition, licence file, or score was opened;
temporary plan copies were moved to recoverable Trash. The freeze is not an
acquisition authorization and does not choose the narrow source track.

The bounded
[`ODAQ reference extractor`](perceptual-degradation-odaq-reference-extractor-preparation-20260804.md)
is now verified only on generated PCM-WAV ZIP fixtures. It checks exact ZIP
metadata before member access, streams to an opaque private partial file,
verifies CRC32, SHA-256 and PCM geometry, atomically renames, journals progress,
and reverifies retained files on resume. One-worker live transfer is capped at
56 MiB of HTTP Range responses and preserves the 15 GiB reserve; the full
archive cannot fit inside that network bound. Thirteen focused tests pass,
including refusal before provider access for both the current unauthorized
plan and a structurally valid but uncommitted authorization. The live command
pins the exact canonical freeze path and SHA-256 and requires a separately
committed, clean authorization successor. No responsible-human source
choice or playback declaration is present, so no provider request or audio
write is authorized.

On 2026-08-13 the responsible human selected the narrow ODAQ CC BY/CC0
development path, accepted its one-provider and attribution limits, and
authorized acquisition only of the 16 exactly frozen clean `reference.wav`
members. The separately committed
[`acquisition authorization`](perceptual-degradation-odaq-reference-acquisition-authorization-20260813.md)
records the declared RME ADI-2 Pro FS to Adam Audio T7V playback chain and
treated domestic living room. Live inventory observed the RME as the current
default two-channel USB output at 96 kHz; exact session-rate agreement, quiet
conditions, fixed listening position, channel checks, and conservative level
calibration remain unqualified. Processed ODAQ conditions, published scores,
stimulus generation, metrics, and listener collection remain unauthorized.

The bounded clean-reference acquisition is now complete and recorded in a
path-free
[`result`](perceptual-degradation-odaq-reference-acquisition-result-20260813.md).
All 16 exact members independently passed byte-length, SHA-256, CRC-32,
authorization-membership, inventory-digest, and FFmpeg geometry checks. The
private corpus totals 54,633,154 bytes: seven 48 kHz stereo 32-bit float
RIFF/WAVE files and nine 48 kHz stereo 24-bit integer
WAVE_FORMAT_EXTENSIBLE files. No partial remains in the retained root. The
full archive was not persisted, and processed conditions, published scores,
metrics, stimulus generation, sealed evidence, and listener responses remain
closed. Because the private browser delivery layer accepts integer PCM only,
the next repository gate is a separately frozen score-blind conversion and
delivery preparation plan; this result does not authorize conversion or
listening.

That score-blind
[`delivery preparation`](perceptual-degradation-odaq-reference-delivery-preparation-20260813.md)
is now frozen and synthetic-only. It canonicalizes extensible 24-bit PCM
without changing sample bytes and maps float32 to signed int32 with
nearest/ties-to-even rounding, no dither, gain, normalization, resampling or
channel transform, and fail-closed non-finite or out-of-range handling. Two
synthetic replays were byte-identical. The tool intentionally has no
live-corpus command: retained-audio access, conversion, stimulus generation,
physical playback qualification, and listening remain unauthorized pending a
separately committed successor.

Physical playback is now separately
[`prepared`](perceptual-degradation-playback-qualification-preparation-20260813.md)
with deterministic synthetic 48 kHz channel and conservative-level fixtures.
Two generated replays were byte-identical and pass the existing private
integer-PCM delivery parser. The RME remains last observed at 96 kHz, so the
responsible human must still set and observe an exact 48 kHz session, verify
left/right routing, quiet fixed-position conditions, effects-off state and a
comfortable fixed level. No retained reference or rating is involved.

The responsible-human
[`playback qualification result`](perceptual-degradation-playback-qualification-result-20260813.md)
now closes that physical-chain gate for the declared RME ADI-2 Pro FS and Adam
Audio T7V setup. The browser and macOS both reported exact 48 kHz, fixture
hashes and frame counts verified, left/right routing passed, session
conditions matched the declaration, the conservative level was held fixed,
and no discomfort occurred. This remains plumbing qualification only—not SPL
calibration, a degradation rating, or perceptual validation. Retained-reference
conversion and playback remain separately unauthorized.

The subsequent score-blind listening-feasibility frontier found that the 16
ODAQ source groups have asymptotic equivalence power only `0.0353439413` under
the frozen source-variance model. The first source count above the `0.80`
target is 39 per truth-bearing partition, requiring at least 156 unique groups
across development, calibration, transfer, and final validation. Additional
listeners cannot repair the 16-source floor, so ODAQ remains development
plumbing and cannot assign transparent-lossy truth or independent transfer.

A metadata-only
[`permissive multi-provider candidate screen`](perceptual-degradation-permissive-multiprovider-source-candidates-20260813.md)
now finds 1,867 conservative groups across seven CC BY exact-member-audit
candidates. This clears only a raw-capacity screen. Qualified and allocated
group counts remain zero: exact member rights and attribution, original coding
history, relationship deduplication, domain balance, whole-provider holdouts,
and resource feasibility are not frozen. MusicNet and permissive-item FSD50K
remain provenance-pending; NSynth and ODAQ remain development-only. No new
audio was acquired or opened, and the narrow ODAQ authorization is unchanged.

The deterministic
[`provider-allocation sensitivity`](perceptual-degradation-permissive-provider-allocation-feasibility-20260814.md)
now shows why the 1,867-group headline is insufficient. Count-only packing can
fill four 39-group partitions, but the witness is completely confounded by
provider and domain. Seven eligible providers cannot supply even two providers
per partition, and the eligible real-music candidates contain only seven
groups after Slakh remains correctly classified as synthetic. MusicNet alone
does not repair a provider-pure final music/speech/natural sensitivity. Adding
both MusicNet and FSD50K makes one arithmetic sensitivity feasible, but remains
scientifically ineligible because their original coding histories and exact
member status are unresolved. No member or operational allocation is frozen.

An evidence-bound
[`objective completion audit`](perceptual-degradation-objective-completion-audit-20260814.md)
now evaluates the entire research contract rather than the latest preparation
checkpoint. Four of fourteen requirements are satisfied: the
degradation-not-history estimand, declared playback prerequisite, verdict-free
public CLI, and acceptance of a rigorous negative outcome. Ten remain
unproven. In particular, deterministic score-free oracle and statistical
replays are synthetic plumbing, no human calibration or perceptual metric
execution exists, grouped transfer is untested, and no-reference work remains
ineligible. No final recommendation is frozen.

A current primary-source
[`GstPEAQ proxy disposition`](perceptual-degradation-gstpeaq-proxy-disposition-20260814.md)
now closes the ambiguity without executing the metric. The 2023 in-force
BS.1387-2 text still requires prior owner consent by licence; the ITU database
returns eight policy-2.2 declarations but warns that it is not authoritative
or complete. GstPEAQ's LGPL-2.0 software copyright terms do not supply that
separate consent, and upstream declares results outside ITU tolerance. Public
records therefore cannot clear internal research execution or redistribution.
The frozen two-family candidate's declared stop condition is triggered. No
successor is silently selected, and this candidate-level stop is not promoted
to a full-objective negative result.

The two provenance-pending source candidates are now separately resolved in a
[`public-record disposition`](perceptual-degradation-pending-source-provenance-disposition-20260814.md).
MusicNet's delivered PCM WAV and source metadata do not establish a complete
recording encoding chain, while FSD50K's released uploader/licence metadata and
downmixed PCM delivery do not expose original upload container or codec.
Neither is promoted to truth-bearing clean-reference status, because using
decoded-PCM codec-history inference to certify clean truth would be circular.
This does not assert that either dataset is lossy or prohibit a separately
frozen provenance-unknown stress/abstention role. The only arithmetically
feasible pending-provider sensitivity is therefore scientifically closed;
additional qualified providers, a narrower primary-domain claim, or rejection
of the current truth-source design still requires responsible-human choice.
No audio, member selection, metric, score, collection, sealed evidence,
no-reference training, or public verdict was authorized.

A successor-neutral
[`additional permissive-provider screen`](perceptual-degradation-additional-permissive-provider-screen-20260814.md)
now binds four purpose-recorded music candidates at exact public versions:
AlbumDB, ChoraleBricks, the current Good-sounds Dataverse re-release, and URMP.
They add 63 conservative metadata-level groups, bringing the audit-candidate
pool to 11 providers and 1,930 groups. Whole-provider arithmetic can now fill
four 39-group partitions, two provider slots per partition, a final
music/speech/natural minimum, and eight music groups per partition. Scientific
eligibility remains false: qualified and allocated counts are zero, only two
speech and two natural providers exist, AlbumDB is the only mastered-music
provider and represents one album, three-domain breadth in every partition is
infeasible, and the 120-group sensitivity is infeasible. No source or metric
successor was selected and no audio authority was broadened.

A current official-record
[`ViSQOL-only successor-readiness disposition`](perceptual-degradation-visqol-only-successor-readiness-20260814.md)
now establishes that a simpler score-blind full-reference successor can be
preregistered responsibly, but does not select it or authorize execution. The
frozen v3.3.3 model already has zero-delta synthetic replay across two distinct
build environments. That is technical readiness only: official guidance says
audio mode downmixes to mono, single scores require treatment aggregation,
domain-specific training needs subjective scores, and behavior can be poor
below the 24 kbps training floor or outside codec/VoIP degradations. Raw
MOS-LQO and similarity outputs therefore remain supporting features, not
audibility, materiality, severity, or artifact truth. A selected successor
would require a new committed plan and schema, controlled human calibration,
explicit stereo and domain abstention, and preserved grouped negatives before
any retained or human metric outcome is opened. The current two-family gate,
source authority, no-reference gate, and public verdict remain closed.

A further collection-level
[`breadth-repair provider screen`](perceptual-degradation-breadth-repair-provider-screen-20260814.md)
now separates immutable or stable candidates from preservation-required public
records. English children speech, GESMA and DataSTORRE add stable speech and
natural-sound capacity; ICSI adds the fourth speech provider only
provisionally; and three CC BY Bandcamp releases add mastered-release capacity
only as mutable, origin-unaudited records. The full public-record ceiling can
arithmetically place music, speech and natural sound in every partition and
mastered music in every partition, but the stable-only pool cannot. At this
checkpoint the 120-group sensitivity flipped from feasible at DataSTORRE's
67-recording ceiling to infeasible at an eight-group relationship floor.
Qualified and allocated counts remained zero. No source or metric successor
was selected, no audio or member was opened, and no scientific gate or public
verdict changed.

A bounded successor
[`stable music-provider screen`](perceptual-degradation-stable-music-provider-screen-20260814.md)
adds Vienna 4x22 and ROD as stable CC BY controlled-performance candidates:
two providers and 24 metadata-level groups. Neither is mastered-release
evidence. Spheres and FreiDi remain outside the narrow path under CC BY-SA;
KRAISLER has additional restrictions conflicting with its plain CC BY field;
and MoisesDB's audio is CC BY-NC-SA even though its paper is CC BY. No stable
mastered-release replacement was found. The 24 added groups do repair the
full public-record 120-group arithmetic even at DataSTORRE's conservative
floor, but only with the unpreserved ICSI and Bandcamp records. Stable records
alone still fail 120 groups, three-domain coverage and mastered-music coverage
in every partition. Qualified and allocated counts remain zero, and no audio,
successor, metric, scientific gate or public verdict changed.

A bounded
[`stable speech-provider screen`](perceptual-degradation-stable-speech-provider-screen-20260814.md)
adds VibraVox as a content-addressed CC BY 4.0 direct-speech candidate: 188
participant-level groups using only the clean dry headset-microphone field.
Body-conduction channels and noisy or speechless subsets remain excluded. The
stable pool now has 17 providers and 2,238 candidate groups at DataSTORRE's
recording ceiling, or 2,179 at its conservative floor. Stable-only arithmetic
can now place music, speech and natural sound in every provider-pure partition
and can fill four 120-group partitions even at the conservative floor, without
depending on mutable ICSI or Bandcamp records. Stable mastered-music coverage
still fails because AlbumDB remains the only stable mastered-release candidate.
Qualified and allocated counts remain zero. No repository data object, Parquet
content, audio, successor, metric, scientific gate or public verdict changed.

A bounded
[`stable mastered-music provider screen`](perceptual-degradation-stable-mastered-music-provider-screen-20260814.md)
adds three immutable CC BY 4.0 release candidates: 16 Solar Flux WAV tracks,
19 exposed WAV performances from the historically released Lotte Lehmann
farewell-recital album, and 12 Remnant Tamil Worship composition groups after
collapsing 115 language, version and render WAV objects. Together with AlbumDB,
the stable pool can now place at least eight mastered-music groups in every
provider-pure partition. The pool rises to 20 providers and 2,285 candidate
groups at DataSTORRE's recording ceiling, or 2,226 at its conservative floor;
the broader public pool reaches 24 providers and 2,375 or 2,316 groups. ICSI
and Bandcamp are no longer needed for any currently modelled arithmetic
repair. Production, generation, mastering, rights-origin, file-integrity and
relationship audits remain incomplete; qualified and allocated counts remain
zero. No archive, audio, successor, metric, scientific gate or public verdict
changed.

A refreshed evidence-bound
[`objective completion audit`](perceptual-degradation-objective-completion-audit-refresh-20260814.md)
now reconciles the full contract with the repaired stable-source arithmetic and
the ViSQOL-only successor disposition. Source breadth is no longer
arithmetically blocked: every currently modelled stable provider-pure scenario
passes, including the conservative 120-group and mastered-music constraints.
That capacity is not promoted to a truth-bearing manifest; exact members,
provenance, relationships, selection and allocation remain unfrozen, with zero
qualified or allocated groups. ViSQOL-only remains technically preregisterable
but unselected and without an execution gate. The objective therefore remains
at four of fourteen satisfied requirements. No audio, score, metric, human
response, sealed evidence or no-reference training was opened, and the public
CLI remains verdict-free.

A bounded
[`ViSQOL dependency and SBOM disposition`](perceptual-degradation-visqol-dependency-sbom-disposition-20260814.md)
now screens the pinned production target without selecting or rebuilding it.
ViSQOL, Abseil, TensorFlow Lite and Armadillo expose Apache-2.0 records;
protobuf and LIBSVM expose BSD-3-Clause records; and PFFFT carries permissive
UCAR/NCAR redistribution terms. The direct license screen passes, but the
complete gate remains closed: the two historical builds retained only a
46-name Bazel repository projection, not an exact production-only transitive
closure, linkage inventory, binary-bound CycloneDX SBOM or complete notice
bundle. The binaries were not retained and their hashes differ despite
zero-delta synthetic scores. ViSQOL-only therefore remains preregisterable but
unselected, execution-closed and redistribution-unready. No repository archive,
test audio, model, binary, metric, score or retained audio was opened.

A deterministic score-blind
[`listening operational resource frontier`](perceptual-degradation-listening-operational-resource-frontier-20260814.md)
now replays the actual v2 allocator against 120 symbolic source groups. The raw
power minimum at the protocol caps is 227 eligible or 352 enrolled session
slots per aggregate stratum, device class and partition—1,408 enrolled slots
across four partitions. Rounding to complete 120-slot trial-exposure cycles
raises that sensitivity to 240 eligible, 372 enrolled and 1,488 across four
partitions. Cycle rounding equalizes trial exposure but does not repair the
allocator's repeated candidate-position imbalance: no modelled option passes
the frozen balance audit, and missingness balance remains unproven. No option,
listener count, allocation policy or operational design is selected. The next
score-blind prerequisite is an allocator successor; no audio, response,
recruitment, collection, metric, score, source member, no-reference training or
public verdict was opened.

A deterministic score-blind
[`v3 allocation successor audit`](perceptual-degradation-listening-allocation-v3-symbolic-audit-20260814.md)
now repairs the v2 scheduling defect without selecting an operational policy.
The new construction treats each method as a seeded infinite trial-slot
sequence, rotates trial order by complete exposure cycle, and rotates candidates
by each trial's exposure ordinal. This proves trial-exposure, within-block
trial-position and candidate-position ranges no greater than one at every
contiguous post-eligibility prefix for the divisible grid. All 2,040
option-prefix cases through the four former cycle-rounded boundaries pass,
including the raw power minimums; a non-120, five-candidate test also passes.
Cycle rounding is therefore no longer needed solely for schedule balance,
returning the protocol-cap sensitivity to 352 enrolled slots per aggregate
stratum, device class and partition, or 1,408 across four partitions.
Post-assignment missingness and exclusion balance, append-only concurrent
allocation state,
restart recovery, session timing and the total number of condition strata
remain unresolved. No allocator policy, listener count or study design is
selected, and no audio, response, recruitment, collection, metric, score,
source member, no-reference training or public verdict was opened.

A deterministic score-blind
[`missingness stress`](perceptual-degradation-listening-missingness-stress-20260814.md)
now separates v3 issued-schedule balance from retained-response support. All
complete and contiguous 90% prefixes preserve the v3 range-at-most-one
invariants, but none of 2,048 whole-session or trial-level MCAR replicates does.
The first three workload options retain the eight-judgment source floor in all
MCAR replays; at the 15 + 6 minimum it survives only 200/256 session-loss and
40/256 trial-loss replays. A score-blind exposure-phase mask creates candidate-
position ranges up to three, while source-correlated 10% loss leaves 108 of 120
source groups and twelve groups with zero judgments. This does not prove MCAR
bias or automatically reject an unequal hierarchical design; it proves that a
scalar 90% usable-rate assumption cannot establish retained balance, source
support or power. No imputation, weighting, replacement assignment, exclusion
rule, allocator policy, listener count or study design is selected, and no
audio, response, identity, recruitment, collection, metric, score, source
member, no-reference training or public verdict was opened.

A deterministic score-blind
[`retained-design robustness frontier`](perceptual-degradation-listening-retained-design-robustness-20260814.md)
now separates finite reserve capacity from structured source support. Across
30,720 MCAR retained designs, every workload has a bounded issued-reserve
option that passes the frozen planning-power, eight-judgment source-support and
candidate-position-connectivity gates in at least 244 of 256 replays. At the
existing 90% retention sensitivity, the 3 + 3, 5 + 5 and 8 + 6 options require
10% reserve, while the compact 15 + 6 option requires 20%; at 85% retention,
the joint session/trial sensitivities rise to 20%, 20%, 20% and 40%. The latter
corresponds to 493 planning enrolled slots per aggregate condition stratum,
device class and partition, or 1,972 across four partitions. Complete-source
loss is not repaired by reserve: removing 6, 12 or 24 symbolic groups gives the
missing groups zero support and removes their planned position contrasts, even
when added judgments on the retained groups raise aggregate power above 0.80.
Provider/domain/partition breadth remains unevaluated without exact frozen
members. These are analytic sensitivities, not an empirical missingness model
or listening evidence. No reserve, workload, listener count, missingness or
exclusion policy, operational design, recruitment, collection, source member,
metric, no-reference training or public verdict is selected or authorized.

A synthetic
[`allocation-journal candidate audit`](perceptual-degradation-listening-allocation-journal-audit-20260814.md)
now closes the narrow technical gap between v3's contiguous-index assumption
and a single-database reservation mechanism. Sixteen multi-connection trials
issued 9,216 calls across 32 streams: exactly 3,072 unique reservations and
6,144 idempotent retries produced contiguous `0..95` indices in every stream.
Four logical fault points across 96 requests recovered exactly once, including
commit-before-reply loss; immutable stream/reservation triggers blocked all
updates and deletes; three forced tamper cases were detected; and a 192-index
v3 integration retained exposure, block-position and candidate-position ranges
no greater than one at every prefix. The candidate uses SQLite WAL,
`synchronous=FULL`, `BEGIN IMMEDIATE`, immutable SHA-256-bound stream
configuration and an insert-only event hash chain. This is synthetic evidence
for one database under threaded multi-connection contention, not proof of
real eligibility, process-kill or power-loss durability, multi-host deployment,
privacy/backup ownership, response atomicity, missingness or exclusion policy.
No operational policy, response store, listener count, recruitment, collection,
source member, metric, no-reference training or public verdict is selected or
authorized, and no audio, identity, response, outcome, score or sealed evidence
was accessed.

A deterministic score-blind
[`condition-strata workload sensitivity`](perceptual-degradation-listening-condition-strata-workload-20260814.md)
now quantifies how condition-specific claims multiply the retained-design
resource frontier. The frozen technical inventory supports an arithmetic
candidate grid of four codecs, two encoders per codec and two matched
within-family quality levels per encoder: sixteen codec recipes, plus either
six existing control families or twelve individual control recipes. At 90%
retention across four partitions and one declared device class, the arithmetic
minimum across unselected workload options is 27,048 enrolled session slots for
dedicated execution of the codec grid, 37,192 with control families and 47,332
with all control recipes. Optimistic multi-condition MUSHRA packing reduces
those figures to 16,688, 22,944 and 29,204, but no allocator, player, timing,
fatigue, covariance, reuse or retained-balance evidence supports that packing.
Session slots are not unique people. The recipes and controls remain technical
metadata, not selected listening conditions or perceptual truth; artifact
isolates and hard negatives remain incomplete. No condition, option, partition,
device policy, listener count, source member, recruitment, collection, audio,
metric, score, no-reference training or public verdict was selected, opened or
authorized.

A deterministic score-blind
[`negative/control topology audit`](perceptual-degradation-negative-control-topology-20260814.md)
now accounts for all twenty required negative classes exactly once while
separating transparent truth, source traits, alignment nuisances and
human-truth production controls. It corrects the earlier condition-breadth
composition: the 22- and 28-strata sensitivities omitted the contract's dither
and sample-rate-conversion classes and therefore were not claim-complete. At
90% retention across four partitions and one declared device class, sixteen
codec recipes plus the five required production families require an arithmetic
minimum of 35,500 dedicated or 21,904 optimistically packed enrolled session
slots. Retaining production clipping and the two generation families raises
that to 40,572 or 25,028; retaining all eight generation recipes raises it to
50,716 or 31,284. If all seven alignment nuisances require distinct human-truth
conditions, the family/recipe sensitivities rise as high as 62,548 dedicated or
38,584 optimistically packed slots. These are session slots, not people, and
the packing remains unproven. Eighteen classes have a candidate record or
technical representation, but quiet and naturally clipped references have no
explicit candidates; sparse and tonal share one candidate; dither is confounded
with 12-bit requantization; sample-rate conversion lacks a perceptual replay;
and bounded-drift plus paired leading/trailing-silence plumbing is incomplete.
No exact source trait, condition, human truth, scientific coverage, listening
design, recruitment, collection, metric, score, no-reference work or public
verdict was selected, opened or authorized.

A deterministic score-blind
[`negative-control technical repair`](perceptual-degradation-negative-control-technical-repair-20260814.md)
now closes four named synthetic plumbing gaps. An isolated signed-16 TPDF
candidate adds only `-1`, `0` or `+1` LSB without changing bit depth; an exact
FFmpeg 9.0-bound 48 -> 32 -> 48 kHz roundtrip preserves final geometry while
changing PCM; a train/held-out drift decision recovers and applies `+75` and
`-60` ppm corrections while leaving zero drift untouched; and paired exact-zero
edge fixtures support 0.4 + 0.6 seconds of silence while preserving an
`excessive_trim` abstention at 1.2 + 1.2 seconds. Two fresh temporary replays
were byte-identical. The new FFmpeg SHA-256 is bound explicitly because the
historical 8.1.2_1 binary has been replaced locally by 9.0; the historical tool
binding was not silently reused. The synthetic drift interpolator is not the
frozen oracle resampler, no production resampler is selected, and no retained
audio correction or perceptual effect is validated. No actual audio, source,
condition, metric, score, human response, collection, no-reference work or
public verdict was selected, opened or authorized.

A deterministic score-blind
[`source-trait identifiability contract`](perceptual-degradation-source-trait-identifiability-20260814.md)
now freezes proof obligations for all seven required natural/source-trait
negative classes without reading or selecting audio. Four constructive
witnesses pair distinct latent histories with byte-identical PCM: natural
bandwidth versus generated low-pass, preserved quiet level versus later
attenuation, synthetic versus captured noise, and source clipping versus an
intentional flat-top waveform. Three further fixtures show that sparse and
tonal can overlap while independent sparse-non-tonal and tonal-non-sparse
contrasts are structurally possible. Two fresh temporary replays were
byte-identical. The result forbids PCM descriptors from substituting for
provenance, preserves TinySOL's sparse/tonal confound, and leaves the missing
quiet and naturally clipped candidates explicit. No exact member, source
trait, condition, perceptual truth, metric, response, collection,
no-reference work or public verdict was selected, opened or authorized.

A deterministic score-blind
[`oracle drift-resampler freeze`](perceptual-degradation-oracle-drift-resampler-20260814.md)
now closes the technical resampling choice left open by the bounded-drift
decision fixture. The selected candidate uses a hash-bound 128-tap,
2,048-phase, signed-Q30 Kaiser-sinc table, a shared stereo position grid,
mandatory 64-frame edge discard and a bit-exact zero-drift bypass. All nine
predeclared gates passed across `+75`, `-60`, `+100`, `-100` and zero ppm:
worst channel correlation was 0.9999999906, gain error stayed below 0.000031
dB, sample error stayed below 0.000164, passband ripple was 0.000267 dB,
stopband magnitude from 0.99 Nyquist was at most -60.11 dB, and zero-channel
leakage was exactly zero. The drifted observations came from an independent
analytic source-time generator rather than the candidate resampler. Two fresh
temporary replays were byte-identical. This selects only the frozen technical
resampler; integration after the held-out apply decision and retained-audio
validation remain separately gated. No retained audio, perceptual metric,
human truth, response, collection, no-reference work or public verdict was
opened or authorized.

A bounded score-blind
[`source-trait provider-capability screen`](perceptual-degradation-source-trait-provider-capability-screen-20260814.md)
now narrows the two missing natural/source-trait negative routes without
reading audio or exact-member records. SONYC's CC BY 4.0 collection and primary
system paper document a common calibrated capture chain, fixed gain context,
32--120 dBA dynamic range and lossless FLAC upload, making it a plausible later
route for a preserved-level quiet member. Absolute PCM level, activity and
absence of post-capture attenuation remain unobserved, so no quiet candidate
or trait is assigned. Freesound's official API exposes text, file-type and
item-licence search plus original-format download, but its provider schema does
not establish capture-chain clipping or exclude intentional flat-top
waveforms; no catalogue query was executed and no naturally clipped candidate
was found. The search is bounded and does not prove global absence. No exact
member, source-trait manifest, source or metric successor, audio, human truth,
response, collection, no-reference work or public verdict was selected,
opened or authorized.

A deterministic score-blind
[`objective completion-audit source-trait and drift refresh`](perceptual-degradation-objective-completion-audit-source-trait-drift-refresh-20260814.md)
now reconciles those later checkpoints against all fourteen requirements. The
completion count remains four satisfied and ten unproven. Provider-pure source
arithmetic is feasible, but the seven-trait proof contract has only five
candidate records: quiet has a provider-level route rather than an exact
candidate, naturally clipped still has no candidate, and exact selection and
allocation remain unfrozen. The bounded-drift resampler passed all nine
synthetic gates and is the selected technical algorithm, but it is not
integrated after a held-out apply decision or validated on retained development
pairs. The historical fixed 44.1-to-48 kHz metric-rate view is explicitly not
treated as drift integration. Two fresh report generations were byte-identical.
No audio, exact member, source or metric successor, correction integration,
human truth, score, metric, collection, no-reference training, final
recommendation or public verdict was opened, selected or authorized.

A deterministic score-blind
[`listening privacy-readiness audit`](perceptual-degradation-listening-privacy-readiness-20260814.md)
now distinguishes the minimized response surface from operational privacy
readiness. The current closed-world schema has 39 field names and no direct
identity, contact, payment, raw-IP, precise-location, microphone-recording or
device-serial field; the local qualification player also has no network,
cookie, persistence or microphone API. Its participant code repeats across
sessions and responses, however, so the data are pseudonymous rather than
de-identified as the historical schema title claims. Consent versioning and
the time-bounded withdrawal link must live in separate successor records, and
ten operational fields covering responsibility, jurisdiction, storage,
access, incident response, retention, deletion, withdrawal, compensation,
publication thresholds and version hashes remain unset. Two fresh report
generations were byte-identical. No operational value, participant contact,
recruitment, consent, response storage, collection, response, no-reference work
or public verdict was selected, opened or authorized.

The deterministic score-blind
[`oracle drift integration`](perceptual-degradation-oracle-drift-integration-20260814.md)
now binds the frozen held-out apply decisions to the exact frozen resampler and
the score-free oracle envelope on three synthetic stereo cases. All twelve
integration gates passed. The `+75` and `-60 ppm` cases improved every channel
by at least 0.1046 correlation and ended with supported post-correction
alignment; zero drift remained bit-exact. Applied cores discard the required
64 frames at each edge. Two fresh temporary payloads were byte-identical. The
oracle records remain execution-blocked with null severity and audibility, and
both metric families remain not authorized. No actual, retained or provider
audio, real-audio drift validation, perceptual metric, human truth, response,
collection, no-reference work or public verdict was opened or authorized.

A deterministic
[`objective completion-audit drift-integration refresh`](perceptual-degradation-objective-completion-audit-drift-integration-refresh-20260814.md)
records that synthetic correction plumbing is now integrated while refusing
to promote it to retained-audio or scientific validation. The completion count
remains four satisfied and ten unproven. The full-reference requirement is now
`synthetic_drift_integration_passed_retained_and_scientific_validation_closed`:
real drift estimation, retained development-pair behavior, perceptual metrics
and human calibration remain absent. Source-trait, metric-successor and
retained-validation decisions remain separately authority-gated; no source or
condition was selected and the public CLI remains verdict-free.

A deterministic score-blind
[`oracle drift-estimator integration`](perceptual-degradation-oracle-drift-estimator-integration-20260814.md)
now closes the synthetic path from PCM-based estimation through the held-out
apply decision, exact frozen resampler, alignment v2 and score-free oracle. All
seven frozen drift values were selected using training windows only. Disjoint
held-out windows permitted correction for `+75`, `-60`, `+100` and `-100 ppm`;
every applied channel reached at least 0.999 correlation and improved by at
least 0.1. The `+20` and `-20 ppm` cases stayed below the benefit threshold and
remained bit-exact passthroughs; zero drift used the bit-exact identity bypass.
All thirteen gates passed and two fresh temporary payloads were byte-identical.
No actual, retained or provider audio, perceptual metric, human truth, response,
collection, no-reference work or public verdict was opened or authorized.

A deterministic
[`objective completion-audit drift-estimator refresh`](perceptual-degradation-objective-completion-audit-drift-estimator-refresh-20260814.md)
records the end-to-end synthetic estimator and correction result without
scientific promotion. The completion count remains four satisfied and ten
unproven. The full-reference requirement is now
`synthetic_estimator_apply_correction_pipeline_passed_retained_and_scientific_validation_closed`:
retained development-pair behavior, real-audio estimation, perceptual metrics
and human calibration remain absent. Source-trait, metric-successor and
retained-validation decisions remain separately authority-gated, and the
public CLI remains verdict-free.

A score-blind
[`ODAQ retained-reference drift-validation readiness`](perceptual-degradation-odaq-retained-drift-validation-readiness-20260814.md)
checkpoint now freezes the next real-content technical protocol without
opening retained audio or implementing a live runner. The future design covers
112 cases across the exact 16 acquired clean references, uses five fixed
training and five disjoint held-out windows, abstains on insufficient
reference-energy support, and predeclares estimator accuracy, correction
benefit, bit-exact bypass, two-replay determinism and public-redaction gates.
All nine metadata-only readiness gates pass. A narrow successor-authorization
schema permits only temporary in-memory canonical projection and controlled
clock-drift validation; ODAQ processed conditions and scores, actual codec
generation, metrics, playback, ratings, responses, no-reference work and
public verdicts remain closed.

A deterministic
[`objective completion-audit retained-drift readiness refresh`](perceptual-degradation-objective-completion-audit-retained-drift-readiness-refresh-20260814.md)
records that protocol readiness without treating it as authorization or
validation. The completion count remains four satisfied and ten unproven. The
full-reference requirement is now
`retained_drift_validation_protocol_frozen_authorization_and_execution_pending`.
No retained reference was read or projected, no live runner was implemented,
and no real-content, perceptual or human validation occurred. The public CLI
remains verdict-free.

The bounded
[`exact-member source-trait confirmation`](perceptual-degradation-source-trait-exact-member-confirmation-20260818.md)
acquired only the two metadata-qualified CC0 provider originals and replayed
the frozen score-free integer-PCM descriptors twice with byte-identical private
reports. The quiet member measured `-51.622035 dBFS` RMS with nonzero activity
across all 346 one-second blocks. The naturally clipped candidate produced 66
exact-rail samples, seven repeated high-level plateau runs and 66 near-flat
high-level windows. No derived PCM was retained. An independent audit confirms
the public projection is exact, path-free and hash-redacted. The observations
do not assign source traits, establish perceptual truth, freeze a source
manifest or enable a verdict.

A deterministic
[`objective completion-audit exact-member refresh`](perceptual-degradation-objective-completion-audit-exact-member-confirmation-refresh-20260818.md)
reconciles that result without scientific promotion. Completion remains four
of fourteen. Quiet and clipped descriptor obligations are observed, but no
quiet classification or trait assignment was authorized, sparse and tonal
remain non-independent, and relationships and partition allocation remain
unfrozen. The retained ODAQ 16-of-17-gate technical negative is unchanged; no
codec, perceptual metric, listener response, sealed evidence, no-reference
training, final-validation claim or public verdict was opened or produced.

A deterministic metadata-only
[`source-trait adjudication and relationship audit`](perceptual-degradation-source-trait-adjudication-relationship-20260818.md)
now closes the next policy gate without reading another audio sample. The
observed quiet descriptor cannot receive a numeric cutoff selected after the
value was seen. The naturally clipped candidate has pre-access provenance and
a predeclared technical support event, making it ready only for a separately
authorized assignment gate; partition support remains absent. TinySOL exposes
2,273 eligible exact-member candidates inside one conservative partition
group, but metadata alone establishes neither a sparse non-tonal member nor a
tonal non-sparse member. Sparse and tonal descriptor rules, thresholds,
non-overlap constraints and bounded member selection must be frozen before any
candidate audio is read. No exact member was selected, trait assigned, manifest
frozen or partition allocated.

The deterministic
[`objective completion-audit adjudication and relationship refresh`](perceptual-degradation-objective-completion-audit-adjudication-relationship-refresh-20260818.md)
reconciles that policy checkpoint. Completion remains four of fourteen. The
retained ODAQ technical negative is unchanged, the public CLI remains
verdict-free, and no new audio, codec, perceptual metric, listener response,
sealed evidence, no-reference training or validation claim was opened or
produced.

A score-blind
[`sparse/tonal descriptor freeze`](perceptual-degradation-source-trait-sparse-tonal-descriptor-20260818.md)
now preregisters conservative time-occupancy, spectral-concentration,
abstention and non-overlap rules before candidate access. The existing
sparse-tonal overlap, sparse non-tonal and tonal non-sparse synthetic fixtures
all pass their structural gates. These synthetic cases are not source evidence:
no exact member was selected or read and no trait was assigned. TinySOL may
supply the tonal non-sparse side, but its pitched-note metadata does not
establish a sparse non-tonal contrast; that provider route remains the next
metadata-only source gate.

The deterministic
[`objective completion-audit sparse/tonal refresh`](perceptual-degradation-objective-completion-audit-sparse-tonal-descriptor-refresh-20260818.md)
reconciles the descriptor freeze without scientific promotion. Completion
remains four of fourteen, the retained ODAQ technical negative is unchanged,
and manifest allocation, human truth, metrics, no-reference work and public
verdicts remain closed.

A bounded metadata-only
[`sparse/tonal exact-member selection`](perceptual-degradation-source-trait-sparse-tonal-exact-member-selection-20260818.md)
now nominates two exact candidates without reading audio. Freesound 856645 is
a CC0 direct-to-REAPER, unprocessed studio finger snap for the sparse non-tonal
contrast. A deterministic fixed-seed selection over eleven eligible natural
TinySOL oboe rows chose the ordinary mezzo-forte D-sharp-4 member for the tonal
non-sparse contrast. The private TinySOL metadata replay reproduced the
selection. Both remain candidates pending two frozen descriptor replays; no
trait, source manifest, partition, perceptual truth or verdict was assigned.

The bounded
[`sparse/tonal exact-member confirmation plan`](perceptual-degradation-source-trait-sparse-tonal-exact-member-confirmation-plan-20260818.md)
now freezes the only permitted audio-access successor before either selected
member is opened. The future one-worker runner accepts only the exact Freesound
856645 original and exact selected TinySOL oboe archive member, measures every
channel twice under the already-frozen descriptor, retains no derived PCM, and
publishes no private path or encoded/PCM hash. Abstention or class mismatch is
predeclared as a negative result without threshold changes, substitution, trait
assignment or manifest allocation. The runner has so far been exercised only on
synthetic integer-PCM fixtures; no candidate audio has been opened.

The bounded
[`sparse/tonal exact-member confirmation`](perceptual-degradation-source-trait-sparse-tonal-exact-member-confirmation-20260819.md)
has now run the two frozen exact members twice. The private reports are
byte-identical and no derived PCM was retained. The TinySOL oboe passed the
tonal non-sparse descriptor. The Freesound finger snap abstained: it occupied
three time blocks rather than the frozen maximum of two and met the tonal rather
than non-tonal spectral rule. The candidate was not replaced and no threshold
changed. An independent audit confirms the public result is exact, path-free
and hash-redacted. No trait or manifest allocation was promoted.

The deterministic
[`objective completion-audit sparse/tonal confirmation refresh`](perceptual-degradation-objective-completion-audit-sparse-tonal-confirmation-refresh-20260819.md)
reconciles that rigorous negative. Completion remains four of fourteen, the
independent sparse/tonal pair remains missing, and the retained ODAQ technical
negative is unchanged. The next bounded source gate is a new metadata-only
sparse non-tonal successor checkpoint. Codec generation, perceptual metrics,
listening responses, sealed evidence, no-reference work, validation claims and
public verdicts remain closed.

A new metadata-only
[`sparse non-tonal successor audit`](perceptual-degradation-source-trait-sparse-non-tonal-successor-metadata-audit-20260819.md)
examined five exact CC0 Freesound records after the snap abstention. All were
rejected before audio access: disclosed normalization/fades, an uncertain
per-channel capture chain, absent or ambiguous transformation history, or
designed-impact intent prevented eligibility. No preview, download, descriptor,
replacement, trait assignment or manifest allocation occurred. The next gate
remains an exact-member metadata search under the same frozen prerequisites.

A separately frozen
[`sparse non-tonal metadata search v2`](perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v2-plan-20260819.md)
now bounds that next gate before new discovery. It permits eight declared
discovery queries and at most twenty primary Freesound or Zenodo exact-record
inspections, stops at the first fully eligible member, excludes all six
consumed exact members, and treats discovery snippets as non-evidence. Only
text or JSON metadata may be retrieved; candidate audio, preview players,
waveform assets, downloads and descriptor execution remain closed. No new
candidate has yet been inspected or nominated under this checkpoint.

The bounded
[`sparse non-tonal metadata search v2 result`](perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v2-20260819.md)
executed four of the eight declared queries and inspected nine exact Freesound
records as text-only primary HTML. It stopped at sound 703342: a CC0,
11.802-second provider WAV described as 192 kHz, 32-bit-float stereo, one
unprocessed 9 mm round captured with dual Shure SM58 microphones into a Zoom
F3 and explicitly not assembled sound design. The first eight records were
rejected under the unchanged prerequisites. No candidate page was rendered and
no audio, preview, waveform or referenced media asset was requested. The
result nominates one exact member for technical confirmation only.

The one-member
[`sparse non-tonal exact-member confirmation v2`](perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v2-plan-20260819.md)
is now frozen before that provider original is downloaded. Its one-worker
runner accepts only the expected 192 kHz stereo 32-bit-float WAV, supports both
direct and extensible IEEE-float containers, rejects non-finite samples and
unexpected geometry, performs two private replays, retains no derived PCM, and
publishes no channel measurements, hashes or private paths. Focused synthetic
parser, descriptor, replay and redaction tests pass. Abstention or mismatch is
predeclared without substitution or threshold change; audio remains unopened.

The deterministic
[`objective completion-audit sparse-successor metadata refresh`](perceptual-degradation-objective-completion-audit-sparse-successor-metadata-refresh-20260819.md)
records those rejections without treating them as source evidence. Completion
remains four of fourteen, the independent sparse/tonal pair remains missing,
and the retained ODAQ technical negative is unchanged. The public CLI remains
verdict-free.

The deterministic
[`objective completion-audit sparse-successor nomination refresh`](perceptual-degradation-objective-completion-audit-sparse-successor-nomination-refresh-20260819.md)
reconciles the metadata nomination and frozen confirmation checkpoint without
scientific promotion. Completion remains four of fourteen. The sparse member
is unmeasured, both contrasts remain unassigned and unallocated, the source
manifest remains unfrozen, the retained ODAQ technical negative is unchanged,
and the public CLI remains verdict-free.

The frozen
[`sparse non-tonal exact-member confirmation v2`](perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v2-20260819.md)
acquired only the exact Freesound 703342 provider-original WAV through the
official authenticated route. Its stereo 192 kHz 32-bit-float container matched
the precommitted boundary and two private descriptor reports were byte-identical,
but the candidate returned a class mismatch under the unchanged sparse
non-tonal descriptor. No playback occurred, no derived PCM was retained, the
candidate was not replaced and no threshold changed. An independent audit
confirmed the exact path-, measurement- and audio-hash-redacted public result.

The deterministic
[`objective completion-audit sparse-successor confirmation v2 refresh`](perceptual-degradation-objective-completion-audit-sparse-successor-confirmation-v2-refresh-20260819.md)
preserves that rigorous negative without promotion. Completion remains four of
fourteen. Two exact sparse non-tonal candidates have now failed the frozen
descriptor, so the independent sparse/tonal pair, source-trait assignments,
relationships and manifest allocation remain missing. The retained ODAQ
technical negative is unchanged, and codecs, perceptual metrics, listening,
sealed evidence, no-reference work and the public verdict remain closed. The
next source gate is a separately frozen metadata-only successor search.

The separately bounded
[`sparse non-tonal metadata search v3`](perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v3-plan-20260819.md)
is now frozen before query execution. It excludes all fifteen exact Freesound
members consumed by earlier checkpoints and preserves both failed sparse
candidates. Eight declared discovery queries and at most twenty exact primary
records may be inspected as text or JSON only. The unchanged descriptor and all
audio, preview, waveform, download, playback, trait-assignment, manifest and
public-verdict surfaces remain closed. The narrower metadata proxy requires one
broadband natural transient with recording context in a five-to-sixty-second
provider-original WAV; it is not descriptor or perceptual evidence.

The bounded
[`sparse non-tonal metadata search v3 result`](perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v3-20260819.md)
executed all eight declared queries and stopped at Freesound sound 476736. The
candidate is a 26.745-second CC0 stereo 48 kHz 24-bit WAV described as one
unprocessed thunder clap with light-rain context, captured through a Zoom H6 XY
capsule. Eleven distinct primary records were attempted; five yielded text-only
HTML and six timed out without evidence. A single same-query transport retry is
recorded and did not expand scope. No audio, preview, waveform or media asset was
requested, and timeout rows carry no discovery-snippet inference.

The one-member
[`sparse non-tonal exact-member confirmation v3`](perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-plan-20260819.md)
is frozen before that original is acquired. Its one-worker runner accepts only
the expected stereo 48 kHz signed 24-bit integer PCM WAV, performs two private
replays, retains no derived PCM and redacts channel measurements, hashes and
paths from the public result. Abstention or mismatch is predeclared without
substitution or threshold change; audio remains unopened.

The deterministic
[`objective completion-audit sparse-successor v3 nomination refresh`](perceptual-degradation-objective-completion-audit-sparse-successor-v3-nomination-refresh-20260819.md)
keeps completion at four of fourteen. The new candidate is unmeasured, the
independent sparse/tonal pair remains missing, source traits and relationships
remain unassigned, no manifest is allocated, the retained ODAQ technical
negative is unchanged and the public CLI remains verdict-free.

The frozen
[`sparse non-tonal exact-member confirmation v3`](perceptual-degradation-source-trait-sparse-non-tonal-exact-member-confirmation-v3-20260819.md)
acquired only the exact Freesound 476736 provider-original WAV through the
official authenticated route. Its stereo 48 kHz signed 24-bit integer-PCM
container matched the precommitted boundary and two private descriptor reports
were byte-identical, but the candidate abstained under the unchanged sparse
non-tonal descriptor. No playback occurred, no derived PCM was retained, the
candidate was not replaced and no threshold changed. An independent audit
confirmed the exact path-, measurement- and audio-hash-redacted public result.

The deterministic
[`objective completion-audit sparse-successor confirmation v3 refresh`](perceptual-degradation-objective-completion-audit-sparse-successor-confirmation-v3-refresh-20260819.md)
preserves that rigorous negative without promotion. Completion remains four of
fourteen. Three exact sparse non-tonal candidates have now failed the frozen
descriptor, so the independent sparse/tonal pair, source-trait assignments,
relationships and manifest allocation remain missing. The retained ODAQ
technical negative is unchanged, and codecs, perceptual metrics, listening,
sealed evidence, no-reference work and the public verdict remain closed. The
next source gate is a separately frozen metadata-only v4 search for a cleanly
isolated broadband one-shot with explicit quiet context and provenance.

That
[`sparse non-tonal metadata search v4`](perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v4-plan-20260819.md)
is now frozen before query execution. It excludes all twenty-six exact members
consumed by earlier checkpoints and permits eight declared discovery queries
and at most twenty distinct primary Freesound records. The unchanged descriptor
is not executed. The narrower metadata proxy requires one ten-to-sixty-second
provider-original lossless broadband physical one-shot with explicit quiet
context before and after the event, exact capture provenance, permissive rights
and no processing beyond a declared trim. All audio, preview, waveform,
playback, trait-assignment, manifest and public-verdict surfaces remain closed.

The bounded
[`sparse non-tonal metadata search v4 result`](perceptual-degradation-source-trait-sparse-non-tonal-metadata-search-v4-20260819.md)
executed all eight declared queries after exact-head CI passed and exhausted the
route without an eligible exact member. Three distinct primary Freesound pages
were inspected as text-only HTML. Two sub-five-second FLAC firecrackers lacked
capture, transformation and quiet-context evidence; a sub-second designed
gunshot disclosed fade, amplification and compression. No audio, preview,
waveform, media asset, page rendering, playback or descriptor was accessed.

The deterministic
[`objective completion-audit sparse metadata v4 negative refresh`](perceptual-degradation-objective-completion-audit-sparse-metadata-v4-negative-refresh-20260819.md)
preserves that bounded negative without promotion and keeps completion at four
of fourteen. Three exact sparse candidates have failed and the narrow metadata
route is exhausted, so repeating the same search is no longer justified. The
independent pair, assignments, relationships and manifest remain missing. The
next meaningful source decision is a separately authorized controlled-source
route or an objective-level rigorous negative; this checkpoint authorizes
neither, and the public CLI remains verdict-free.

A precise
[`sparse non-tonal clean-capture acquisition specification`](perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-acquisition-spec-20260819.md)
is now frozen for that materially different route. It requires one safe
balloon-pop or wooden-clapper event in a 15-30-second original 24-bit WAV, five
seconds of quiet context on both sides, complete per-channel capture logging,
permissive rights, exact identity and no processing. Metadata acceptance is
fail-closed and must precede a separately committed exact-member checkpoint.
The specification authorizes no outreach, payment, collection, preview,
download, audio access, trait assignment, manifest allocation or verdict.

The
[`clean-capture metadata intake gate`](perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-intake-20260819.md)
now operationalizes that specification without opening a live-delivery surface.
Its synthetic fixture passes eight ordered metadata gates, while focused tamper
tests reject processing, container, quiet-context, safety, rights, channel,
path, malformed-input, authority and binding failures. The public result is
aggregate-only and the implementation makes zero audio-file open attempts.
Without `--synthetic`, the command fails closed.

The deterministic
[`objective completion-audit clean-capture intake readiness refresh`](perceptual-degradation-objective-completion-audit-clean-capture-intake-readiness-20260819.md)
keeps completion at four of fourteen. Acquisition and intake readiness are not
a live delivery or source evidence. The three failed exact sparse candidates,
bounded metadata negative and retained ODAQ technical negative are unchanged;
the independent pair, assignments, relationships and manifest remain missing.
Further source progress requires explicit authority for one safe capture or a
decision to terminate source-manifest feasibility as a rigorous negative.

The user has now explicitly authorized one safe clean capture. The frozen
[`live clean-capture metadata-intake checkpoint`](perceptual-degradation-source-trait-sparse-non-tonal-clean-capture-live-intake-plan-20260819.md)
accepts exactly one private, external-to-Git JSON manifest through the unchanged
eight gates, requires two byte-identical private replays and exposes only an
independently audited aggregate projection. External outreach and spending
remain unauthorized. No live manifest, delivery, recording or audio has been
opened under this checkpoint.

The deterministic
[`objective completion-audit authority and live-intake refresh`](perceptual-degradation-objective-completion-audit-clean-capture-authority-live-intake-20260819.md)
keeps completion at four of fourteen. Authority and readiness are not source
evidence. The next gate is the exact physical microphone/preamp/event declaration
needed to freeze a capture-execution checkpoint; local device enumeration alone
cannot prove that chain. Trait assignment, relationship adjudication, allocation,
codec generation, perceptual metrics, listening, no-reference work and the public
verdict remain closed.

## Research restart and target semantics — 2026-09-05

The [strategic review](perceptual-degradation-strategic-review-20260905.md)
reassesses the central estimand, source-descriptor validity, active-duration
support, listening feasibility and metric shortlist. It is a proposal, not an
execution amendment or a new scientific disposition. Prior evidence, including
the history-detection negative and retained drift failure, remains unchanged.

A separate [target-semantics integration](perceptual-degradation-target-semantics-integration-20260905.md)
now connects the existing synthetic listening outputs to explicitly named
targets. Two complete replays are byte-identical. Correct-response probability
is distinct from audible-condition probability; the former is currently
conditional on zero listener/source random effects. Indeterminate evidence
remains null, and aggregate analysis groups cannot become per-source labels.
The legacy Brier/ECE/AUC thresholds are not transferred to a different target.

This resolves a software-interface ambiguity in the synthetic path and records
the remaining statistical design questions. It does not validate an oracle,
open observed data, change a frozen human threshold, select a new metric,
qualify a source or make no-reference work eligible. The full scientific
objective remains incomplete, and the existing one-capture authority persists.

## Paired-rating protocol successor — 2026-09-05

The [paired-rating successor](perceptual-degradation-paired-rating-protocol-20260905.md)
corrects the preparation path for subtle ratings: collect both concealed
candidate grades, resolve their roles from the assignment, and preserve the
signed condition-minus-hidden-reference difference separately from forced
choice. This is a new protocol and synthetic response processor; the old player,
schema, analysis and evidence are immutable and remain unsuitable for this
paired target without an explicit integration successor.

Two independent synthetic CLI replays are byte-identical. Five numerical
fixtures, each with 288 paired trials across 24 synthetic listeners and 12
sources, reach the crossed-effects solver with incorrect choices and positive
differences intact. In the symmetric-error fixture the signed estimate is zero;
correct-choice filtering gives -0.6 and nonpositive clipping gives -0.3.
These are counterfactual numerical demonstrations, not measured impairment.
Twenty-one focused tests cover role/order invariance, incomplete pairs, grade
entry and locking, assignment linkage, signed support and closed access.

The old -4 through 0 response range cannot represent all legitimate paired
differences, whose range is -4 through +4. No missing reference grade is assumed,
and no legacy record, material threshold, variance assumption or power result is
promoted to paired scientific evidence. Live UI/delivery, privacy/session
integration, paired-target power and uncertainty, source qualification, human
calibration and all original oracle/transfer gates remain outstanding. No
playback, audio access, listener collection or metric execution occurred.

## Silent paired-rating UI integration — 2026-09-05

The [silent UI successor](perceptual-degradation-paired-ui-20260905.md) now
connects a browser's locked choice and two explicitly entered grades to the
frozen paired-rating processor. The browser exposes no correctness feedback
or condition role. It has no audio, microphone, network-submission or response-
persistence API. All predecessor code and evidence remain unchanged.

Real-browser QA with arbitrary automation values verified field gating,
submission locking, fresh trial state and reload clearing. The two complete
browser records matched the declared fixtures and replayed to +0.6 and -0.6,
retaining both incorrect choices. A cleared-grade termination case exposed and
resolved a missingness detail: final field state must remain separate from
earlier valid events. Its missing grade and paired target now remain null.
Desktop and mobile-width layouts were inspected; the temporary browser and
loopback server were closed. Separate deterministic JavaScript/Python replays
are byte-identical, and unit checks cover both valid and invalid event streams.

This is interface and analysis-linkage evidence, not playback qualification,
participant privacy approval, perceptual data, statistical calibration or
oracle validation. Paired-target uncertainty, proper nonmateriality evidence,
population/source estimands and real-study delivery remain open. The authorized
clean capture still needs the physical equipment/setup declaration; no capture,
listening session, metric execution or no-reference training occurred.

## Nonmateriality evidence-state successor — 2026-09-05

The [nonmateriality successor](perceptual-degradation-nonmateriality-evidence-20260905.md)
now separates material support, nonmaterial support, unresolved intervals and
missing or inadequate support. An actual replay of the unchanged legacy
classifier on two generated boundary fixtures produces `transparent` and
`audible_nonmaterial` despite severity intervals crossing its material boundary.
The successor keeps both indeterminate, without editing any predecessor result.

The paired-rating processor is connected to the evidence-state adapter through
six synthetic numerical cases. Missing pairs reduce severity support explicitly;
the all-incorrect fixture's logistic nonconvergence is retained rather than
converted to a forecast. A 48-case bridge grid distinguishes genuinely opposed
method evidence from a missing or unresolved required method. Two independent
CLI replays are byte-identical. These are software observations, not perceptual
labels, statistical coverage, a new power result or an oracle pass.

Legacy numbers remain diagnostic coordinates, not selected paired scientific
thresholds. Nonmateriality is not transparency, aggregate fits are not per-source
truth, and unvalidated intervals cannot become scientific certification. The next
statistical work concerns paired-target margins, interval coverage, population
and source variation, missingness and solver behavior. Source qualification and
the authorized capture's physical setup declaration remain outstanding. No audio,
listener collection, metric execution, training or public verdict was enabled.

## Paired uncertainty sensitivity diagnostic — 2026-09-05

The [paired uncertainty audit](perceptual-degradation-paired-uncertainty-20260905.md)
tests the unchanged fixed-variance solver on bounded, role-linked synthetic
paired grades. It includes five variance settings and three missingness
mechanisms, retaining the same pre-missingness population target throughout.
Complete balanced designs are checked against independent mean/variance
calculations and finite discrete probability enumeration; 128 actual fitted
panels per mechanism supply additional diagnostics with Monte Carlo uncertainty.

Enumerated interval coverage is 97.624% with matched variance but 73.595% when
all three generating standard deviations double. The old multiplier corresponds
to approximately 97.5% central normal coverage, not ordinary 95% or established
familywise coverage. Under the declared outcome-dependent missingness mechanism,
0/128 returned intervals cover the target; 97 panels pass count gates and still
produce nonmaterial severity support at the diagnostic boundary. Missing-source
panels all abstain on support. These are conditional synthetic findings, not
human error rates or a scientific disposition about perceptual estimation.

The fixed-variance, complete-case path remains unqualified for human calibration.
Variance estimation, valid uncertainty and selective-missingness sensitivity
need an explicit successor; correct label logic and numerical convergence do
not substitute for them. No human margin, replacement estimator, audibility
model or multiplicity rule is selected. Source qualification, physical capture
setup, human calibration, oracle validation and all no-reference gates remain
open. No research audio, real listener data or sealed evidence was accessed.

## Paired uncertainty serialization successor — 2026-09-05

The original uncertainty checkpoint passed locally but failed its Linux CI
golden-report comparison because a Wilson boundary serialized as `0.0` versus
`0`. The [serialization correction](perceptual-degradation-paired-uncertainty-serialization-20260905.md)
uses floating-point clamp constants and retains the original evidence unchanged.
The successor report binds the original hash. Two full corrected local replays
are byte-identical; tests require numerical equality of every original scenario
and exact byte equality with the corrected golden report. No experimental
assumption, threshold, result or scientific eligibility changes. Remote CI
verification applies to the corrected commit separately from the failed run.

## Crossed resampling and missing-rating bounds — 2026-09-05

The [paired resampling comparison](perceptual-degradation-paired-resampling-20260905.md)
evaluates the unchanged fixed-variance solver, a listener/source-resampled
basic interval and a bounded-missingness extension on 12 declared synthetic
mechanisms, with 128 panels each. Every method receives completed paired values
and the planned assignment grid, never the hidden generated outcomes.

Crossed resampling improves doubled-variance coverage from 90/128 to 119/128,
but rare-source coverage remains 105/128. All 23 crossed misses in that case
occur among 33 panels lacking the rare source component, despite adequate
counts. Complete-case resampling also retains 0/128 coverage under selective
outcome missingness. Bounds cover in those generated missingness cases while
often abstaining; clear controls expose the cost in useful decisions. Forty-four
source-missing complete-case intervals fail because a bootstrap draw is empty;
none is silently dropped or resampled.

Two full CLI replays are byte-identical. Doubling bootstrap draws on 96 panels
is a limited precision diagnostic, not a validation pass. No replacement is
selected for human calibration, and no source, capture, listening, metric,
oracle, training or public-verdict gate is opened. Finite source-sampling
uncertainty and rare components now require explicit attention alongside
selective missingness. The full objective remains unachieved.

## Independent-group boundary-rate audit — 2026-09-05

The [independent-group audit](perceptual-degradation-independent-groups-20260905.md)
finds that the frozen full-reference bootstrap and boundary-rate guard use
source counts even when multiple sources share a partition group. Regrouping
the existing synthetic fixture's 40 sources into 40, 20 or one partition changes
only diagnostic counts: record validation accepts each, and both boundary-rate
components retain the same numeric pass. This is not a whole-oracle evaluation.

Exact enumeration of 128 declared independent-partition/shared-outcome models
shows how this can overstate generalization evidence. With 20 independent
partitions, two sources each and true false-alert probability 0.11, the zero-alert
event alone produces a false combined safety-component claim with probability
0.0972299658. This is a hypothetical dependence result, not an audio error rate.
Partition-count Wilson still has small-sample undercoverage; exact binomial
tails apply only under the audit's explicit Bernoulli assumptions. Unequal-size
examples also show that changing the grouping can change target weighting.

Two full replays are byte-identical. The next inferential successor must declare
the sampling population, independent units, dependence and weights, separately
from leakage-control IDs and source-conditional listener targets. No replacement
method or group-count cutoff is selected; original evidence is unchanged.
No capture, human, metric, oracle, training or public-verdict prerequisite is
opened. The full objective remains active and incomplete.

## Source-condition linkage and evidence units — 2026-09-05

The [case-linkage successor](perceptual-degradation-case-linkage-20260905.md)
connects the unchanged paired response reducer to a declared synthetic
assignment-to-case registry. It separates listener-specific presentation aliases
from stable reference/condition comparisons and from source/leakage groups.
Across five complete scenarios, 1,440 presentations map to 60 cases sharing
12 source groups and six leakage groups. No count is promoted to an independent
sampling-unit count or population support.

Three missingness variants retain the complete planned case inventory, separate
choice and paired-rating denominators, and leave missing full-panel targets
null. Dropping the incorrect-choice pairs changes the observed paired mean
from −0.5 to −2, but does not replace the original full-panel target. An entirely
unanswered case remains present. All four bound aggregate target-adapter outputs
are rejected by the finite case-summary consumer preflight; scientific-label
and population-inference requests remain closed.

Two full CLI replays are byte-identical. This is synthetic linkage and
finite-panel arithmetic, not observed source identity, a selected estimator,
calibrated uncertainty or a replacement full-reference evaluator. Exact real
case linkage, source-conditional listener targets and a population sampling
contract still need separate justification. The physical capture setup and all
source, listening, metric, oracle and no-reference prerequisites remain open.
No existing evidence, scientific gate or public verdict was changed.

## Sparse/tonal descriptor rate and context audit — 2026-09-05

The [descriptor audit](perceptual-degradation-descriptor-rate-context-20260905.md)
replays four fixed mathematical signals at 48, 96 and 192 kHz, with exact
sample equality on their shared time grid. A separately declared 15-second
padded construction passes the sparse/non-tonal contrast at 48 kHz but abstains
at 96 kHz: flatness changes from 0.986670558 to 0.000039540 while both retain
one active time block and supported spectral measurements. Both rates are
permitted by the unchanged clean-capture specification. No actual capture or
natural-source truth is represented by these synthesized constructions.

Eight occupancy-only cases establish a separate context dependency. A fixed
1.6-second event occupies three active blocks at onset 5.950 seconds in a
15-second record, but two after a 50-ms translation or after adding 15 seconds
of trailing zeros. Its sparse flag changes at both permitted rates. Independent
exact interval-overlap calculations agree with every case. Whole-recording
occupancy is intentionally context-relative; this is not declared a coding bug.

Two complete final replays are byte-identical. All controls and non-transition
results are retained, including the coherent unpadded kernel's tonal result.
The audit does not isolate every spectral mechanism or reclassify a retained
candidate. It supports a prospective review of physical-band/window support
and event-versus-recording context before treating the descriptor as a
rate-independent trait adjudicator. Original thresholds, source outcomes and
capture authority are preserved. No listening, metric, oracle, training or
public-verdict gate is opened; the full objective remains active.

## Descriptor frame-origin and window-support mechanism — 2026-09-05

The [window-support audit](perceptual-degradation-descriptor-window-support-20260905.md)
isolates frame origin and inventory at fixed 48-kHz rate on unchanged exact
integer periodic records. Across three families, 1,024 origins and two frame
counts, it evaluates 6,144 cases with three declared diagnostic summaries.
Every frame has identical raw energy within its family. Forty-eight comparisons
against the unchanged descriptor and a separate NumPy calculation agree.

For the coherent development period at origin zero, six post-Hann weak-spectrum
frames contribute only 0.029395914% of analyzed-band energy but determine the
11-frame equal-weight medians and a tonal result. Reversing the 6:5 inventory
by advancing the grid one hop gives non-tonal; balancing it with a twelfth frame
gives indeterminate. The full original class changes at 172 of 1,024 origins
between the two inventories. The exact impulse and tone controls remain stable.

Additional admission by post-window band energy changes the origin-zero result
while retaining over 99.97% of energy, but still leaves 20 indeterminate origins
with 11 frames. Pooling spectra is non-tonal throughout this coherent grid,
without establishing natural-source validity or preserving temporal structure.
Neither diagnostic is selected as a replacement, and no threshold is tuned.

Two full replays are byte-identical. All 18,432 method decisions are retained as
complete origin-class encodings, alongside aggregate numeric evidence. The
next definition must align physical band, frame support, aggregation and the
intended trait, then use fresh validation. Prior source outcomes, capture
authority, human/metric/oracle/training gates and the verdict-free CLI remain
unchanged. The objective stays active and incomplete.

## Continuous temporal energy measure — 2026-09-07

The [temporal measure](perceptual-degradation-temporal-energy-measure-20260907.md)
selects and implements exact squared-sample energy-quantile times in seconds,
separately from literal nonzero support and recording-relative occupancy. It is
a technical development measure, not a sparse classifier or perceived-duration
model. Original source outcomes and descriptor thresholds are unchanged.

Nine declared profiles at two native rates and two signed gains produce 36
summaries. Exact zero append preserves temporal spans while changing the context
ratio; a 50-ms translation shifts quantile times without changing their spread.
Separating equal-energy intervals preserves 1.6 seconds of nonzero support while
widening central-90 spread from 1.44 to 12.64 seconds. Positive background is
retained: one declared append changes the span from 1.5606 to 14.5458 seconds,
showing why this raw measure cannot silently stand for event or perceived duration.

Two complete captured replays are byte-identical. Thirty-six dense sample-cell
checks and independent closed-form unit expectations agree exactly; the dense
core shares result assembly, so this is numerical corroboration, not scientific
validation. Background, carrier/DC dependence and spectral time-locality still
require explicit scope and fresh validation before source assignment.

The authorized capture still needs its physical setup and execution checkpoint.
No actual audio, source assignment, listening, metric, oracle, training, external
communication, spending or public-verdict boundary changes. The overall research
objective remains active and incomplete.

## Channel normalization information boundary — 2026-09-07

The [channel audit](perceptual-degradation-channel-normalization-boundary-20260907.md)
distinguishes the current diagnostic alignment from prospective normalization.
The unchanged alignment does not apply its reported gains or polarity, and all
18 synthetic executions preserve their input arrays. Fifteen alignments are
supported; the original oracle still returns blocked or unsupported states and
never supplies perceptual outcomes.

Exact common and independent gain projections show different information loss.
Independent fits erase residuals for channel imbalance and relative polarity;
they can also fit a dropped channel with zero gain and zero residual. Both
dropouts remain alignment-unsupported. A correlated channel swap and both
dual-mono mixtures are alignment-supported, so support alone cannot exclude
known channel remixing or authorize sample changes.

The audit also preserves the dropped channel's misleading correlation of 1,
traced to an invalid-energy sentinel followed by absolute value. Its combined
support still abstains. Whole-record Gram geometry also misses some waveform
changes. Neither component diagnostics nor projection residuals establish
perceptual fidelity, and neither prospective correction method is selected.

Two full replays are byte-identical; all 18 direct/Gram checks agree exactly.
The selected boundary keeps original channel relationships available and requires
a target-matched successor before any real normalization. Original implementations,
thresholds and research evidence are unchanged. Capture setup, source assignment,
human calibration, metric execution, oracle validation, no-reference training
and public-verdict prerequisites remain open; the objective remains incomplete.

## Explicit alignment correlation validity — 2026-09-07

The [validity successor](perceptual-degradation-alignment-validity-successor-20260907.md)
replaces invalid-correlation sentinels throughout a separate score-free alignment
implementation. Undefined values cannot enter candidate ranking, local drift or
structural regression, or complete-channel minima. Valid signed −1 correlation
remains distinct from invalid zero-energy evidence. No gain correction is applied.

All 18 consumed channel-audit fixtures retain their support decisions: 15 supported,
three unsupported. The 196 jointly defined diagnostic values match the prior
report precision, while 20 dropout slots become explicitly unavailable. A new
central-silence fixture has only four of five valid drift windows and six of seven
valid structural windows; both local models abstain rather than fitting fallback
lags. Constant-envelope and zero-energy evidence also remain unsupported.

Two complete synthetic replays are byte-identical. Original code, limits and
reports remain unchanged. The old oracle rejects the successor's distinct record
kind for all 23 alignment records, preventing silent integration or coercion of
null values. No actual audio, source assignment, normalization, metric, listening,
training, outreach, spending or public-verdict gate opens. The authorized capture
still requires its physical setup, and the overall objective remains incomplete.

## Score-free oracle validity integration — 2026-09-07

The [oracle successor](perceptual-degradation-oracle-validity-integration-20260907.md)
consumes validity-aware alignment without silently filling unavailable evidence.
It validates numeric and support consistency, retains per-channel rejection
reasons and complete-channel nulls, and explicitly binds the four-second subtle
or eight-second quality-metric mode. A valid record does not prove the source's
provenance or the producer's actual configuration.

Seven declared synthetic cases produce three technically supported but
execution-blocked oracle records and four alignment-unsupported records. The
six-second identity does not meet the eight-second requirement; the twelve-second
construction does not enable metric execution. Supported polarity inversion
does not establish fidelity. No samples are normalized or corrected.

All oracle support remains false. Severity, artifact components, distinct
correct-response and audible-condition probabilities, and uncertainty intervals
remain unavailable. Neither a metric suite nor a human-calibration mapping is
selected. Original evidence and thresholds are unchanged. The physical capture
setup and all real-data prerequisites remain open; the objective is incomplete.

Two complete final synthetic replays are byte-identical. This establishes only
repeatable software integration, not perceptual validity or generalization.

## User-approved digital-development sequencing amendment — 2026-09-07

The user approved [deferring capture and using the retained ODAQ references](perceptual-degradation-digital-development-sequence-20260907.md)
for the first digital development study. For this study only, the new
[amendment](../../benchmarks/perceptual-degradation-v1/digital-development-sequence-amendment-20260907.json)
supersedes the capture-first next-step dependency in historical objective audit
022. Do not continue requesting microphone/preamp details as a prerequisite for
preparing this study. The earlier observations and full completion requirements
remain unchanged; the seven-trait manifest is not declared complete.

Next: prepare one exact execution proposal and tested bounded runner for the
existing 16-member, 48 kHz stereo canonical-delivery cohort. Freeze recipes,
matched input controls, exact tools, delay/padding treatment, case accounting
and private retention before seeking execution approval. The cohort stays
development-only and colocated; no current file-integrity verification or new
audio access is claimed. Unsupported members remain in the accounting.

This amendment permits planning, not codec generation, metrics, playback,
human collection, source assignment, new capture, outreach, spending or training.
The sparse capture and other missing source traits are deferred, not waived.
The retained drift negative, original thresholds, sealed evidence and public
verdict-free boundary are preserved. The full objective remains incomplete.

## Exact digital execution proposal — 2026-09-08

The [concrete proposal and bounded runner](perceptual-degradation-digital-execution-proposal-20260908.md)
are prepared for the retained 16-member canonical delivery cohort. Eight new
native-48-kHz codec recipes and two controls give 160 cases per replay, 320 across
two replays. The float32 input-adapter control is separate from codec comparisons;
decoder delay/padding metadata and unmodified alignment diagnostics remain explicit.
Study duration eligibility is capped at the actual aligned frame count so partial
activity-block rounding cannot manufacture four/eight seconds of support; the raw
legacy diagnostic and numeric limits are preserved.

The native tool/runtime closure is newly bound because installed tools and the
operating system changed since the historical work. All 16 sources and every
planned case remain in the denominator, including failures, unsupported cases and
cases not started after a resource/time stop. No family is designated unseen
validation by this development proposal, and no perceptual outcome is populated.

Constructed-fixture and mocked-boundary tests cover two complete replays without
actual codec generation. Real retained audio and private manifests remain unread.
Next is explicit approval of the exact two technical replays, followed by a
separately committed authorization and successful exact-execution-head CI. No
microphone, loopback, room test, metric, listening, training or public verdict is
requested or enabled by this preparation checkpoint.

## Exact digital technical execution approved — 2026-09-08

The responsible user explicitly approved the two private technical replays in
the published [proposal](perceptual-degradation-digital-execution-proposal-20260908.md).
The [execution authorization](../../benchmarks/perceptual-degradation-v1/digital-development-execution-authorization.json)
binds that unchanged proposal and runner. It opens only the exact retained
16-reference cohort, eight codec conditions and two controls, twice: 320 planned
comparisons with one worker and the frozen resource, accounting and retention
limits. No substitution, threshold adjustment or automatic rerun is authorized.

This is an approval checkpoint, not an execution result. The separately committed
authorization must pass exact-head push CI and the live native tool/runtime gate
before private path or inventory inspection. Playback, perceptual metrics, human
collection, source-trait assignment, training and public verdicts remain closed.
Prior dated records are unchanged; the broader research objective is incomplete.

## Digital technical replays: reproducible runtime failure — 2026-09-08

The [approved two-replay study](perceptual-degradation-digital-technical-result-20260908.md)
has finished. Both actual private reports are byte-identical: each accounts for
160 cases, with 20 alignment timeouts and 140 cases not started after the one-hour
cutoff. Sixteen codec encode/decode pairs and four controls reached alignment per
replay; no comparison completed. The fixed order attempted the same two sources
in each replay. All 320 planned slots remain visible, without substitution.

A separate read-only audit verified exact case identity/order, aggregate bytes,
source preservation and the five-file private JSON retention boundary. No derived
audio remains in the run directory. Native bindings matched before and after.
The execution head was `804e10a455c4facf0c5f85cc6a2ece371f98b343`, with successful
exact-head CI before private access; report publication is a separate checkpoint.

This exposes a runtime-qualification gap: tiny native-rate fixtures and mocked
replays did not demonstrate full-duration 48 kHz alignment throughput. Static
inspection suggests the exhaustive structural-window search is costly, but no
profiling hotspot or perceptual conclusion is established. Next is a separately
versioned synthetic-only full-rate performance/feasibility checkpoint.

The two-replay authorization is consumed; no third real replay, automatic repair
or rerun is authorized. Existing proposal, runner, thresholds and negative results
remain unchanged. No metric, playback, human truth, source-trait assignment,
training, independent-validation or public-verdict gate opens. The broader
research objective remains incomplete.

## Full-rate synthetic runtime feasibility — 2026-09-08

The [synthetic-only runtime checkpoint](perceptual-degradation-alignment-runtime-feasibility-20260908.md)
ran its four declared full-size cases twice, after a separate local pre-observation
commit. Both uninstrumented identities exceeded 180 seconds. Both timed identities
also timed out, spending 83.7% and 82.6% of observed alignment time in structural
correlations before the first channel completed. This localizes an engineering
bottleneck on the declared construction, not a perceptual failure.

Full-size constant-envelope and topology controls completed and correctly
abstained; their numerical alignment records match byte-for-byte. Timings and
partial counts differ as expected. All eight slots are retained, with null
completed alignment for timeouts. A separate read-only artifact audit passed.

Next is a separately versioned structural-correlation optimization with semantic
equivalence and full-size synthetic runtime evidence. Original alignment code,
thresholds and the consumed real-audio result remain unchanged. No real audio,
codec execution, playback, metric, human collection, training or public verdict
was enabled. No complete-run or second-channel timing is inferred, and the full
research objective remains incomplete.

## Native local-search synthetic qualification — 2026-09-08

The [separately versioned v4 qualification](perceptual-degradation-alignment-native-qualification-20260908.md)
completed both full-size uninstrumented identities in about 118 seconds, within
the unchanged 180-second limit. Both instrumented identities also completed.
All completed alignment records match across rounds and instrumentation modes;
all 135,624 local candidates per identity were evaluated, with no Python fallback.
The constant-envelope and topology controls correctly abstained. An independent
saved-artifact audit passed; frozen predecessor code and negative results remain
unchanged.

The native local-search backend preserves exact tested numerical behavior and
complete search coverage. Structural search still consumes about 83 seconds per
identity. This is a synthetic per-case execution pass, not a full-study throughput
or codec-pipeline qualification. A conditional 160 cases at the same 118-second
cost would take roughly 5.2 hours before codec work, exceeding the earlier
one-hour replay cutoff.

Next is a separately bounded end-to-end digital canary with new explicit
real-audio/codec authority and exact-execution-head CI, not an automatic full
replay. Human calibration, source independence, metrics, training and public
verdicts remain closed. The overall research objective is incomplete.

## Bounded native digital canary prepared — 2026-09-08

The [new canary proposal](perceptual-degradation-digital-canary-proposal-20260908.md)
and separately bound runner reduce the next end-to-end test to one full-length
reference, selected deterministically by largest declared frame count from the
frozen delivery metadata. Both input controls and one unchanged setting from
each of the four development codec families run twice: 12 comparisons and at
most eight encode/decode pairs. The other 15 waveforms remain unopened by this
successor. The conditional runtime estimate is about 24 minutes, not a measured
codec-throughput result or completion guarantee.

Constructed fixtures and mocked codec/CI boundaries test selection, authorization,
retention, edge-check stops and complete accounting. Timing alone is excluded
from deterministic replay comparison; numerical records, hashes, packet geometry,
support/nulls and native counts remain included. Control support, codec support
and computational completion are reported separately.

No real-source, codec, capture or playback execution occurred in preparing this
checkpoint. The new exact authorization remains absent and the consumed old
authorization cannot open this runner. Execution still needs user approval,
successful exact-execution-head push CI, unchanged native bindings and a live
15 GiB reserve plus 384 MiB scratch allowance. No cleanup or reserve reduction
is authorized. Metrics, human collection, trait assignment, training and public
verdicts remain closed; the overall objective remains incomplete.

Preparation validation passes: 29 focused tests, Rust formatting/Clippy/all-target
tests, and the full Python suite with 1,599 tests and 14 skips. After the initial
internal-volume reserve failures, validation ran from a byte-verified external
checkout with build and temporary storage on that volume. Missing historical
bindings in its initial shallow clone were resolved by fetching the complete
public Git history and rerunning the full suite. No implementation, consumed
result or reserve guard was changed. Two generated SBOMs are identical; the
publication privacy and artifact-boundary audit passed.

## Bounded native digital canary execution approved — 2026-09-08

The responsible user explicitly approved the [frozen canary scope](perceptual-degradation-digital-canary-proposal-20260908.md).
The [new authorization](../../benchmarks/perceptual-degradation-v1/digital-canary-authorization.json)
binds the unchanged proposal and runner. It permits one invocation comprising
two fixed six-condition replays on one full-length reference selected from the
hash-bound delivery metadata: 12 planned comparisons and at most eight
encode/decode pairs, with one worker. The other 15 waveforms remain unopened by
this successor. No substitution, threshold change or automatic rerun is allowed.

This records approval, not execution or a result. Private path, metadata and
waveform access still require this authorization to be committed, successful
push CI for the exact execution head, unchanged native tool/compiler bindings
and the live 15 GiB reserve plus 384 MiB scratch allowance. Failed, unsupported
and not-started cases remain in the accounting. The consumed predecessor
study and all frozen implementations, limits and negative results are unchanged.

No hardware, playback, perceptual metric, listening response, source-trait
assignment, training, independent-validation or public-verdict gate opens.
The broader objective remains incomplete.

## Bounded native digital canary: partial completion and failed repeatability — 2026-09-08

The [approved one-shot canary](perceptual-degradation-digital-canary-result-20260908.md)
has finished and its independent saved-artifact audit passed. All 12 planned
slots were attempted on the one metadata-selected reference. The first replay
had six alignment timeouts; the second had two timeouts and four completed,
technically supported comparisons. None completed in both replays. The
computational-completion and timing-excluded repeatability gates both failed.

All four codec conditions have matching recorded encoded/decoded hashes and
packet records across the two replays. That limited codec-stage repeatability
does not override the failed end-to-end gate. No native fallback was recorded;
the aggregate all-cases/no-fallback conjunction is false because eight cases
did not complete. No numerical nondeterminism or perceptual-quality conclusion
follows from timeout-censored comparisons.

The invocation took about 34.5 minutes. The approximately 118-second synthetic
identity did not establish sufficient margin for this real-source workload.
Static code leaves global refinement in Python with a content-dependent
candidate inventory, but no new runtime hotspot or scheduling cause was
profiled. Next is a separately frozen score-free workload/runtime successor,
or a prospectively justified controlled-digital alignment design, before any
further real-audio execution.

All replay-edge checks passed; the selected source is unchanged. The other
15 waveforms were not reopened by this successor or its audit. Five private
JSON files and the bound native library remain; no derived audio or case scratch
is retained. The authorization is consumed, without substitution, changed
limits or another run. Metrics, listening, source assignment, training and
public verdicts remain closed. The broader objective remains incomplete.

## Standing digital development authority and global-search qualification — 2026-09-08

The user now authorizes additional technical development attempts without a
fresh permission question for every shot. The [standing authorization](perceptual-degradation-standing-development-authority-20260908.md)
does not reopen consumed checkpoints. Every batch still has prospective
scope, immutable implementation/limits, bounded execution and full accounting;
real-reference batches still require successful exact-execution-head CI.

The [global-search workload successor](perceptual-degradation-global-workload-qualification-20260908.md)
adds an isolated v5 native global-correlation dispatch while preserving the v4
alignment model, every lag, numerical method and support threshold. A fixed
16-slot synthetic qualification spans four numeric/activity families, comparing
full-size global candidate records with v4 and timing full stereo alignments.
The unchanged 180-second deadline has a new prospective 120-second margin gate.
No full-size observation or further real-audio execution is claimed at this
protocol checkpoint. Metrics, human collection and public verdicts stay closed.
