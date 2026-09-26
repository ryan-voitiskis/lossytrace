# ViSQOL dependency and SBOM disposition - 2026-08-14

## Outcome

The pinned ViSQOL-only candidate passes a bounded direct-dependency
copyright-license screen, but the existing evidence does not support a complete
binary SBOM or redistribution decision.

This is a deliberately split result:

- the production target's declared direct software dependencies all expose
  permissive redistribution terms subject to their conditions; and
- the historical builds do not retain enough sanitized evidence to prove the
  exact production-only transitive closure, binary linkage, notice bundle or
  model-asset packaging obligations.

The candidate remains technically preregisterable for internal research. It is
not selected, execution-ready or distribution-ready. No rebuild or metric
execution is authorized by this disposition.

## Direct production graph

The pinned `//:visqol` target and its workspace declare the following production
components:

| Component | Frozen version | Observed copyright-license record |
| --- | --- | --- |
| ViSQOL | `c3aa2e498e0f7f14202643594335a0b9ee40bdd9` | Apache-2.0 |
| Abseil | `215105818dfde3174fe799600bb0f3cae233d0bf` | Apache-2.0 |
| protobuf | `v3.19.1` | BSD-3-Clause |
| TensorFlow Lite | `3f878cff5b698b82eea85db2b60d65a2e320850e` | Apache-2.0 |
| Armadillo headers | `9.860.2` | Apache-2.0 plus NOTICE |
| PFFFT | `7c3b5a7dc510a0f513b9c5b6dc5b56f7aeeda422` | UCAR/NCAR permissive terms in source header |
| LIBSVM | `v324` | BSD-3-Clause |
| ViSQOL audio model | frozen SHA-256 | top-level Apache-2.0 repository record only; no separate asset notice observed |

The inspected primary records are the pinned ViSQOL
[`WORKSPACE`](https://github.com/google/visqol/blob/c3aa2e498e0f7f14202643594335a0b9ee40bdd9/WORKSPACE),
[`BUILD`](https://github.com/google/visqol/blob/c3aa2e498e0f7f14202643594335a0b9ee40bdd9/BUILD),
and [`LICENSE`](https://github.com/google/visqol/blob/c3aa2e498e0f7f14202643594335a0b9ee40bdd9/LICENSE),
plus the pinned
[`Abseil`](https://github.com/abseil/abseil-cpp/blob/215105818dfde3174fe799600bb0f3cae233d0bf/LICENSE),
[`protobuf`](https://github.com/protocolbuffers/protobuf/blob/v3.19.1/LICENSE),
[`TensorFlow`](https://github.com/tensorflow/tensorflow/blob/3f878cff5b698b82eea85db2b60d65a2e320850e/LICENSE),
[`LIBSVM`](https://github.com/cjlin1/libsvm/blob/v324/COPYRIGHT) and
[`PFFFT`](https://bitbucket.org/jpommier/pffft/src/7c3b5a7dc510a0f513b9c5b6dc5b56f7aeeda422/pffft.c)
records. The Armadillo 9.860.2 archive matched the SHA-256 already frozen in
ViSQOL's workspace; only its `LICENSE.txt` and `NOTICE.txt` members were read.

This is a copyright-license metadata screen, not legal advice or a patent,
trademark, export-control or security review.

## Why the SBOM gate remains closed

Both prior environments resolved the same projection of 46 Bazel repository
names, but that is not a component inventory. It mixes production libraries,
transitive TensorFlow dependencies, toolchains, rules, local configuration and
possibly test-only material. The historical evidence intentionally omitted the
raw Bazel resolution records because they contained ephemeral absolute paths.

The two exact binaries were not retained and have different hashes despite
zero-delta synthetic metric outputs. No sanitized `query`/`cquery`/`aquery`
closure, static/dynamic linkage inventory, CycloneDX document or bundled license
and notice set was retained. Equal synthetic scores do not prove binary or
packaging equivalence.

Consequently:

- direct declared license screening is complete;
- complete transitive dependency and model-asset review is incomplete;
- a binary-bound SBOM is unavailable;
- redistribution readiness is false; and
- the earlier successor recommendation is unchanged.

## Required future packaging evidence

If the responsible human selects the ViSQOL-only successor, a separately
authorized clean ephemeral packaging build must precede any redistribution
decision. That build must retain only sanitized evidence and produce:

1. the exact patched source and model bindings;
2. a production-only Bazel query/action closure with exact versions and hashes;
3. a binary linkage record separating static, dynamic, tool-only and test-only
   components;
4. a CycloneDX SBOM bound to the binary, model, compiler and build
   configuration;
5. a complete license and notice bundle; and
6. a separate model-asset attribution and non-copyright constraints review.

Selection would not itself authorize this build, metric execution, audio
access, score access or redistribution.

## Access and claim boundary

Only public text records and the two Armadillo software-license members were
read. The software archive was temporary and removed after hashing and member
inspection. No repository archive, test audio, model bytes or binary was read;
no software was built; and no metric, retained audio, score, sealed evidence,
human collection or no-reference training was opened. The public CLI remains
verdict-free.

Machine-readable artifacts:

- [`direct dependency observation`](../../research/toolchains/evidence/perceptual-degradation-visqol-direct-dependency-license-observation-20260814-001.json)
- [`dependency and SBOM disposition`](../../benchmarks/perceptual-degradation-v1/visqol-only-dependency-sbom-disposition.json)
- [`validator`](../../scripts/validate-perceptual-degradation-visqol-dependency-sbom-disposition.py)
