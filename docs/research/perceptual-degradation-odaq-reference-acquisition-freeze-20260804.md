# ODAQ reference-acquisition metadata freeze - 2026-08-04

**Status:** exact reference-member metadata frozen; source track unselected;
audio acquisition, processed conditions, scores, metrics, stimuli, and listening
remain unauthorized

## Result

The metadata-only ODAQ reference freeze ran twice against the bound
1,048,071,792-byte provider ZIP in separate temporary directories. Each replay
made three bounded HTTP Range requests totalling 85,617 bytes and opened only
the ZIP central directory. The two complete plans and the committed
[`freeze`](../../benchmarks/perceptual-degradation-v1/odaq-reference-acquisition-freeze.json)
are byte-identical with SHA-256
`1a39f50013a4274f60ca7c1771ebad22dcafda6950db87d2ffe4acdfb58ab0e7`.

No ZIP member payload was opened. In particular, no audio member, processed
condition, licence or disclaimer member, or listening-score member was read.
The two temporary plan directories were moved to recoverable Trash after the
comparison.

## Frozen population

Exactly 16 `reference.wav` members are bound by public folder/source ID,
basename, CRC32, compressed bytes, uncompressed bytes, ZIP compression method,
artifact-family code, and licence-record IDs. Together they occupy 46,721,638
compressed bytes and 54,633,154 uncompressed bytes. The selection contains:

- seven movie-like soundtrack references from the ODAQ dialogue-enhancement
  trial family;
- nine music references across low-pass, pre-echo, spectral-hole, tonality-
  mismatch, and unmasked-noise trial families; and
- no processed condition, anchor, training item, or result file.

The family codes identify the ODAQ trial folders from which a clean reference
is selected. They are not degradation labels for the references and cannot be
used as model inputs or quality targets.

## Execution boundary

The freeze is not an acquisition authorization. It records enough metadata for
a future bounded extractor to request only the selected compressed ZIP ranges,
verify every member before an atomic private write, and avoid persisting the
full archive. It does not select the permissive source track for the study.

Reference acquisition still requires a successor authorization after the
responsible human chooses the narrow CC BY/CC0-only path and declares a
qualified playback chain. Until then, all audio, processed conditions, scores,
actual-codec generation, metrics, stimulus generation, participant contact,
and response collection remain closed.
