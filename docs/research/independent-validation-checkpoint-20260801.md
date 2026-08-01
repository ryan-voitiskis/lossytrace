# Independent validation checkpoint — 2026-08-01

**Decision:** do not promote a detector or open either sealed holdout. Keep
LossyTrace at evidence schema `1`, measurement feature version `0`, and
`public_verdict_enabled: false`.

## Scope and reproducibility

The repository, public GitHub state, and `origin/main` agreed at
`3526bf5a49039466203f66dcca439e0e46c59ab8`. Mandatory CI was green for that
exact commit. The only release was the experimental `v0.1.0-alpha.1` tag at
`22b8af8`; its downloaded artifacts, checksums, licences, SBOM, and
attestations verified. No release or public-interface change was made.

The retained corpus inventory and relocation record verified before scoring:
110 checks passed, comprising 46 file hashes, 63 semantic commitments, and one
explicit informational relationship for a historical archive record whose own
hash was never committed. The corpus occupied about 90 GB. The run started
with 56 GiB free and finished with 55 GiB free, above the 15 GiB reserve.

The local toolchain was Rust/Cargo 1.94.0, Python 3.14.6, FFmpeg 8.1.2,
Zstandard 1.5.7, jq 1.8.2, and GitHub CLI 2.97.0. Runs used one low-priority
worker. Mandatory CI remains synthetic/public-data only.

## Frozen method

Promotion criteria and the exact-transform ablation were fixed before the new
scores were inspected. The primary requirements were zero Tier A hard-negative
alerts; a one-sided 95% Wilson false-positive upper bound no greater than 2.5%;
at least 75% support; at least 90% supported recall with a one-sided lower
bound of 85%; no failing source domain; two independent evidence families;
container, gain, silence, trim, duration, and sample-rate robustness; and p95
runtime overhead no greater than 10% without a second decode.

The observed baseline contained 5,280 cases from 597 source groups: 1,734
genuinely lossless negatives and 3,546 controlled positives. It included real
and synthetic material, low-pass and naturally bandwidth-limited controls,
low-rate sparse instruments, full mixes, public Tier A recordings, lossy
original histories, and controlled codec-to-lossless transcodes. The run was
sharded deterministically by source group into 32 resumable shards. The 280
future SQAM cases and release holdout stayed sealed.

The only candidate direction was the pinned ISO Layer III exact-hybrid probe.
Its archived front end replayed 120 cases from 24 groups with zero mismatches;
the largest magnitude difference was `2.220446049250313e-15`, within the
predeclared `1e-10` tolerance. A0–A4 were then evaluated on 2,261 observed
cases: all 1,734 negatives and 527 MP3-128 controlled positives. Thresholds
were selected strictly above the maximum edge-gated training negative in each
leave-one-source-domain-out fold. Public PCM parents and transcodes were one
canonical fold family to prevent source leakage.

## Results

Feature version `0` remains a measurement, not a classifier. High-band
features were supported on 1,127/1,734 negatives and 2,435/3,546 positives;
transform features were supported on 1,720/1,734 and 3,500/3,546 respectively.
Transform-alignment positive-minus-negative deltas were positive in 460 and
negative in 131 of 591 eligible groups, so separation was not domain-stable.
Spectral-edge drop had a positive median paired delta of 1.106 dB, while edge
persistence had a negative median delta of 0.000433. Naturally band-limited
negatives overlapped both families. Median runtime overhead was 224.1% and p95
was 287.3%, failing the frozen 10% gate.

No exact-hybrid row survived:

| Row | Negative alerts (cases/groups) | MP3 support | Supported recall | Wilson lower | Outcome |
| --- | ---: | ---: | ---: | ---: | --- |
| A0 archived statistic | 2 / 2 | 100.0% | 23.3% | 20.4% | false-positive and recall failure |
| A1 subband-relative | 2 / 1 | 99.2% | 16.3% | 13.8% | false-positive and recall failure |
| A2 time median | 2 / 1 | 86.3% | 16.0% | 13.4% | false-positive, support, and recall failure |
| A3 phase stable | 1 / 1 | 86.0% | 14.3% | 11.9% | false-positive, support, and recall failure |
| A4 content guarded | 1 / 1 | 85.2% | 14.5% | 12.0% | false-positive, support, and recall failure |

All five rows had zero recall in the 36-group DEMAND/MAESTRO fold and the
48-group public Tier A fold. A0 reached 62% on MUSDB and 70% on the private
full-mix domain, but only 0.5–1.9% on the two sparse NSynth domains. Later
normalization and aggregation reduced MUSDB recall and support without fixing
transfer. This confirms content/source dependence rather than a threshold
problem; changing a threshold or combining rows after inspection would not be
defensible.

A separate ephemeral container audit used 14 deterministically selected source
groups across seven observed domains and four codec families. Across all 56
codec/source combinations, the ten feature fields matched exactly between
FLAC, WAV, and AIFF wrappers. Lossy-original versus wrapper feature objects did
not match exactly for any of the 42 supported codec/source combinations: the
public decoder and FFmpeg decode paths produce measurably different PCM. Opus
originals could not be analyzed because Symphonia 0.5 has no Opus decoder; the
Opus intermediate was hash-committed and its three lossless wrappers matched
exactly. This is a decoder-support limitation, not provenance evidence.

## Failure modes and limitations

- The observed evaluation is disciplined source-domain transfer, but it is not
  fresh independent validation: its labels were consumed by earlier research.
- There is no surviving score to calibrate, no probability, and no second
  independent evidence family.
- Gain, trim, leading-silence, duration, and candidate runtime checks were not
  run after the earlier false-positive/recall stop rule fired.
- The standalone eight-phase probe took a median 301 ms and p95 334 ms per
  case. It performs a second decode and is research-only.
- AAC, Opus, Vorbis, high-bitrate histories, encoder diversity, and broad
  provenance remain outside any positive claim.
- The future codec-only subset and release labels remain unopened. A promotion
  attempt still requires at least 150 fresh, independent Tier A groups and an
  unseen content domain and encoder.

## Evidence commitments

Private manifests, case rows, paths, audio, and checkpoints remain outside
Git. The following hashes bind the retained run while allowing this report to
stay path-free. After the implementation was frozen, all three path-free
aggregates regenerated byte-for-byte from their sealed raw inputs:

| Artifact | Schema/state | SHA-256 |
| --- | --- | --- |
| retained-inventory verification | schema 1 | `13fdcff3914bc5ce61b04abeed600373f3675c9013bb49bd54636082963abbc1` |
| observed manifest | schema 1 | `e19b5b408fedf348fa9b6499d5cdd1b6b734d84b19b895d5b0a528f0c4423b7a` |
| baseline raw report | schema 1 | `4c9ddedc847801a8db3a4bdda318faa7a15e478ee4698bd17a2c3d47287aacc9` |
| baseline path-free aggregate | schema 2 | `e41e2da69c78a8f34dfcdcc3b8c3f8d1b9bac5f28229b8d355b53eab74679e1d` |
| exact-hybrid raw report | schema 1, probe schema 2 | `18703080e8200e98c55fa92382fb2ff93d30a5612993291978f39d6a7d3b3829` |
| exact-hybrid replay | schema 1 | `50c193dc13167a7cfe7c0dc8eade9a201978e2d8546c584d6a7c8205e21ca12b` |
| exact-hybrid path-free evaluation | schema 1 | `fd377281039492a456f0ea6e89e7b28928b30e0d4026f38ea3da14314a03c430` |
| equivalence manifest | schema 1 | `1aa859898987296228b456ab61f5d66ffb96f809ce90ed9336d89cd96ced5f43` |
| equivalence raw report | schema 1 | `6ce23f67d9d58d8b9a5c024f103e9ba7f5fb730250992184372af0f0000b5a4c` |
| equivalence path-free aggregate | schema 1 | `2f98cf21f79394604067877f590ca1f4bc4f62a4bce4ef686194557cc36352b5` |

## Recommended next decision

Stop threshold and exact-hybrid tuning. Retain the reproducible corpus,
relocation verifier, sharded baseline, exact replay harness, and container
audit as research infrastructure, but do not integrate the probe into the
public measurement path. Resume detector work only for a materially new,
explainable signal that can supply two genuinely distinct evidence families;
freeze it before scoring, then acquire and seal fresh transfer data before
opening either retained holdout. The public CLI should continue to emit only
experimental measurements.
