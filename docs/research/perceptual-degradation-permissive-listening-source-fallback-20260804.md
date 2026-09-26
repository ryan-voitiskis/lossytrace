# Permissive listening-source fallback - 2026-08-04

**Status:** CC BY/CC0-only development path identified; audio, scores,
processed conditions, actual-codec generation, metrics, and listening remain
closed

## Result

ODAQ provides a narrower path that does not depend on a noncommercial or
ShareAlike decision. Its primary paper describes studio-quality stereo
references at 44.1 or 48 kHz: 14 music excerpts and 11 movie-like soundtrack
excerpts. The committed score-blind audit had already reduced that population
to every source with CC BY or CC0 terms and an uncoded or lossless origin. The
result is 16 clean-reference records: nine music excerpts and seven soundtrack
excerpts, represented conservatively as 13 upstream work groups in one ODAQ
provider stratum.

The selected records comprise 15 CC BY sources and one CC0 source. All 16
attribution notices are ready. Seven derived soundtrack mixes depend on 14
additional bound attribution records, so a future notice must include those
dependencies rather than silently replacing the provider's raw metadata.

The machine-readable
[`fallback plan`](../../benchmarks/perceptual-degradation-v1/permissive-listening-source-fallback-plan.json)
binds the existing ODAQ inventory and attribution evidence. It does not open or
download a WAV, a processed condition, or a listening-score row.

## Scientific boundary

ODAQ's paper reports 240 processed samples rated by 26 post-screened expert
listeners in two laboratories. For music, however, the five published
processing families simulate isolated artifacts that can arise in coding; they
are not actual MP3, AAC, Opus, or Vorbis encodes. The soundtrack conditions are
source-separation and remix outputs. Their published scores can later provide
a separately authorized metric sanity check for simulated artifacts, but they
cannot calibrate actual-codec audibility.

Only the clean references are candidates for a future LossyTrace development
listening population. Actual codec and production-control conditions would be
generated from those references under the frozen recipes and judged under the
separate blinded protocol. Every related remix of the same upstream work must
remain in one group.

This population improves permissive studio-music and soundtrack coverage but
does not close independent-provider transfer. It is one packaged provider
stratum, is development-only, and cannot support broad commercial-music,
all-genre, or final-validation claims. A fresh, separately sealed provider is
still required for a positive final result.

## Licence boundary

CC BY 4.0 permits sharing and adaptation for any purpose, including commercial
use, provided attribution, a licence link, and modification disclosure are
preserved. CC0 permits copying, modification, distribution, and performance,
including commercially, without asking permission. Those deeds do not warrant
that every other right needed for a particular use is cleared.

For LossyTrace, every future presentation notice must preserve the bound
creator and supplied title, link the original source and licence, identify the
codec or anchor transformation, and avoid suggesting endorsement. No NC or SA
source is admitted to this fallback.

## Next gate

A separately committed acquisition plan may bind only the 16 `reference.wav`
members by ZIP name, CRC32, compressed size, and uncompressed size. It must use
bounded HTTP Range requests, preserve 15 GiB free, keep the full archive and
all audio outside Git, and leave every processed condition and score member
closed.

The responsible human still needs to choose between this narrow one-provider
fallback and the wider NC/SA source track. A declared physical playback chain
also remains required before stimulus presentation or response collection.
