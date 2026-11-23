# Finished-music source intake, 23 November 2026

The September design still hashes to `8bd18d1c1a813ad91e90beac9d01909ff6d954b6e3fe53249b88a3a3093b1c57`. November's single-file pilot tested ranking on constructed synthetic sources. The release experiment calls for matched non-codec interventions on independently grouped finished music. Its source allocation and execution freeze remain outstanding. The local inspector RC tag resolves to `4ca4384dfa897bf68f968deddb6a72e083f3ea90`.

## RareTunes

The archive describes making first-generation WAV transfers of donated material, keeping the WAVs and depositing them on the Internet Archive. It also links externally hosted material. Its general terms mention educational and non-commercial use, with additional conditions on remixing and commercial use. Assess rights and lineage at item level. [Curator FAQ](https://raretunes.org/faq/)

The Internet Archive advanced search for `collection:raretunes AND mediatype:audio` returned all 499 distinct identifiers in one page (2,000 requested; sorted by identifier ascending). Fields requested were identifier, creator, licenseurl, title, source and date. There were 134 distinct nonempty literal creator values and four missing values. These figures precede artist alias, session, shared-work and cross-collection grouping. The license URLs indicated 254 NC-SA, 240 NC-ND, one BY-SA, two public-domain-related labels and two missing labels. This is an inventory of declarations only. NC records can warrant separate research-use review.

Reviewed the individual metadata of all three records bearing BY-SA or public-domain labels. Each lists an original WAVE of over 30 seconds; none states the native sample rate, depth and channels for that object. No audio was requested.

| Archive identifier | Item-level evidence | Outstanding qualification |
| --- | --- | --- |
| [raretunes-mac-fadyen-adram](https://archive.org/metadata/raretunes-mac-fadyen-adram) | John MacFadyen, *A dram afore ye go*. The description identifies a Glasgow recording from about 1958, issued on Gaelfonn LP STC 6001. A 57.74-second original WAVE carries Archive MD5 `f8167a373496dfad99786885fd5f04b4`; the item declares a Public Domain Mark. | Strongest analogue-source lead here. Check rights for the actual transfer and underlying material, eligible technical format, and performer/session/work overlap with consumed metadata before allocation. |
| [cuffe_hoy_eydmann_session1](https://archive.org/metadata/cuffe_hoy_eydmann_session1) | *Bonawe Highlanders*, an Edinburgh house performance credited to Tony Cuffe, Stuart Eydmann and Derek Hoy. Original WAVE, 152.58 seconds, Scottish BY-SA declaration. | The specific recording medium and path to this transfer remain unresolved. All three performers must be linked for grouping. [Performer record](https://raretunes.org/derek-hoy/) |
| [raretunes_203_joe-hill](https://archive.org/metadata/raretunes_203_joe-hill) | Paul Robeson, *Joe Hill*. Original WAVE, 177.68 seconds, legacy public-domain URL. The notes discuss a film depicting a performance. | The object description does not identify the medium actually used for this transfer. Song, film and digitization provenance need separate review. [Curator record](https://raretunes.org/paul-robeson/) |

Raw metadata is on schwarz in `lossytrace/validation/source-metadata-20261123-001`. SHA-256 values bind the precise responses.

| File | SHA-256 |
| --- | --- |
| index.json | 920144ded2636de299155f347e194267d65a2656337e51f7ef7d5dd698cc3da2 |
| raretunes-mac-fadyen-adram.json | b83a0bbb827e18cfd632101dc17240a867c3f6fd9d892f85f70c48cd8c12edfa |
| cuffe_hoy_eydmann_session1.json | 89eb0cd2bfc39524c637c980dddd4f8c87c920f9774a8f73bb50097ebb36a118 |
| raretunes_203_joe-hill.json | ecbb59e70954348042135d06e8da8599f876f3394ed1d7bc99af6e3a5821b57b |

## Other routes

Two sampled UCSB cylinder music records describe the process for requesting WAVs and a transfer use fee. Public MP3 access does not qualify their PCM masters for the present workflow. [UCSB record 12412](https://alexandria.ucsb.edu/lib/ark%3A/48907/f3m32tsd) · [UCSB record 4131](https://alexandria.ucsb.edu/lib/ark%3A/48907/f3d50kp7)

Independently authored electronic music may offer a different source stratum. A CC0 submission links four editable original BeepBox scores by one creator. These count as at most one component. The reproducible route would require checking synthesis inputs, renderer, complete-work duration, credits and prior consumption before rendering. The MP3 previews would not serve as clean controls. [Creator submission](https://opengameart.org/content/four-original-midi-loops)

## Extended item-level screen

Retrieved all 254 NC-SA item metadata records into the snapshot's `nc-sa/` directory. The sorted identifier-and-response digest is `d4341face274e60317f5bd484af9b537f956ac3a1b3d409671684a7b684916a9`. Replay the screen with `python3 scripts/music_verdict_raretunes_metadata.py /Volumes/schwarz/lossytrace/validation/source-metadata-20261123-001`. All 254 identities matched the index. Of these, 252 listed at least one original WAVE. Forty had selected cataloguing cues such as a record matrix number or an explicit source LP, covering 25 distinct nonempty creator-field values. None matched the separately defined narrow physical-medium expression. These text filters only prioritize manual investigation and can miss valid sources.

Checked the first eight shortlisted identifiers in lexical order. Examples include Adam Rennie's *Primrose Polka* (Parlophone F.3445, matrix CE 14038, 150.67 seconds) and Molendinar's live East Berlin recording (February 1979, Amiga 8 45 169, 123.8 seconds). The archive identifies pianist Gerald Moore on the Isobel Baillie item, illustrating why a creator field alone undercounts links between items. Paul Robeson appears in both license screens. These records materially improve the analogue-source shortlist; item-specific transfer, rights, technical and grouping checks still precede allocation. [Rennie item](https://archive.org/metadata/PrimrosePolka) · [Molendinar item](https://archive.org/metadata/raretunes_257_paddys-leather-breeches) · [Baillie item](https://archive.org/metadata/raretunes_274_coming-through-rye-2)

This pass admits zero components. Next intake work can compare the shortlist against consumed metadata, verify particular transfers and clarify which uses the published terms already support. Independently authored project exports provide a second discovery route. This single archive could contribute only one provider stratum.
