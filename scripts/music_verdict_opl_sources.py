"""Inspect public FM tracker entry metadata without fetching tunes or previews."""

import argparse
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote
from urllib.request import urlopen

from music_verdict_raretunes_groups import group


FORMATS = ("opl2", "opl3", "adlib")
PAGE_SIZE = 250


def normalized(text):
    return re.sub(r"[^\w]+", " ", text.casefold()).strip()


class OplListing(HTMLParser):
    """Read the catalogue's original/cover headings and displayed VGM links as text."""

    def __init__(self):
        super().__init__()
        self.section = None
        self.works = {}
        self.entries = 0

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        css = attrs.get("class")
        if tag == "div" and css in ("artist-header", "artist-originals", "artist-covers"):
            self.section = css
        link = attrs.get("href", "")
        if tag != "a" or not link.startswith("./vgm/"):
            return
        artist, title = unquote(link[6:]).rsplit("/", 1)
        if self.section not in ("artist-originals", "artist-covers") or not title.lower().endswith(".vgz"):
            raise ValueError("unexpected OPL catalogue layout")
        key = normalized(artist), normalized(title[:-4])
        self.works.setdefault(key, set()).add(self.section)
        self.entries += 1


def project_record(row):
    battle = row["battle"]
    periods = battle.get("period_data") or []
    # Some older periods are anonymous list elements or unavailable.
    # Any supplied pack anywhere in the battle warrants lineage review.
    if isinstance(periods, dict):
        periods = periods.values()
    return {
        "id": row["id"], "title": row["title"], "date": row["datetime"],
        "format": row["format_token"], "battle": row["battle_id"],
        "battle_title": battle["title"],
        "battle_pack": (any(bool(p.get("bitpack")) for p in periods) if periods else None),
        "authors": [{"id": a["id"], "name": a["name"]} for a in (row.get("authors") or [])],
        "length": row.get("length"), "entry_url": row["profile_url"],
        "source_label": row.get("view_url"), "preview_format": row.get("render"),
    }


def capture(root):
    root.mkdir(exist_ok=True)
    for token in FORMATS:
        for page in range(100):
            url = (f"https://battleofthebits.com/api/v1/entry/list/{page}/{PAGE_SIZE}"
                   f"?filters=format_token~{token}&sort=id")
            path = root / f"{token}-{page}.json"
            if path.exists():
                cached = json.loads(path.read_bytes())
                if cached["url"] != url:
                    raise ValueError("snapshot URL mismatch")
                count = len(cached["entries"])
            else:
                with urlopen(url, timeout=45) as response:
                    raw = response.read()
                data = json.loads(raw)
                if not isinstance(data, list) or any(r["format_token"] != token for r in data):
                    raise ValueError("unexpected format or response")
                rows = [project_record(r) for r in data]
                page_data = dict(url=url, response_sha256=hashlib.sha256(raw).hexdigest(), entries=rows)
                with path.open("x") as output:
                    json.dump(page_data, output, ensure_ascii=False)
                count = len(rows)
                print(token, page, count, flush=True)
            if count < PAGE_SIZE:
                break
        else:
            raise ValueError("pagination did not terminate")


def summarize(root, catalogue=None):
    records = {}
    digest = hashlib.sha256()
    for token in FORMATS:
        last_id = 0
        page = 0
        while True:
            raw = (root / f"{token}-{page}.json").read_bytes()
            digest.update(hashlib.sha256(raw).digest())
            entries = json.loads(raw)["entries"]
            for row in entries:
                identity = row["id"]
                if row["format"] != token or identity in records or int(identity) <= last_id:
                    raise ValueError("unexpected format, duplicate or unordered entry")
                records[identity] = row
                last_id = int(identity)
            if len(entries) < PAGE_SIZE:
                break
            page += 1
    keys = {}
    suffixes = {}
    for identity, row in records.items():
        authors = row["authors"]
        title = normalized(row["title"])
        keys[identity] = {("artist", a["id"]) for a in authors}
        if title:
            keys[identity].add(("title", title))
        # The API puts literal '#' characters in some original file names.
        # Read its label as a name. Parsing it as a URL would truncate the suffix.
        suffixes[identity] = Path(unquote(row["source_label"] or "")).suffix.lower()
    # Apply known cross-item grouping edges before narrowing to a subset.
    components = group(keys)
    eligible = {i for i, r in records.items() if r["authors"] and r["length"]
                and float(r["length"]) >= 30 and r["date"][:4] >= "2012"}
    declared_modules = {i for i in eligible if suffixes[i] in {
        ".a2m", ".rad", ".fur", ".s3m", ".mptm", ".amd", ".sa2", ".fmc", ".dfm"}}
    subset = {i for i in declared_modules if records[i]["battle_pack"] is False}

    def counts(ids):
        return {
            "entries": len(ids),
            "distinct_artist_ids": len({a["id"] for i in ids for a in records[i]["authors"]}),
            "components_with_entries": sum(not ids.isdisjoint(c) for c in components),
            "suffixes": dict(sorted(Counter(suffixes[i] for i in ids).items())),
        }
    result = {
        "snapshot_sha256": digest.hexdigest(), "all_entries": len(records),
        "by_format": dict(Counter(r["format"] for r in records.values())),
        "all_components": len(components), "duration_30s_post_2011_with_authors": counts(eligible),
        "recognized_modules": counts(declared_modules),
        "no_listed_battle_pack": counts(subset),
        "rad_no_listed_battle_pack": counts({i for i in subset if suffixes[i] == ".rad"}),
    }
    if catalogue is not None:
        raw = catalogue.read_bytes()
        listing = OplListing()
        listing.feed(raw.decode())
        listing.close()
        originals, covers = set(), set()
        for i in subset:
            record = records[i]
            if len(record["authors"]) != 1:
                continue
            key = normalized(record["authors"][0]["name"]), normalized(record["title"])
            sections = listing.works.get(key, set())
            if "artist-covers" in sections:
                covers.add(i)
            elif "artist-originals" in sections:
                originals.add(i)
        result["catalogue_match_in_no_pack_subset"] = {
            "catalogue_sha256": hashlib.sha256(raw).hexdigest(), "listed_links": listing.entries,
            "originals": counts(originals), "covers": counts(covers),
            "original_entry_ids": sorted(originals, key=int), "cover_entry_ids": sorted(covers, key=int),
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--opl-catalogue", type=Path, help="previously saved OPL Archive index HTML")
    args = parser.parse_args()
    if args.capture:
        capture(args.snapshot)
    print(json.dumps(summarize(args.snapshot, args.opl_catalogue), indent=2))
