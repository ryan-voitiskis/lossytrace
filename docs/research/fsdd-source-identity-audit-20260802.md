# FSDD v1.0.10 source-identity audit

Date: 2026-08-02

State: source-identity evidence only; no source allocation or factor freeze

## Outcome

The exact Free Spoken Digit Dataset v1.0.10 tag contributes six conservative
speaker groups to the proposed encoder-transfer partition. The acquired
archive contains the complete six-speaker by ten-digit by fifty-repetition
grid: 3,000 WAVs, 500 per speaker, with 3,000 distinct PCM payloads.

All audio is mono, 8 kHz, signed 16-bit integer PCM. The repository's bound
collection code instructs contributors to record and export WAV in Audacity at
an 8 kHz project rate, then uses SciPy to read, split, trim, and write PCM WAV
clips. That is a documented PCM-domain release path, not an inference from the
file extension alone.

The path-free evidence is
[`research/sources/evidence/fsdd-v1.0.10-observed-20260802.json`](../../research/sources/evidence/fsdd-v1.0.10-observed-20260802.json).
It is reproduced by
[`scripts/audit-audio-integrity-v2-fsdd.py`](../../scripts/audit-audio-integrity-v2-fsdd.py)
under the hash-bound
[`benchmarks/audio-integrity-v2/fsdd-source-group-rules.json`](../../benchmarks/audio-integrity-v2/fsdd-source-group-rules.json).

## Provider and artifact bindings

The official
[`Jakobovski/free-spoken-digit-dataset` repository](https://github.com/Jakobovski/free-spoken-digit-dataset)
tag `v1.0.10` resolves to commit
[`d6938f9bf1545aa66d8489fc9f1385a7abd64282`](https://github.com/Jakobovski/free-spoken-digit-dataset/tree/d6938f9bf1545aa66d8489fc9f1385a7abd64282).
The codeload archive is bound by tag, commit, strong ETag, size, local digest,
and ZIP CRC:

| Field | Value |
| --- | --- |
| Filename | `free-spoken-digit-dataset-1.0.10.zip` |
| Bytes | 16,419,872 |
| SHA-256 | `c680098f5d2355ba7cc4bd8b0ca9e0a24c00ebe3b4c552208889a4d28d4fbc2b` |
| Strong ETag | `"248f3f5caf01524ccd38bd74a1dac661854fd431de2abae9757c49b9fe1142f7"` |
| Rules SHA-256 | `8f7dce1cc369fffcc9f24b18b0fd8af9bf071d9198135698de33c931699d6677` |
| Evidence SHA-256 | `80ce2326afac2baa85f55ab6828615632352fbbc02c4d0809cd30f73cc5f75ec` |

The audit also binds the exact README, metadata, recording prompt,
split/label code, and trimmer bytes. The relevant contributor path is visible
in the pinned
[`say_numbers_prompt.py`](https://github.com/Jakobovski/free-spoken-digit-dataset/blob/d6938f9bf1545aa66d8489fc9f1385a7abd64282/acquire_data/say_numbers_prompt.py)
and
[`split_and_label_numbers.py`](https://github.com/Jakobovski/free-spoken-digit-dataset/blob/d6938f9bf1545aa66d8489fc9f1385a7abd64282/acquire_data/split_and_label_numbers.py).

## Archive observations

| Property | Observed value |
| --- | ---: |
| Regular files | 3,012 |
| Audio WAVs | 3,000 |
| Non-audio code/docs | 12 |
| Speakers | 6: `george`, `jackson`, `lucas`, `nicolas`, `theo`, `yweweler` |
| Digits per speaker | 10 |
| Repetitions per speaker-digit cell | 50 |
| Distinct PCM digests | 3,000 |
| Duplicate PCM groups | 0 |
| Format | mono 8 kHz signed 16-bit integer PCM |
| RIFF chunks | standard `fmt ` and `data` only |
| Frame range | 1,148 to 18,262 |
| Uncompressed audio-member bytes | 21,128,848 |

The shortest member is `recordings/6_yweweler_3.wav`; the longest is
`recordings/9_theo_16.wav`. These identities describe the archive and do not
select either file.

## Grouping and factor boundary

The repository speaker identifier is the source and partition grouping unit
across every digit and repetition. A later freeze may select at most one
bounded reference excerpt per speaker. It must preserve digit, repetition,
original 8 kHz bandwidth, and provider identity, and it must keep all six
speakers inside one FSDD provider stratum.

The public repository does not identify microphone, room, recording date,
Audacity version, or contributor-specific export settings. Those properties
must remain unknown; the complete grid does not make its cells independent
recording chains. The 8 kHz bandwidth and PCM trimming are explicit hard
negative factors, not evidence of prior lossy encoding.

No benchmark derivative, source selection, mechanism score, candidate
decision, or transfer evidence was opened by this audit.
