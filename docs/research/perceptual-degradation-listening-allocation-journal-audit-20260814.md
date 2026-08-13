# Perceptual-degradation allocation-journal audit - 2026-08-14

**Status:** synthetic single-database candidate audit passed. The candidate can
reserve contiguous v3 allocation indices exactly once under the audited
multi-connection retries and logical restart faults. It is not an operational
policy or collection service. Real eligibility, deployment, privacy ownership,
backup, response atomicity, missingness, exclusion, and recovery policies
remain unfrozen, and human collection remains unauthorized.

## Candidate boundary

The candidate uses one SQLite database file with WAL journalling,
`synchronous=FULL`, and `BEGIN IMMEDIATE` for every reservation. Each immutable
stream binds:

- the manifest ID and SHA-256;
- the v3 allocator policy and allocation-seed SHA-256;
- the subtle and MUSHRA trial limits; and
- an opaque eligibility-contract ID.

Each reservation contains only a stream ID, zero-based allocation index,
opaque request ID, opaque request-binding SHA-256, opaque eligibility-
attestation SHA-256, previous event hash, and current event hash. The schema
has no participant key or identity, response, outcome, rating, score, path, or
timestamp column. Stream and reservation updates and deletes are rejected by
database triggers.

The request ID is unique within a stream. Repeating it with the same binding
and attestation returns the original index. Repeating it with changed inputs is
rejected. The next index is derived and inserted inside the same immediate
transaction; there is no separately mutable counter. Event hashes form a
canonical SHA-256 chain from a fixed genesis digest.

## Concurrent retry audit

Sixteen fresh-database trials each used two streams, 96 unique requests per
stream, three calls per request, 24 workers, and independent SQLite
connections. Across all trials:

- 9,216 calls completed;
- exactly 3,072 reservations were created;
- exactly 6,144 calls returned the existing idempotent reservation;
- every stream contained the exact range `0..95` with no gap;
- every stream contained 96 unique request IDs; and
- zero conflicting retry was accepted.

All 16 trials passed the schema, configuration, contiguity, uniqueness, and
hash-chain verifier.

This is evidence for serialization inside one SQLite database under audited
threaded multi-connection contention. It is not a distributed-linearizability,
multi-host, network-filesystem, or database-replication result.

## Logical restart audit

Twenty-four unique requests were injected at each of four fault points:

| Fault point | Present before retry | Retry result |
| --- | ---: | --- |
| Before transaction begin | 0 / 24 | 24 created |
| After begin, before insert | 0 / 24 | 24 created |
| After insert, before commit | 0 / 24 | 24 created |
| After commit, before reply | 24 / 24 | 24 idempotent returns |

After reopening a connection and retrying every request, the journal contained
exactly 96 reservations with indices `0..95`. No duplicate and no gap was
created.

The injected failure closes a logical database connection. It does not kill an
operating-system process, corrupt a WAL, remove a directory entry, exhaust
storage, or cut power. `synchronous=FULL` is a candidate setting, not proof of
the filesystem, storage device, host, backup, or disaster-recovery boundary.

## Immutability and tamper evidence

Reservation update, reservation delete, stream update, and stream delete were
all rejected. A reused request ID with a changed binding and an existing stream
ID with a changed configuration were also rejected, leaving the journal valid
and unchanged.

Three copies then had the append-only triggers deliberately removed before an
event-hash change, request-binding change, or middle-row deletion. The verifier
detected all three through missing triggers, canonical event-hash mismatch,
chain mismatch, or allocation-index gaps. This makes tampering detectable in
the audited representation; it is not a cryptographic transparency service,
external notarization, key-management design, or protection against an
attacker replacing the database and every expected binding together.

## V3 integration

A separate synthetic stream reserved indices `0..191` against the bound
120-source symbolic manifest and the 8 + 6 trial limits. The journal verifier
passed, and the v3 allocator audit passed every contiguous prefix through 192:

- maximum trial-exposure range: 1;
- maximum within-block trial-position range: 1; and
- maximum candidate-position range: 1.

This closes the narrow gap between the v3 allocator's contiguous-index
assumption and one technically credible single-database reservation candidate.
It does not preserve balance after missing responses or exclusions; the
separate missingness and retained-design audits continue to govern that
boundary.

## What remains before any operational selection

The opaque eligibility-attestation field proves only that a value was bound,
not that consent, eligibility, training, playback, or device checks occurred
before reservation. A separately frozen policy would still need to define:

- the exact pre-reservation eligibility transition and authority;
- participant-key custody and assignment-delivery data flow;
- deployment topology, filesystem, locking, backup, restore and retention;
- atomic trial-response submission and duplicate evidence;
- privacy ownership, access control, withdrawal and incident handling;
- outcome-blind monitoring, incompleteness and exclusions;
- post-assignment support diagnostics and abstention; and
- explicit recruitment, response-storage and collection authority.

No operational journal, eligibility rule, allocator policy, workload, listener
count, missingness correction, response store, recruitment or collection path
is selected. No audio, identity, response, outcome, score, metric or sealed
evidence was accessed, and the public CLI remains verdict-free.

## Bound artifacts

- [`frozen plan`][plan]
- [`candidate and audit implementation`][implementation]
- [`synthetic audit evidence`][evidence]

[plan]: ../../benchmarks/perceptual-degradation-v1/listening-allocation-journal-audit-plan.json
[implementation]: ../../scripts/perceptual_degradation_listening_allocation_journal.py
[evidence]: ../../research/toolchains/evidence/perceptual-degradation-listening-allocation-journal-audit-20260814-001.json
