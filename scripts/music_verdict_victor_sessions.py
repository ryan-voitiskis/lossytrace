"""Link Potpourri transfer metadata to LC's partial Victor session catalogue."""
import argparse
from collections import Counter, defaultdict
import hashlib
from html import unescape
import json
from pathlib import Path
import re
import unicodedata
from urllib.parse import quote

from music_verdict_potpourri_metadata import screen
from music_verdict_raretunes_groups import group


def normal(text):
    text = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(re.findall(r"[a-z0-9]+", "".join(c for c in text if not unicodedata.combining(c))))


def performance_names(row):
    names = []
    for credit in row["Contributors"]:
        role = credit.get("Role") or ""
        if role.startswith(("Vocalist", "Instrumentalist")) or role in (
                "Conductor", "Leader", "Musical Group", "Vocal Group", "Choral Director", "Performer"):
            name = credit["Name"]
            parts = name.split(", ", 1)
            names.append(normal(" ".join(reversed(parts))))
    return sorted(set(names) - {""})


def audit(snapshot, lc_path):
    intake = screen(snapshot)
    if intake["captured_item_metadata_sha256"] != "bf03844257bba21b9b0ed2b3169892a74d33621e12002d5d0bafcc905e0dd8c7":
        raise ValueError("unexpected transfer metadata")
    data = lc_path.read_bytes()
    if hashlib.sha256(data).hexdigest() != "ea6b74f30eeac6be74f4ab947f41001a070719bdb5831bcdac12e243b9cbb93a":
        raise ValueError("unexpected LC metadata")
    catalog = json.loads(data)
    by_number = defaultdict(list)
    for row in catalog:
        if row.get("Recording_label") == "Victor":
            by_number[row["Recording_catalog_number"]].append(row)
    counts = Counter()
    linked = {}
    keys = {}
    for item in intake["candidate_ids"]:
        meta = json.loads((snapshot/"cc0"/(quote(item,safe="")+".json")).read_bytes())["metadata"]
        desc = unescape(re.sub(r"<[^>]+>", " ", meta["description"]))
        numbers = set(re.findall(r"\bVictor\s+(\d{4,6})\b", desc, re.I))
        candidates = [row for n in sorted(numbers) for row in by_number[n]]
        counts["victor_number"] += bool(numbers)
        counts["number_in_catalog"] += bool(candidates)
        titles = [row for row in candidates if normal(row["Title"]) == normal(meta["title"])]
        counts["title_and_number"] += bool(titles)
        creator = meta.get("creator", "")
        credits = [creator] if isinstance(creator,str) else creator
        note = " " + normal(" ".join([desc,*credits])) + " "
        agreement = [row for row in titles if any(" "+n+" " in note for n in performance_names(row))]
        if not agreement:
            continue
        linked[item] = [dict(id=r["Id"], matrix=r["Recording_matrix_number"],
                             take=r["Recording_take_number"], date=r["Date"], place=r["Location_text"],
                             names=performance_names(r),
                             overlap=[n for n in performance_names(r) if " "+n+" " in note])
                        for r in agreement]
        counts["with_named_credit"] += 1
        if len(titles) != 1:
            counts["not_unique_within_title_number"] += 1
            continue
        row, = agreement
        keys[item] = {("name",n) for n in performance_names(row)} | {("work",normal(meta["title"]))}
    place_date = {i:set(k) for i,k in keys.items()}
    for i in keys:
        r, = linked[i]
        if r["place"] and re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["date"] or ""):
            place_date[i].add(("date_place",(r["date"],r["place"])))
    return dict(lc_rows=len(catalog), intake_count=len(intake["candidate_ids"]), counts=dict(counts),
                linked=linked, shared_performer_or_work_groups=group(keys),
                with_same_day_place_quarantine=group(place_date))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("lc_metadata", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.snapshot, args.lc_metadata), indent=2))
