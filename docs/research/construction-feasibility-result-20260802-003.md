# Factorial benchmark v2 construction-feasibility result 003

Date: 2026-08-02

State: two header-only audits are byte-identical; construction is not
authorized because 11 assigned groups violate frozen transform minima; no
waveform sample, benchmark audio, feature, score, or unopened label was read

## Replay result

Both complete private audits have SHA-256
`9a4bbfcaa3742b1d665e2738547fd1ffaf74b2a0c245ed063610e8414f271a6c`.
Both path-free run aggregates have SHA-256
`ccc22f3120d6c688f62fcc36f777e0246081c030f1d796faed6dd6a02630e844`.
The attested public aggregate is
[`construction-feasibility-observed-20260802-003.json`](../../research/sources/evidence/construction-feasibility-observed-20260802-003.json),
with SHA-256
`2791c0e5c64bffae89412418693295be7b0ddd4ce8ad18eb323106bbe09bd3b4`.

The audit verified all bound source archives and the 793 exact selected source
headers. All sources are FLAC or uncompressed PCM, and all have one or two
native channels. Channel preconditioning is therefore feasible for every
group.

## Duration failures

Eleven unique assigned groups fail at least one predeclared transform minimum:

| Partition | Source domain | Transform | Unsupported assigned groups |
| --- | --- | --- | ---: |
| encoder transfer | home-recorded bandwidth-limited digit speech | 3 s duration prefix | 4 |
| encoder transfer | home-recorded bandwidth-limited digit speech | 250 ms head trim | 3 |
| encoder transfer | studio speech | 3 s duration prefix | 3 |
| external transfer | laboratory Lombard speech | 3 s duration prefix | 3 |

One digit-speech group fails both minima, so the four row counts represent 11,
not 13, unique groups. All six selected digit-speech groups are under one
second. Encoder transfer also contains 36 studio-speech groups between one and
three seconds. External transfer contains 50 Lombard-speech groups between one
and three seconds. Development sources are all at least six seconds.

These failures are construction constraints, not detector outcomes. They do
not justify padding, truncating a transform below its declared minimum,
dropping a difficult source domain, or silently choosing replacements after
seeing a score.

## Disposition

Construction remains stopped. The narrow correction is to bind this private
header audit and apply the already-frozen identity/domain ranking within the
set of groups that meet each transform's declared minimum. Source allocation,
all-source codec anchors, nonanchor settings, transforms without duration
minima, and every score boundary remain unchanged.

That feasibility-only assignment rule must be committed and replayed twice
before construction. Mechanism scoring and transfer-label opening remain
unauthorized.
