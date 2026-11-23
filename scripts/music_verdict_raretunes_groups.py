"""Bound the RareTunes shortlist and screen two historical metadata inventories."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata

from music_verdict_raretunes_metadata import summarize
from music_library_pilot_select import layers


def norm(s):
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s).casefold()).strip()


def works(title):
    return {norm(re.sub(r"\s*\([^)]*\)\s*$", "", t)) for t in title.split("/")} - {""}


def group(keys):
    """Return the transitive closure of intersecting sets of typed identifiers."""
    clusters = []
    for item, labels in sorted(keys.items()):
        members = {item}
        combined = set(labels)
        disjoint = []
        for prior, tags in clusters:
            if labels & tags:
                members.update(prior)
                combined.update(tags)
            else:
                disjoint.append((prior, tags))
        clusters = disjoint + [(members, combined)]
    return sorted(sorted(members) for members, _ in clusters)


def audit(root, library):
    screen = summarize(root)
    if screen["sorted_metadata_digest"] != "d4341face274e60317f5bd484af9b537f956ac3a1b3d409671684a7b684916a9":
        raise ValueError("unexpected item metadata snapshot")
    keys, by_placement, personnel, titles = {}, {}, set(), set()
    durations, hashes, formats = [], set(), set()
    file_rights = 0
    for i in screen["candidates_for_manual_review"]:
        item = json.loads((root / "nc-sa" / (i + ".json")).read_bytes())
        m = item["metadata"]
        wav, = [f for f in item["files"] if f.get("source") == "original" and f.get("format") == "WAVE"]
        durations.append(float(wav["length"]))
        hashes.add(wav["md5"])
        formats.update(wav)
        file_rights += m["licenseurl"] in wav.get("license", "")
        artist = {norm(p) for p in m["creator"].split(",")}
        if "duncan mcmillan trio" in artist:
            artist.add("duncan mcmillan")
        # Additional personnel plainly named in the reviewed recording notes.
        for token, name in (("gerald moore", "gerald moore"), ("sandy moir", "sandy moir"),
                            ("paul powell", "paul powell"), ("john reid", "john reid jr"),
                            ("john ried jnr", "john reid jr")):
            if token in norm(m.get("description","")):
                artist.add(name)
        personnel.update(artist)
        parts = works(m["title"])
        titles.update(parts)
        keys[i] = {("performer", n) for n in artist} | {("work", t) for t in parts}
        # Same LP can contain unrelated sessions. Quarantine these together
        # only in an explicitly separate sensitivity calculation.
        by_placement[i] = keys[i].copy()
        for record in ("hmv dlp 1143", "emi clp 1220"):
            if record in norm(m.get("description","")):
                by_placement[i].add(("compilation", record))
    raw = (root/"rwc-pinned-metadata.csv").read_bytes()
    if hashlib.sha256(raw).hexdigest() != "eba3fe129f835db58a9c23dad554547201ab02ef3af90c10857ef5b50b8b99da":
        raise ValueError("unexpected historical RWC annotations")
    rwc = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";"))
    selection = json.loads((library/"pilot-selection.json").read_bytes())
    inventory = (library/"inventory.json").read_bytes()
    if hashlib.sha256(inventory).hexdigest() != selection["inventory_sha256"]:
        raise ValueError("unexpected historic pilot inventory")
    selected = {r["path"] for r in selection["selected"]}
    library_rows = [layers(r["metadata"]) for r in json.loads(inventory)["entries"] if r["path"] in selected]
    if len(rwc) != 328 or len(library_rows) != len(selected) or len(selected) != 24 or not all(library_rows):
        raise ValueError("missing historical identities")
    tags = [layer for row in library_rows for layer in row]

    def screen_labels(rows, people_fields, title_field):
        people = {norm(s) for row in rows for field in people_fields
                  for s in re.split("[,;/]", row.get(field) or "") if s.strip()}
        names = set().union(*(works(row.get(title_field) or "") for row in rows))
        return dict(rows=len(rows), person_key_hits=len(personnel & people),
                    work_key_hits=len(titles & names))

    return dict(shortlisted=len(keys), distinct_wav_md5=len(hashes),
                duration_range_seconds=[min(durations), max(durations)],
                original_file_metadata_keys=sorted(formats), corroborating_file_license=file_rights,
                linked_groups=group(keys), compilation_quarantine_groups=group(by_placement),
                library_tracks=len(library_rows), overlap=dict(rwc=screen_labels(rwc, ("Artist", "Composer"), "Title"),
                             library=screen_labels(tags, ("artist","album_artist","composer","remixer"),"title")))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("library_inventory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.snapshot,args.library_inventory), indent=2))
