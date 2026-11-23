"""Count text-score leads and cross-format identity links in retained BotB catalogue pages."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import unquote

from music_verdict_opl_sources import normalized
from music_verdict_study import identity_components


def read_pages(folder, formats):
    rows = []
    digest = hashlib.sha256()
    for fmt in formats:
        page = 0
        previous = 0
        while True:
            raw = (folder / f"{fmt}-{page}.json").read_bytes()
            digest.update(hashlib.sha256(raw).digest())
            obj = json.loads(raw)
            expected_url = f"https://battleofthebits.com/api/v1/entry/list/{page}/250?filters=format_token~{fmt}&sort=id"
            if obj["url"] != expected_url:
                raise ValueError("unexpected catalogue page")
            for r in obj["entries"]:
                if r["format"] != fmt or int(r["id"]) <= previous:
                    raise ValueError("unordered or mismatched entry")
                previous = int(r["id"])
                rows.append(r)
            if len(obj["entries"]) < 250:
                break
            page += 1
    return rows, digest.hexdigest()


def audit(folder, opl):
    records, new_digest = read_pages(folder, ("jummbox", "mml"))
    prior, old_digest = read_pages(opl, ("opl2", "opl3", "adlib"))
    old_report = json.loads((Path(__file__).resolve().parents[1] / "research/music-verdict-v1/opl-project-metadata-20261123.json").read_bytes())
    if old_digest != old_report["snapshot_sha256"]:
        raise ValueError("previous OPL pages differ from the recorded snapshot")
    by_id = {r["id"]:r for r in prior + records}
    if len(by_id) != len(prior) + len(records):
        raise ValueError("duplicate entry ID")
    suffixes = {r["id"]:Path(unquote(r["source_label"] or "")).suffix.lower() for r in records}
    graph = []
    for r in by_id.values():
        title = r["title"].strip()
        suffix = Path(title).suffix.lower()
        if suffix in {".json", ".txt", ".mml"}:
            title = title[:-len(suffix)]
        title = normalized(title)
        graph.append(dict(source_id=r["id"], artist_ids=[a["id"] for a in r["authors"]],
                          lineage_ids=[title] if title else []))
    # Preserve the earlier documented cover links, including off-catalogue works.
    review = json.loads((Path(__file__).resolve().parents[1] / "research/music-verdict-v1/opl-lineage-review-20261123.json").read_bytes())
    old_short = {i for i in old_report["catalogue_match_in_no_pack_subset"]["original_entry_ids"]
                 if by_id[i]["battle"] not in review["cover_only_battles"]}
    for work in review["related_works"]:
        artists = {a["id"] for r in by_id.values() for a in r["authors"] if normalized(a["name"]) == normalized(work["artist"])}
        if work["artist_id"]:
            artists.add(work["artist_id"])
        graph.append(dict(source_id=work["entry_id"] or ("work:"+work["title"]), artist_ids=sorted(artists),
                          lineage_ids=[normalized(work["title"]), review["work_lineage_id"]]))
    groups = [{r["source_id"] for r in group} for group in identity_components(graph, ("source_id","artist_ids","lineage_ids"))]
    def counts(ids):
        return dict(entries=len(ids), artist_ids=len({a["id"] for i in ids for a in by_id[i]["authors"]}),
                    linked_groups=sum(bool(g & ids) for g in groups),
                    groups_also_containing_prior_opl_lead=sum(bool(g & ids and g & old_short) for g in groups))
    stages = {}
    accepted = set()
    for fmt in ("jummbox", "mml"):
        all_ids = {r["id"] for r in records if r["format"] == fmt}
        formats = {".txt",".json"} if fmt == "jummbox" else {".txt",".mml"}
        textual = {i for i in all_ids if suffixes[i] in formats}
        long = {i for i in textual if float(by_id[i]["length"] or 0) >= 30 and by_id[i]["authors"]}
        screened = {i for i in long if by_id[i]["battle"] not in review["cover_only_battles"]}
        accepted.update(screened)
        stages[fmt] = dict(all=counts(all_ids), labelled_text=counts(textual),
                           credited_text_30s=counts(long), excluding_known_cover_events=counts(screened),
                           no_listed_pack=counts({i for i in screened if by_id[i]["battle_pack"] is False}),
                           suffixes=dict(sorted(Counter(suffixes[i] for i in all_ids).items())))
    return dict(projected_pages_sha256=new_digest, opl_pages_sha256=old_digest, by_format=stages,
                combined_screen=counts(accepted), prior_opl_on_combined_graph=counts(old_short),
                union_with_prior_opl=counts(accepted|old_short), accepted_ids=sorted(accepted,key=int))


if __name__ == "__main__":
    print(json.dumps(audit(*map(Path, sys.argv[1:])), indent=2))
