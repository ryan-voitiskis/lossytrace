# Checking independence before splitting finished music

The 109 shortlisted tracker works form 49 provisional artist or work groups when grouped in isolation. The full snapshot and the recorded lineage review give 46. Three excluded collaborations account for the difference. *sensory premonition* links gotoandplay to tennisers, and *flattened* links tennisers to bigSmonkinLoser. *dream chaser* links 2a03fox to TristEndo. Each artist has shortlisted solo work. A split made from the 109 rows alone could therefore put related music on opposite sides. Both the study graph and the earlier independent catalogue grouper reproduce 46 from the retained records. These are provisional discovery counts. [sensory premonition](https://battleofthebits.com/arena/Entry/sensory+premonition/30550/) · [flattened](https://battleofthebits.com/arena/Entry/flattened/33531/) · [dream chaser](https://battleofthebits.com/arena/Entry/dream+chaser/45265/) · [Original lineage review](opl-lineage-review-20261123.md)

The metadata preflight can now include identity records for tracks outside the allocation. Compute connected groups from the complete supplied graph before counting selected representatives. A reference can join two performers, connect a recording to a known remix or record a previous use. References contribute zero observations to train, selection, calibration, evaluation or provider quotas. Cross-partition links block the allocation. A historical reference marked consumed, sealed or unresolved anywhere in a calibration or evaluation component blocks its freshness claim. An exact sealed source or byte copy is excluded from every partition. An exact consumed copy requires the historical exposure label even in development. A shared performer alone does not establish byte identity. [Study preflight](../../scripts/music_verdict_study.py) · [Frozen source rules](../../docs/research/music-verdict-successor-20260927.md)

## Private inventory format

Use the existing `--inventory` command. Version 1 still audits the selected rows alone. Version 2 takes `schema_version`, `sources` and `identity_references`. Each selected source retains the original source schema. Each reference has the following fields.

| Field | Meaning |
| --- | --- |
| `source_id` | Globally reconciled source ID. An exact ID shared with a selected row is a copy-identity edge. Use one reference row per source ID. |
| `artist_ids`, `session_ids`, `lineage_ids` | Arrays of globally reconciled identities. Empty arrays indicate missing edges. Different identity types occupy separate namespaces. |
| `audio_sha256` | Existing file commitment, or null if unavailable. Unknown hashes never link two records. |
| `history_status` | One of `unselected`, `consumed`, `sealed`, `unresolved`. Unselected records carry known relationships without asserting historical exposure. |
| `identity_refs` | Nonempty evidence references supporting the curator's identity and historical-status assertions. The checker does not follow links or open audio. |

The output contains aggregate counts and a digest of the private input document. A passing check depends on the identities and history provided. Omitted sources, unknown aliases and incorrect curatorial assertions can conceal relationships. An empty reference list supplies no external evidence. Final allocation still requires a qualified corpus, a bound exclusion inventory and prospectively fixed selection order and quotas. No real study allocation was made here.

## Replay

The catalogue replay uses the original snapshot, including the prior cover review. Its `lineage_review` section now reports both counts. Six new regression tests cover graph bridges, freshness, copies, reference-only counts, invalid records and input compatibility. An independent graph traversal agreed with the study implementation on 200 generated inventories of 45 rows each.

```sh
snapshot=/Volumes/schwarz/lossytrace/validation/botb-opl-project-metadata-20261123-001
python3 -B scripts/music_verdict_opl_sources.py "$snapshot" \
  --opl-catalogue "$snapshot/opl-catalogue.html" \
  --lineage-review research/music-verdict-v1/opl-lineage-review-20261123.json
python3 -B -m unittest discover -s scripts/tests -p 'test_music_verdict_study.py'
```
