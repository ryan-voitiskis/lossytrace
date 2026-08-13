# Permissive provider-allocation feasibility - 2026-08-14

**Status:** score-blind aggregate-capacity sensitivity complete. No exact
member, source manifest, provider allocation, primary-domain design, audio
access, score access, metric execution, recruitment, collection, no-reference
work, or public verdict is authorized.

## Outcome

The seven CC BY providers in the exact-member-audit tier can arithmetically
pack at least 39 source groups into each of development, calibration, transfer,
and final validation while keeping every provider in at most one partition.
That count-only result is not a viable research design: the deterministic
witness assigns whole partitions to speech, natural sound, or synthetic
material and permits complete provider/domain confounding.

Two minimal safeguards expose the shortage:

- two providers in every partition requires eight provider slots, but only
  seven eligible providers exist; and
- the eligible real-music candidates contain only seven groups—six GuitarSet
  performer groups and one TinySOL recording-program group—below the existing
  eight-group primary-domain evaluation minimum.

Slakh's 1,710 deduplicated MIDI groups remain `synthetic`. Relabelling them as
real music would make the arithmetic look easier while destroying the domain
boundary the sensitivity is intended to test.

## Frozen sensitivities

| Scenario | Arithmetic result | Scientific result |
| --- | --- | --- |
| Seven audit-tier providers, count only | feasible | ineligible; domain/provider confounding |
| Seven audit-tier providers, at least two providers per partition | infeasible | ineligible |
| Audit tier, final has at least eight music, speech, and natural groups | infeasible | ineligible |
| Add provenance-pending MusicNet to that final-domain constraint | infeasible | ineligible |
| Add both pending MusicNet and FSD50K | feasible | ineligible; depends on unresolved source histories and exact members |
| Require music, speech, and natural breadth in every partition | infeasible even with both pending providers | ineligible |

The MusicNet-only failure is not a group-count problem. Reserving a music,
speech, and natural provider for final validation leaves too few provider-pure
capacities to fill all three other partitions. Adding FSD50K supplies a large
aggregate capacity for one non-final partition and makes that narrow arithmetic
sensitivity feasible, but FSD50K's mixed clip-level licences and source
histories and MusicNet's upstream coding history remain unresolved. Neither is
promoted by the calculation.

## Deterministic method

The solver orders providers by opaque provider ID, considers `unused` followed
by the four frozen partitions, and assigns each provider to at most one
partition. Dynamic-programming states retain only capacity capped at the
scenario's 39-group, provider-count, and eight-group domain thresholds.

This is a monotone lower-bound capacity test. A witness reports provider-level
available capacity only. It does not choose a single source group or member,
and it does not prove that provider groups are independent, correctly licensed,
never previously lossily coded, appropriately attributed, or operationally
affordable.

Two fresh executions were byte-identical at SHA-256
`cb81d0016ab8ad4916ffdb5ad82203225d0d090af7554e50d86c575047d166d7`.
The report binds plan SHA-256
`02969f38ae6ad69b221b8285f16769d726c8dc3e3896d5647f0f20a662d3e1a2`
and implementation SHA-256
`d97ad981c985dcedea6ce530f84caa9a736f62bf7866102439dfe8a351af1f32`.

## Decision

An exact-member manifest is premature. The current eligible pool passes only
the weakest count-only screen and fails simple leakage and domain-breadth
sensitivities. The next score-blind requirement is one of:

1. identify or qualify additional independent, permissively licensed
   real-music, speech, and natural providers with auditable original coding
   histories; or
2. explicitly narrow the future primary-domain and generalization claim before
   any members or listener workload are frozen.

Neither choice is made here. The user's narrow ODAQ acquisition authorization
is unchanged, and ODAQ remains one-provider development plumbing rather than a
truth-bearing partition.

Machine-readable bindings:

- [`feasibility plan`](../../benchmarks/perceptual-degradation-v1/permissive-provider-allocation-feasibility-plan.json)
- [`deterministic report`](../../research/toolchains/evidence/perceptual-degradation-permissive-provider-allocation-feasibility-20260814-001.json)
- [`solver`](../../scripts/perceptual_degradation_provider_allocation_feasibility.py)
