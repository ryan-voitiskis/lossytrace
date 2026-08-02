# VCTK clean 56-speaker source-identity audit

Date: 2026-08-02

State: source-identity evidence only; no source allocation or factor freeze

## Outcome

The official `clean_trainset_56spk_wav.zip` release is suitable as a Tier A
confirmed-PCM encoder-transfer candidate, but its provider count is not
literal. The archive contains 23,075 canonical clean WAVs from 58 VCTK speaker
identifiers. The bound 56-speaker log and transcript archive independently
expose the same 23,075 utterance keys and the same 58 speakers. The relevant
rows in the provider's VCTK speaker table are balanced at 29 female and 29 male,
not the paper's stated 28 and 28.

This audit does not opportunistically increase the proposed contribution from
56 to 58 groups. The hash-bound source rules preregister a content-independent
cap of 28 speaker identifiers per provider gender. The cap will be applied only
at source freeze, before any benchmark audio or mechanism score exists. No
selected or excluded speaker list is produced here.

The path-free evidence is
[`research/sources/evidence/vctk-clean-56spk-2017-observed-20260802.json`](../../research/sources/evidence/vctk-clean-56spk-2017-observed-20260802.json).
It is reproduced by
[`scripts/audit-audio-integrity-v2-vctk.py`](../../scripts/audit-audio-integrity-v2-vctk.py)
under the hash-bound
[`benchmarks/audio-integrity-v2/vctk-source-group-rules.json`](../../benchmarks/audio-integrity-v2/vctk-source-group-rules.json).

## Provider and byte bindings

The derivative is the University of Edinburgh DataShare item
[`10.7488/ds/2117`](https://doi.org/10.7488/ds/2117), licensed under CC BY 4.0.
The audio is bound to DSpace bitstream
`386ac199-5d34-402f-8112-2a123577dd57`:

| Field | Value |
| --- | --- |
| Filename | `clean_trainset_56spk_wav.zip` |
| Bytes | 4,770,619,279 |
| Provider MD5 | `c351cbc9db30e41686c988c19f0e1475` |
| Local SHA-256 | `c7a5580c1d96b52886ca7ca080cc1a21ae3ee1cb8eae4903af6d4bb796f90441` |
| Strong ETag | `"c351cbc9db30e41686c988c19f0e1475"` |
| Last-Modified | `Mon, 21 Aug 2017 10:33:40 GMT` |

Supporting provider bytes are also bound rather than cited only by mutable
landing-page prose:

| Artifact | Bytes | Provider MD5 | Local SHA-256 |
| --- | ---: | --- | --- |
| `logfiles.zip` | 115,932 | `0d16f5b6afe12d64238d1e4a0e6ff6e8` | `ab37c41f31bc2b6c204cc10c8e5bb8bde800307fdb49f277e366d986fefc9e39` |
| `trainset_56spk_txt.zip` | 12,918,133 | `8aa183b7cfbf148b9558302a0c0c3771` | `1bd933130da4f5b362536dccdc068ec9e01b0ff8787303c19780405b99a9f175` |
| VCTK v0.80 README | 2,790 | `6d59a65471c0e9ff108a41f8eb15e6bc` | `f33acbe652f50e3c4d3afe02665a2cf3b08cb34257bec41e06dd911cda3ae8db` |
| VCTK speaker table | 3,712 | `1a5b42650b13061a67e935aeb08b31ad` | `daa68d27a01418d113ac79e6914017beeded4e7de65d03f7705f9d81295da236` |
| CC BY 4.0 `license_text` | 17,416 | `2946b37a07baeba80cea628909e28cae` | `b34e17103bfb246f2549fc82a279e6ba28834e0cb42f76a92efc14b72e3a3723` |
| SSW 2016 primary paper | 755,633 | not supplied | `3dbb7eb3351729a45b87bed18c8a92b69e7e3ea333c5145f04db7979e27337ac` |

Additional reproducibility bindings:

- source-group rules SHA-256:
  `862fa45181cb5118a60f4dbc45e70e18feb0c6bfa17f9445ec8bcc7728544c81`;
- path-free evidence SHA-256:
  `6ccfb8b6b3d81750226be33aa41143f3773d0236ed8120982c8cf427a038cac3`;
  and
- two complete audit replays were byte-identical.

The Edinburgh endpoint was too slow for a practical full transfer. The first
170,790,912 bytes acquired from that endpoint were compared with the same
prefix from a public transport mirror and had identical SHA-256
`6717459a30a21b89f9dd52975bb24aff59017ebff1273f9b418e8b3d4be71958`.
Only transport then moved to the mirror. The reconstructed whole file still had
to match the official DSpace byte count and MD5; the mirror did not become a
provenance authority.

## Archive observations

| Property | Observed value |
| --- | ---: |
| Canonical audio WAVs | 23,075 |
| Speaker identifiers | 58 |
| Files per speaker | 292 to 481 |
| Gender balance | 29 female / 29 male |
| Canonical transcript keys | 23,075, exactly equal to audio keys |
| Log keys | 23,075, exactly equal to audio keys |
| Distinct PCM digests | 23,075 |
| Repeated-PCM groups | 0 |
| Audio format | mono 48 kHz signed 16-bit integer PCM |
| RIFF layout | one 16-byte `fmt ` chunk and one `data` chunk; no ancillary chunks |
| Frame range | 56,325 to 779,850, or about 1.17 to 16.25 seconds |
| Uncompressed WAV-member bytes | 6,578,059,372 |
| Encrypted or special archive members | 0 |

The shortest member is `p275_226.wav`; the longest is `p271_023.wav`. These
identities describe the archive and do not select either utterance. Every clean
WAV remains selection-eligible at this stage because no exact PCM digest is
repeated.

The transcript ZIP also contains 23,076 macOS AppleDouble sidecar files. They
are CRC-checked and counted, but they are not transcript identities. There are
no other unexpected regular members.

## Why the released count is 58, not 56

This is not inferred from a single filename listing:

- the audio ZIP central directory has 23,075 canonical
  `clean_trainset_56spk_wav/pNNN_NNN.wav` members from 58 prefixes;
- the exact log has 23,075 unique rows from those same 58 prefixes;
- the transcript ZIP has 23,075 canonical text members with exactly the same
  utterance keys; and
- every used prefix resolves in the bound VCTK speaker table.

The exact speaker subset has nine provider accent labels and is balanced 29/29
by gender. The primary
[`SSW 2016 paper`](https://doi.org/10.21437/SSW.2016-24) instead describes a
56-speaker, 28-female/28-male collection from Scotland and the United States.
Neither the paper nor the provider record identifies two released prefixes as
accidental additions. Guessing which two were intended would therefore be an
unverifiable source decision.

The base VCTK v0.80 README itself says 109 speakers, while its bound speaker
table has 108 rows. This separate discrepancy does not break the derivative
identity: all 58 released speaker prefixes are present, and the other 50 table
rows are recorded as unused metadata rather than silently discarded.

## Conservative 56-group rule

At source freeze, and not before, speakers will be ranked separately within
each provider gender by ascending SHA-256 of:

```text
UTF-8("lossytrace-v2-vctk-provider-count-cap-20260802" + NUL) || UTF-8(speaker_id)
```

The first 28 identifiers per gender will be retained. Speaker identifier is
only a digest-collision tie break. This rule is:

- independent of waveform content, duration, utterance count, accent, codec
  measurement, and any future outcome;
- fixed before source allocation; and
- sufficient to preserve the preregistered 56-group denominator without
  pretending the released archive has only 56 identities.

The cap's result is deliberately absent from this evidence. Publishing or
using that result now would collapse the distinction between an identity audit
and the later source freeze.

## Recording and processing boundary

The bound VCTK v0.80 README reports a common recording setup: DPA 4035
omnidirectional microphone, 96 kHz at 24 bits, and a University of Edinburgh
hemi-anechoic chamber. It then documents conversion to 16 bits, downsampling to
48 kHz using a tool named in that README as `STPK`, and manual endpointing.

The primary SSW paper says the clean waveforms were subsequently normalized
and that leading and trailing silence segments longer than 200 ms were trimmed
before noisy derivation. Those operations are PCM-domain, but they mean these
files are not untouched microphone masters. Normalization, trimming, original
48 kHz bandwidth, speaker, utterance, and provider identity must remain source
factors. The noisy derivatives are never independent masters.

## Grouping and independence limit

The source and partition grouping unit is the provider VCTK speaker
identifier. A later allocation may select at most one bounded reference excerpt
per retained speaker. All retained speakers remain inside one provider stratum
because they share one recording collection and one clean-waveform processing
path; 23,075 utterances do not establish 23,075 independent export lineages.

No benchmark derivative, retained-speaker allocation, factor setting,
mechanism score, candidate decision, or held-out label was opened by this
audit. After this checkpoint, the only remaining pre-freeze source-identity
gate is the five RWC audio archives. After redundant VCTK transport ranges were
removed, 33,496,936,448 bytes (31.20 GiB) remained free. The 12.50 GiB RWC
acquisition would leave about 3.70 GiB above the fixed 15 GiB reserve, so the
one-source, resumable, streaming-audit boundary remains mandatory.
