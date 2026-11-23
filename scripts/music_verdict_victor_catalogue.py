"""Use the complete retained Victor performer catalogue as an identity reference graph."""
import argparse
from collections import Counter, defaultdict, deque
import json
from pathlib import Path

from music_verdict_study import identity_components
from music_verdict_victor_sessions import audit, normal, performance_names


def shortest_performer_chain(rows, start, end):
    by_id = {r["source_id"]: r for r in rows}
    by_name = defaultdict(list)
    for r in rows:
        for name in r["artist_ids"]:
            by_name[name].append(r["source_id"])
    queue = deque([start])
    parents = {start: None}
    seen_names = set()
    while queue:
        current = queue.popleft()
        if current == end:
            path = []
            while parents[current]:
                previous, name = parents[current]
                path.append(dict(first=previous, name=name, second=current))
                current = previous
            return path[::-1]
        for name in by_id[current]["artist_ids"]:
            if name in seen_names:
                continue
            seen_names.add(name)
            for other in by_name[name]:
                if other not in parents:
                    parents[other] = current, name
                    queue.append(other)
    raise ValueError("missing named-performer path")


def summarize(snapshot, lc):
    earlier = audit(snapshot, lc)  # Verifies both snapshots and reproduces the 35 take joins.
    old_groups = earlier["shared_performer_or_work_groups"]
    selected = {item: earlier["linked"][item][0]["id"] for group in old_groups for item in group}
    catalog = json.loads(lc.read_bytes())
    rows = []
    for entry in catalog:
        title = normal(entry["Title"])
        composers = {normal(c["Name"]) for c in entry["Contributors"]
                     if c.get("Role") == "Composer" and c.get("Name")}
        rows.append(dict(source_id=entry["Id"], artist_ids=performance_names(entry), title=title,
                         composed_titles=sorted(name + "|" + title for name in composers if title)))
    if len({r["source_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate catalogue row ID")
    selected_ids = set(selected.values())
    results = {}
    for mode in ("performer", "performer_and_selected_titles", "performer_and_composed_title", "performer_and_title"):
        for r in rows:
            r["lineage_ids"] = []
            if mode == "performer_and_composed_title":
                r["lineage_ids"] = r["composed_titles"]
            elif mode == "performer_and_title" or (mode == "performer_and_selected_titles" and r["source_id"] in selected_ids):
                r["lineage_ids"] = [r["title"]] if r["title"] else []
        groups = identity_components(rows, ("artist_ids", "lineage_ids"))
        selected_groups = []
        for group in groups:
            ids = {r["source_id"] for r in group}
            items = sorted(item for item, identifier in selected.items() if identifier in ids)
            if items:
                selected_groups.append(items)
        if sum(map(len, selected_groups)) != len(selected):
            raise ValueError("missing transfer in graph")
        results[mode] = dict(catalogue_components=len(groups), largest=max(map(len, groups)),
                             with_any_named_performer=sum(any(r["artist_ids"] for r in g) for g in groups),
                             shortlisted_transfer_components=sorted(selected_groups))
    # Two previously separate shortlisted groups connected solely by named performing credits.
    ends = ["a-little-bit-of-heaven", "dont-turn-my-picture-to-the-wall"]
    witness = shortest_performer_chain(rows, *(selected[i] for i in ends))
    if not all(any(r["source_id"] == e[k] and e["name"] in r["artist_ids"] for r in rows)
               for e in witness for k in ("first", "second")):
        raise ValueError("invalid credit path")
    return dict(catalogue_rows=len(rows), transfer_rows=len(selected), distinct_matched_takes=len(selected_ids),
                earlier_groups=len(old_groups), rows_without_performer=sum(not r["artist_ids"] for r in rows),
                audio_mime_counts=dict(Counter(t for e in catalog for t in e["Mime_type"] if t.startswith("audio/"))),
                modes=results, witness_transfers=ends, performer_only_witness=witness)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("lc", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.snapshot, args.lc), indent=2))
