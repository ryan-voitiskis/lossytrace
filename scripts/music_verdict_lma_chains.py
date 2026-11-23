"""Replay a recording-chain screen on saved Live Music Archive metadata."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

PAGE_HASHES = (
    "9b89dfd38c984dd764bff5afdc4cb888c61c4d328e023d9512ce84bc63501fc7",
    "6b8cd02f4c3f2687f6dde07b82c5f9d72a804f5fe7e70b6c493eae54e780bb5f",
)
CAPTURE_HASH = "fde1ff176ba52c56a88b2de07a0e2c959325cd26e026153e7f8433c9eb235d28"
THIS_CLOSE = "ThisCloseBand2025-02-28.sbd.flac16"


def bound(path, digest):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("metadata snapshot digest changed")
    return raw


def screen(index):
    rows = []
    for page, digest in enumerate(PAGE_HASHES, 1):
        data = json.loads(bound(index / f"lma-licensed-page{page}" / "response.json", digest))
        rows.extend(data["response"]["docs"])
    if len(rows) != len({r["identifier"] for r in rows}):
        raise ValueError("overlapping index pages")
    eligible, matched = Counter(), Counter()
    groups = defaultdict(list)
    for row in rows:
        tag = row["licenseurl"]
        if re.fullmatch(r"https?://creativecommons\.org/(?:licenses/by(?:-sa)?/|publicdomain/zero/)[\w./-]+", tag):
            label = "BY_BY-SA_CC0"
        elif re.fullmatch(r"https?://creativecommons\.org/licenses/by-nc(?:-sa)?/[\w./-]+", tag):
            label = "BY-NC_BY-NC-SA"
        else:
            continue
        eligible[label] += 1
        chain = " ".join(row.get(field, "") for field in ("source", "lineage")).lower()
        if "flac" in chain and re.search(r"(?<![a-z])wav(?:e)?(?![a-z])", chain):
            matched[label] += 1
            groups[row["creator"].strip().casefold()].append(row)
    def rank(row):
        return hashlib.sha256(("lossytrace-lma-chain-v1:" + row["identifier"]).encode()).digest()
    return len(rows), eligible, matched, [min(group, key=rank) for group in groups.values()]


def inspect(index, snapshot):
    total, eligible, matched, representatives = screen(index)
    capture = json.loads(bound(snapshot / "capture.json", CAPTURE_HASH))
    expected = {}
    by_id = {}
    for row in representatives:
        collection, = [c for c in row["collection"] if c != "etree" and not c.startswith("fav-")]
        expected[row["identifier"]] = "record"
        expected[collection] = "collection"
        by_id[row["identifier"]] = row
    if expected != {key: entry["kind"] for key, entry in capture.items()}:
        raise ValueError("capture differs from recording and collection selection")

    details = {}
    track_files = {}
    for identifier, entry in capture.items():
        path = (snapshot / (identifier + ".json") if entry["origin"] == "retained"
                else snapshot / identifier / "response.json")
        document = json.loads(bound(path, entry["sha256"]))
        metadata = document["metadata"]
        if metadata["identifier"] != identifier:
            raise ValueError("item identity mismatch")
        if entry["kind"] == "collection":
            if metadata["mediatype"] != "collection" or not metadata.get("rights"):
                raise ValueError("missing collection policy")
            continue
        if metadata["licenseurl"] != by_id[identifier]["licenseurl"]:
            raise ValueError("license declaration changed since index capture")
        details[identifier] = document
        track_files[identifier] = [f for f in document["files"] if f.get("source") == "original"
                                   and f.get("format") in ("Flac", "24bit Flac")]

    tracks = track_files[THIS_CLOSE]
    item_files = details[THIS_CLOSE]["files"]
    evidence = {}
    for local, label in (("transfer-notes.txt", "Text"), ("pcm-fingerprints.ffp", "Flac FingerPrint")):
        file, = [f for f in item_files if f.get("source") == "original" and f["format"] == label]
        raw = (snapshot / local).read_bytes()
        if (len(raw) != int(file["size"]) or hashlib.sha1(raw).hexdigest() != file["sha1"]
                or hashlib.md5(raw).hexdigest() != file["md5"]):
            raise ValueError("transfer document mismatch")
        evidence[local] = raw.decode()
    fingerprints = {}
    for line in evidence["pcm-fingerprints.ffp"].splitlines():
        if line and not line.startswith(";"):
            name, digest = line.rsplit(":", 1)
            if name in fingerprints or not re.fullmatch(r"[0-9a-f]{32}", digest):
                raise ValueError("unexpected audio fingerprint")
            fingerprints[name] = digest
    if set(fingerprints) != {f["name"] for f in tracks} or len(fingerprints) != len(tracks):
        raise ValueError("fingerprint and original track lists differ")
    first, = [f for f in tracks if f["track"] == "1" and f["title"] == "I'll Take Two"]
    return dict(index_rows=total, license_screen=eligible, wav_flac_screen=matched,
                representative_items=len(representatives), artist_collections=len(expected)-len(representatives),
                original_flacs=sum(map(len, track_files.values())),
                original_flacs_at_least_30s=sum(float(f["length"]) >= 30 for v in track_files.values() for f in v),
                item_original_counts={i: len(v) for i, v in track_files.items()},
                this_close=dict(tracks_with_pcm_fingerprint=len(fingerprints), title=first["title"],
                                seconds=first["length"], file_sha1=first["sha1"],
                                declared_pcm_md5=fingerprints[first["name"]]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args()
    print(json.dumps(inspect(args.index, args.snapshot), indent=2, sort_keys=True))
