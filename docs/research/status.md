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
