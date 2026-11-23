"""Replay the public-domain-dedication subset screen over saved Archive JSON."""
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote


def screen(root):
    index = (root/"potpourri-index-through-1922.json").read_bytes()
    if hashlib.sha256(index).hexdigest() != "03625ab89f61dbcf9a175e29b9335e032e7898d10bc9fc7d9099524577ec1b00":
        raise ValueError("unexpected catalog snapshot")
    rows = json.loads(index)["response"]["docs"]
    cc0 = "https://creativecommons.org/publicdomain/zero/1.0/"
    ids = sorted(r["identifier"] for r in rows if r.get("licenseurl") == cc0)
    candidates, missing, unmatched = [], [], []
    labels, wav_items, chains = set(), 0, 0
    digest = hashlib.sha256()
    for i in ids:
        path = root/"cc0"/(quote(i, safe="") + ".json")
        if not path.exists():
            missing.append(i)
            continue
        raw = path.read_bytes()
        digest.update(i.encode() + b"\0" + hashlib.sha256(raw).digest())
        item = json.loads(raw)
        m = item.get("metadata", {})
        if m.get("identifier") != i or m.get("licenseurl") != cc0:
            unmatched.append(i)
            continue
        files = item.get("files", [])
        wavs = {f["name"] for f in files if f.get("format") == "WAVE" and f.get("source") == "original"}
        wav_items += bool(wavs)
        flacs = [f for f in files if f.get("original") in wavs and f.get("source") == "derivative"
                 and f.get("format","").lower() in ("flac", "24bit flac")
                 and re.fullmatch(r"\d+(\.\d+)?", str(f.get("length",""))) and float(f["length"]) >= 30]
        chains += bool(flacs)
        if flacs and re.search(r"magnetic cartridge|bass turnover|de.click|recorded with .*equalization",
                               str(m.get("description", "")), re.I):
            candidates.append(i)
            if m.get("creator"):
                labels.add(json.dumps(m["creator"], sort_keys=True))
    return dict(catalog_count=len(rows), cc0_catalog_items=len(ids), absent_responses=missing,
                missing_or_inconsistent_item_identity_or_license=unmatched, original_wave_items=wav_items,
                with_linked_flac_at_least_30_seconds=chains, with_transfer_text=len(candidates),
                distinct_nonempty_creator_fields_in_shortlist=len(labels), candidate_ids=candidates,
                captured_item_metadata_sha256=digest.hexdigest())


if __name__ == "__main__":
    print(json.dumps(screen(Path(sys.argv[1])), indent=2))
