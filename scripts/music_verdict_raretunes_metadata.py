"""Summarize locally saved RareTunes catalogue metadata. Reads JSON only."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote


MEDIUM = re.compile(r"\b(?:78\s*(?:rpm|r\.p\.m)|vinyl|shellac|cassette|reel[ -]to[ -]reel)\b", re.I)
CATALOG = re.compile(r"\b(?:matrix|from (?:the )?(?:record|ep|lp)\b|beltona\s+\d|hmv\s+[a-z][.\s-]*\d)", re.I)


def summarize(root):
    catalog = json.loads((root / "index.json").read_bytes())["response"]
    ids = sorted(row["identifier"] for row in catalog["docs"] if "/by-nc-sa/" in str(row.get("licenseurl")))
    if len(set(ids)) != len(ids) or len(catalog["docs"]) != catalog["numFound"]:
        raise ValueError("invalid catalogue coverage")
    digest = hashlib.sha256()
    candidates = []
    with_wave = medium_matches = catalog_matches = 0
    creators = set()
    for identifier in ids:
        path = root / "nc-sa" / (quote(identifier, safe="") + ".json")
        data = path.read_bytes()
        response = json.loads(data)
        metadata = response["metadata"]
        if metadata["identifier"] != identifier:
            raise ValueError("item identity mismatch")
        digest.update(identifier.encode() + b"\0" + hashlib.sha256(data).digest())
        waves = [f for f in response["files"] if f.get("source") == "original"
                 and f.get("format") == "WAVE" and f["name"].lower().endswith(".wav")]
        if waves:
            with_wave += 1
        text = " ".join(str(metadata.get(k, "")) for k in ("description", "source", "lineage"))
        has_medium = bool(waves and MEDIUM.search(text))
        has_catalog_hint = bool(waves and CATALOG.search(text))
        medium_matches += has_medium
        catalog_matches += has_catalog_hint
        if has_medium or has_catalog_hint:
            candidates.append(identifier)
            if metadata.get("creator"):
                creators.add(json.dumps(metadata["creator"], sort_keys=True))
    return dict(catalog_items=catalog["numFound"], reviewed_nc_sa=len(ids), items_with_original_wave=with_wave,
                medium_text_and_wave=medium_matches, catalog_text_and_wave=catalog_matches,
                either_hint_and_wave=len(candidates), literal_nonempty_creator_values=len(creators),
                sorted_metadata_digest=digest.hexdigest(), candidates_for_manual_review=candidates)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot_directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.snapshot_directory), indent=2))
