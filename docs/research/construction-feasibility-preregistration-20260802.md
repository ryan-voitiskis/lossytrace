# Factorial benchmark v2 construction-feasibility preregistration

Date: 2026-08-02

State: header-only audit frozen before duration inspection; no benchmark audio,
waveform samples, feature, score, or unopened label inspected

## Purpose

Fractional assignment deliberately excluded duration and waveform metadata.
Before construction, this gate checks whether the exact selected members can
realize their already-assigned excerpt, channel, and transform cells. It does
not change a source selection or assignment.

The machine-readable
[`construction-feasibility plan`](../../benchmarks/audio-integrity-v2/construction-feasibility-plan.json)
binds the lineage-complete private assignment, source allocation and candidate
index, factor and toolchain manifests, private tool-path registry, and exact
[`audit generator`](../../scripts/audit-audio-integrity-v2-construction-feasibility.py).
The plan SHA-256 is
`25836479805455f6381e9f171d612e89f599199401aa7b3da18d33167e84114b`;
the generator SHA-256 is
`92ee0a3d07562a4dc8e7332abc584bef07b6507e7f1fe7e92b65bf86390dadd1`.

## Allowed observations

The audit may verify already-bound archive bytes and read only these stream
header fields: codec name, sample rate, channel count, duration timestamp, and
time base. Archive members are extracted only into an ephemeral one-worker
directory. No source PCM sample is decoded, hashed, summarized, or retained.

Provider-window decimal boundaries become integer native frames by taking the
ceiling of the start and floor of the exclusive end. This keeps the selected
window entirely inside the declared interval. The effective excerpt is the
smaller of that window and exactly 12 native seconds; short sources are not
padded, looped, stretched, trimmed, rejected, or silently replaced.

## Fixed feasibility checks

- Native channel count must be one or two.
- Current source codec must be bound lossless PCM or FLAC.
- `trim-head-250ms` requires at least 500 ms.
- `duration-prefix-3s` requires at least 3 s.
- All other transforms have no header-level minimum.

Any failure is reported by partition, domain, and transform in path-free
evidence. Pooled success cannot hide an unsupported group. This gate may
invalidate an assignment recipe, but it cannot choose a replacement.

## Replay and authorization boundary

The complete private audit and path-free run aggregate must each be
byte-identical across two runs. A clean result authorizes freezing exact source
preconditioning and construction recipes. Any unsupported group stops
construction and requires a separately committed correction. In either case,
mechanism scoring and all transfer-label opening remain unauthorized.
