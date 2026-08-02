# Factorial benchmark v2 source-allocation preregistration

Date: 2026-08-02

State: rules frozen before identity selection; no allocation result, benchmark
audio, factor level, mechanism score, or unopened label inspected

## Purpose and boundary

This checkpoint fixes how one reference member will be chosen for every
retained v2 source group. It binds the completed source-identity checkpoint at
commit `3049123bfd58de567f65633b2e2d423acf147747` and the exact identity-rule
and evidence hashes in
[`source-allocation-rules.json`](../../benchmarks/audio-integrity-v2/source-allocation-rules.json).

Selection is allowed to use only provider identifiers, archive member names,
provider metadata factors, and the already-consumed v1 manifest's structural
fields. It may not use waveform samples, duration, audio hashes, baseline or
mechanism measurements, model output, or unopened labels. Listing and hashing
the bound source artifacts verifies input identity; it is not audio analysis.

The expected allocation is 793 groups:

| Evidence partition | Groups | Source contribution |
| --- | ---: | --- |
| Mechanism development | 527 | already-consumed v1 non-holdout sources |
| Encoder transfer | 102 | VCTK 56, RAVDESS 24, FSDD 6, TinySOL 1, SONYC 15 |
| External transfer | 164 | SATP 25, Lombard Grid 54, RWC 85 |

External-transfer identities may be frozen now, but their generated cases,
measurements, and outcomes remain sealed. The existing v1 future SQAM and
release holdouts are excluded.

## General deterministic rule

Private source and partition group IDs are derived from a domain-separated
SHA-256 of the source ID and raw provider group identity. Within each retained
group, candidates are ranked by a second domain-separated SHA-256 over source
ID, private group ID, and member ID. The lowest digest wins; member ID is only
the collision tie-break. Every string boundary is explicit and NUL-delimited.

This behaves like a fixed random ordering without a mutable seed. Reordering
an archive directory or metadata table cannot alter the result. The rule stops
if a group has no candidate, the expected counts differ, or any identity is
ambiguous.

## Source-specific decisions

### Already-consumed development evidence

Exactly one negative base class is fixed for each source domain. The 48 public
Tier A original groups must match the 48 controlled groups exactly; the
controlled PCM excerpt is selected because it is the matched reference from
which the already-consumed derivatives were made. This avoids allocating the
same source twice while preserving 527 unique development groups. SQAM rows
are excluded.

### VCTK

The source-identity audit found 29 female and 29 male speaker IDs in the
nominal 56-speaker release. Before choosing utterances, the already
preregistered VCTK-specific hash ranking retains 28 speakers independently in
each provider gender. The general member ranking then selects one utterance
per retained speaker. No accent, transcript, duration, or signal property
changes that rank.

### RAVDESS, FSDD, TinySOL, SONYC, SATP, and Lombard Grid

- RAVDESS selects one member per actor across speech and song after excluding
  both members of its one exact repeated-PCM pair.
- FSDD selects one member per repository speaker and preserves its native
  8 kHz bandwidth as a factor.
- TinySOL selects one non-retuned member from the common conservative
  collection group. Retuned rows cannot be base references.
- SONYC selects one clip per sensor across time and provider split.
- SATP selects one non-calibration recording per exact coordinate group;
  missing-coordinate recordings remain singleton groups.
- Lombard Grid selects one canonical, uniquely reconciled `CORRECT` utterance
  per talker.

### RWC

RWC requires both one member per artist family and no repeated normalized work
title. Independent per-family minima cannot guarantee both constraints, so the
rule uses a deterministic maximum bipartite matching:

1. retain the best-ranked member for each family/title edge;
2. hash-order families using a third domain separator;
3. visit each family's title edges in member-rank order; and
4. run deterministic depth-first augmenting paths, allowing earlier owners to
   be reassigned.

The run must find a complete 85-family matching with 85 distinct normalized
titles or stop without emitting an allocation. This is a feasibility
constraint, not a post-result repair.

## Private and public artifacts

The implementation writes two exact private artifacts outside Git:

1. a candidate index containing member locators and grouping factors; and
2. the selected source allocation.

Neither may contain absolute machine paths. The public aggregate may contain
only counts, rule and private-artifact hashes, constraint checks, and replay
state. It recursively rejects case IDs, group IDs, member IDs, relative paths,
audio hashes, and source-group identifiers.

Two complete executions must produce byte-identical canonical JSON for both
private artifacts. Canonical JSON is UTF-8, sorted by key, indented by two
spaces, and terminated by one LF. Timing fields are prohibited.

## Stop conditions and next gate

The allocation stops on any input-hash, identity-state, eligibility-count,
group-count, unique-title, privacy, or replay mismatch. A failure is resolved
by a separately documented correction, never by changing the ranking after
seeing selected members.

A successful replay freezes source allocation only. Factor levels, exact
toolchain bindings, and the fractional assignment require separate committed
freezes before any v2 benchmark audio is generated or any mechanism score is
opened.
