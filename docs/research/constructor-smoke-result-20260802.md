# Factorial benchmark v2 constructor smoke result

Date: 2026-08-02

State: both 202-cell score-blind smoke roots are complete and byte-identical;
full construction, features, scores, and unopened labels remain unauthorized

## Replay result

The committed smoke-authority construction plan has SHA-256
`0c87f49f144630b769ef39aa47ac0e5c2a1207cd8769470b294cde50dcea5137`.
Both sorted private manifests have SHA-256
`5a53608613789e7411e54e877acdbf33a2fb434645255c5fb3114163764e2bad`,
and both complete path-free run reports have SHA-256
`2ab09fa711a91151fb318018aea98f7045ef86deee563ff7ca676752cb679f80`.
The public attestation is
[`constructor-smoke-observed-20260802-001.json`](../../research/sources/evidence/constructor-smoke-observed-20260802-001.json),
with SHA-256
`5f8e48fa58366c5259eb4e854a869cf145841f20ff7238427bd9038d91ae5615`.

Each root contains the same 202 recipe-addressed artifacts: 108 controlled
positives and 94 matched negatives, comprising 100 mechanism-development, 68
encoder-transfer, and 34 external-transfer cells. The artifacts total
191,654,233 bytes per root. Every checkpoint passed fresh artifact hashing,
wrapper validation, and canonical analysis-PCM validation. Both the artifact
hash-set digest and the analysis-PCM hash-set digest agree across replays.

The public result contains only aggregate counts, byte totals, recipe-level
factor counts, and set digests. It contains no source, member, group, cell,
artifact, or private-path identity. No feature or score was computed, no
external positive was generated, and no public verdict was enabled.

## Interpretation

This is evidence about deterministic benchmark construction, not detector
accuracy or codec-history identifiability. It establishes that the exact
constructor can traverse all declared construction categories on real assigned
sources and reproduce the same retained bytes and canonical PCM in two clean
roots.

## Disposition

The smoke gate passes. A separately committed correction may bind this public
attestation and the byte-identical private-manifest hash, then authorize the
one-worker, resumable full construction. Until that correction is committed,
the constructor must continue to reject full scope. Feature extraction,
candidate scoring, transfer-partition opening, external-positive generation,
and public verdicts remain separately blocked.
