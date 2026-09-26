# Pending-source provenance disposition - 2026-08-14

**Status:** MusicNet and FSD50K are rejected for truth-bearing clean-reference
roles under the current public record. This is not a claim that either dataset
contains lossy audio. No audio was downloaded or opened, no exact member was
selected, and no metric, score, listener response, sealed evidence, or
no-reference training was accessed.

## Outcome

The only aggregate provider-allocation sensitivity that passed arithmetically
depended on both provenance-pending candidates. Neither can cross the stricter
scientific gate:

| Candidate | Public record establishes | Public record does not establish | Disposition |
| --- | --- | --- | --- |
| MusicNet | 330 CC-licensed or public-domain recordings delivered as PCM WAV, with track-level source metadata | A complete recording-to-delivered-PCM transformation chain or absence of prior lossy coding for every track | reject as truth-bearing clean reference |
| FSD50K | 51,197 Freesound clips delivered as 16-bit 44.1 kHz mono PCM, with clip-level uploader and licence metadata | Original upload container/codec or a complete capture-to-delivered-PCM chain for every clip | reject as truth-bearing clean reference |

The official [MusicNet record](https://zenodo.org/records/5120004) identifies
the delivered PCM WAV collection and upstream source families. Its exact
330-row metadata file contains composition, source, transcriber, and duration
fields, but no original acquisition container or codec field. The public paper
describes the dataset and score-alignment construction, not a complete
recording encoding chain.

The official [FSD50K record](https://zenodo.org/records/4060432) identifies
the mixed clip-level licences and delivered PCM format. The
[accepted paper](https://arxiv.org/abs/2010.00475) states that original
multichannel clips are downmixed and that the release is uncompressed 16-bit
44.1 kHz mono PCM. Its released per-clip metadata has exactly five fields:
description, licence, tags, title, and uploader. It has no original upload
container or codec field.

## Why container inspection cannot repair this

The target estimand is degradation, not prior codec history. A WAV or PCM
container can hold audio that was previously lossily coded. Conversely, a
history detector cannot certify that a decoded PCM reference is clean without
making the experiment's truth labels depend on the class of inference the
experiment is supposed to evaluate. That would be circular.

Creative Commons permission answers a reuse question; it does not establish
an acquisition encoding chain. Therefore unknown origin cannot be silently
labelled a clean natural negative.

## Preserved future roles

This disposition does not assert that either dataset is actually lossy and
does not reject every future use. A separately frozen design could use them as
provenance-unknown stress or abstention cases, with applicable item-level
licence filtering and without assigning clean/degraded truth. Such a role
would not repair the truth-bearing source manifest.

## Consequence and next decision

Zero pending providers and zero pending groups are promoted. The remaining
exact-member-audit candidate pool still has seven providers and only seven
real-music groups; no four-partition truth manifest is feasible or frozen.
ODAQ remains one-provider development plumbing and cannot establish truth or
transfer.

A responsible human must choose one of three source successors:

1. qualify additional permissive providers with non-circular original coding
   provenance;
2. preregister a narrower primary-domain claim supported by qualified
   providers; or
3. reject the current truth-source design without promoting that candidate
   stop to a full-objective scientific negative.

This choice is independent of the GstPEAQ successor decision. This checkpoint
authorizes neither choice and does not broaden the existing ODAQ authority.

Machine-readable artifacts:

- [`public provenance observation`](../../research/toolchains/evidence/perceptual-degradation-pending-source-public-provenance-observation-20260814-001.json)
- [`source disposition`](../../benchmarks/perceptual-degradation-v1/pending-source-provenance-disposition.json)
- [`validator`](../../scripts/validate-perceptual-degradation-pending-source-provenance-disposition.py)
