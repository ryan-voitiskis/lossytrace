# v2 source identity audit - RWC metadata - 2026-08-02

**Status:** metadata identity rules audited; audio acquisition and source
allocation remain unfrozen

**Actions:** exact annotation revision and metadata bytes bound, known
repeated-composition rows excluded, artist-label overlaps reviewed, family
merges declared, no RWC audio acquired, no benchmark derivative generated,
and no mechanism score opened

The rules are
[`benchmarks/audio-integrity-v2/rwc-artist-family-rules.json`](../../benchmarks/audio-integrity-v2/rwc-artist-family-rules.json),
the path-free observed result is
[`research/sources/evidence/rwc-metadata-observed-20260802.json`](../../research/sources/evidence/rwc-metadata-observed-20260802.json),
and the replay is
[`scripts/audit-audio-integrity-v2-rwc-metadata.py`](../../scripts/audit-audio-integrity-v2-rwc-metadata.py).

## Decision

Reduce RWC's planning contribution from 99 exact artist strings to 85
conservative artist families. This is a 14-group reduction, not an audio
finding. After the subsequent SATP exact-coordinate audit, external transfer
projects to 188 groups across nine domains—38 above the preregistered floor of
150.

The family count is suitable for source allocation only after the five RWC
audio archives pass their provider checksums and member identities reconcile
to the pinned metadata. It is not permission to treat 85 families as 85
independent recording studios or statistical replicates.

## Exact metadata binding

The official [RWC v2 release](https://zenodo.org/records/18656623) points to the
separate
[RWC annotations repository](https://github.com/rwc-music/rwc-annotations).
This audit binds:

- annotation revision `0a1a6c31dbe73a7f5d44f7caef8cd0999402a4c2`;
- `metadata.csv` SHA-256
  `eba3fe129f835db58a9c23dad554547201ab02ef3af90c10857ef5b50b8b99da`;
- 328 unique `RWCID` rows across the five retained collections; and
- 99 globally unique, nonempty exact artist labels before exclusions.

No count comes from a mutable branch tip at replay time.

## Why 35 jazz rows are ineligible

The primary
[RWC Jazz description](https://staff.aist.go.jp/m.goto/RWC-MDB/rwc-mdb-j.html)
states that pieces 1–35 are five compositions intentionally repeated across
seven instrumentations. They were designed as alternate arrangements, with
duos, trios, and larger groups that may share named or unnamed players.

Counting their 15 displayed artist labels as independent source identities
would conflate work, arrangement, ensemble, and performer dependence. The
rules therefore exclude all 35 instrumentation-variation rows before family
accounting. The 15 jazz style/fusion rows remain eligible, preserving the jazz
domain without knowingly repeated works.

After that exclusion:

| Quantity | Count |
| --- | ---: |
| eligible rows | 293 |
| exact artist labels | 87 |
| normalized work titles | 292 |
| duplicated normalized title groups | 1 |

The sole normalized-title duplication is `Silent Night`; the later allocation
rule permits at most one of the two rows.

## Artist-family reconciliation

An automated review queue flags every pair of eligible labels sharing a
non-generic normalized name token. All 12 pairs were manually adjudicated and
are bound in the rules:

- merge `Kazuo Nishi` with `Nishi feat.T`; the latter row also credits Kazuo
  Nishi as composer;
- merge `Yuriko Furuichi` with `Yuriko Furuichi & Yoshiko Kikuchi`; and
- keep ten same-given-name, same-surname, or generic Tokyo/orchestra overlaps
  separate because the full named identities differ.

Those two merges reduce 87 eligible labels to 85 artist families. The replay
fails if a future metadata revision changes the overlap queue without an
explicit review, if a merge label disappears, or if a reviewed decision and
the unioned family graph disagree.

## Independence boundary

Artist metadata cannot establish disjoint recording sessions, engineers,
studios, or backing personnel. The benchmark must therefore retain all of the
following simultaneously:

- at most one selected reference excerpt per artist family;
- no repeated normalized work title;
- collection, family, work, legacy disc, and track IDs in the manifest;
- RWC as one provider-level stratum in uncertainty and transfer reporting; and
- leave-provider/domain sensitivity so 85 nominal RWC families cannot dominate
  a cross-domain conclusion.

This is deliberately stricter than treating songs as independent, but it does
not claim person-level ground truth that the provider metadata does not expose.
If the audio member audit reveals additional session or duplication links, the
85 count must fall; the 38-group margin absorbs reductions down to 47 RWC
families without changing the external-transfer floor.

## Next gate

RWC's metadata identity concern is resolved enough to proceed to bytes, not to
freeze. The subsequent
[RAVDESS source-identity audit](ravdess-source-identity-audit-20260802.md)
bound its 24 actor groups without changing the projected external-transfer
count. The remaining source gate is to verify the RWC audio archives and the
VCTK, Speech Commands, and TinySOL identities. Only after those checks may
source allocation, factor levels, and toolchain bindings be committed as
separate frozen records.

No RWC audio acquisition, excerpt selection, benchmark generation, candidate
evaluation, or external-transfer score opening is authorized by this audit.
