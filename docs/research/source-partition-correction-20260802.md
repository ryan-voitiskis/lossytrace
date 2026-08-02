# Source-partition correction after provenance audit

Date: 2026-08-02

State: pre-freeze inventory correction; no benchmark audio or scores opened

## Decision

The proposed v2 source inventory is corrected before allocation:

1. reject Google Speech Commands v0.02 as a Tier A source candidate because
   its primary paper documents a majority OGG-to-PCM release path that cannot
   be resolved per file;
2. move already-audited RAVDESS's 24 actor groups from external transfer to
   encoder transfer; and
3. add the six fully audited FSDD v1.0.10 speaker groups to encoder transfer.

This preserves source/encoder separation without relabelling unknown-history
audio, relaxing source identity, or opening any outcome. The detailed records
are the
[`Speech Commands rejection`](speech-commands-provenance-rejection-20260802.md),
[`FSDD audit`](fsdd-source-identity-audit-20260802.md), and existing
[`RAVDESS audit`](ravdess-source-identity-audit-20260802.md).

## Corrected projection

| Partition | Before correction | After correction | Floor | Margin |
| --- | ---: | ---: | ---: | ---: |
| Encoder transfer | 172 groups / 4 domains | 102 groups / 6 domains | 100 groups / 4 domains | 2 groups / 2 domains |
| External transfer | 188 groups / 9 domains | 164 groups / 7 domains | 150 groups / 3 domains | 14 groups / 4 domains |

The corrected encoder-transfer collections are VCTK (56 groups), RAVDESS
(24), FSDD (6), TinySOL (1), and SONYC (15). The external-transfer collections
are SATP (25), Lombard Grid (54), and RWC (85 planned artist families).

The margins are intentionally narrow. They are enough to continue the source
audit, but not permission to weaken VCTK or RWC identity rules. If either
partition falls below its floor after observing those archives, add a new
provider collection under a separately documented correction.

## Storage correction

Removing the 2,428,923,189-byte Speech Commands archive and adding the
16,419,872-byte FSDD archive lowers total planned source archives from
23,237,282,258 to 20,824,778,941 bytes (19.39 GiB). The only planned archives
not yet acquired are VCTK and the five RWC audio members, totaling
18,189,508,204 bytes (16.94 GiB).

At this checkpoint the data volume reported 38,757,392,384 bytes (36.10 GiB)
free. Acquiring the remaining archive bytes would leave 20,567,884,180 bytes
(19.16 GiB), or 4,461,756,820 bytes (4.15 GiB) above the fixed 15 GiB reserve.
This is still a narrow operating margin. Continue resumable acquisition,
archive-streaming audits, one low-priority worker, and a fresh free-space
projection before every source.

VCTK was subsequently acquired and identity-verified at its existing
56-group planning contribution. Its released bytes contain 58 provider speaker
IDs, so an unapplied content-independent 28-per-gender cap preserves the
pre-correction denominator. The only source archives still outstanding are the
five RWC members, totaling 13,418,888,925 bytes (12.50 GiB).

## Validator hardening

The inventory validator now:

- treats rejected sources as a separate, non-overlapping population;
- binds the rejection report's state, provider artifact, diagnostic-only role,
  and path-free boundary;
- accepts GitHub codeload artifacts only when tag, 40-hex commit, strong ETag,
  local SHA-256, and HTTPS URL are present; and
- requires source-identity reports to repeat acquired provider identities,
  not only byte counts and archive hashes.

That final check exposed and repaired an older Lombard evidence gap: its two
strong ETags and Last-Modified values were in the inventory but not the
replayable report. A fresh archive replay produced the corrected evidence
byte-for-byte.

## Next gate

Acquire and verify every RWC audio member; VCTK is now verified. Only after the
RWC checks may source allocation, factor levels, and toolchain versions be
frozen in separate commits. No benchmark derivative, mechanism score,
candidate decision, or external-transfer evidence was opened by this
correction.
