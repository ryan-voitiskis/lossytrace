"""Summarize retained public collection and item metadata without reading audio."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


BASS = re.compile(r"bass\s*:\s*(?:scott\^,\s*)?lucas\b|lucas(?:\s+k\.?)?\s*[:-]\s*"
                  r"(?:(?:acoustic|electric|&)[-\s]+)*bass\b", re.I)
RATE = re.compile(r"\b(?:48|44\.1)\s*k(?:hz)?\b", re.I)


def summarize(folder):
    hashes = {}

    def read(name):
        raw = (folder / (name + ".json")).read_bytes()
        hashes[name] = hashlib.sha256(raw).hexdigest()
        return json.loads(raw)

    collections = {}
    examples = {}
    for band, item in (("BlueFunk", "BlueFunk2013-08-02"), ("TheShipsCat", "ShipsCat2021-01-07")):
        collection = read(band)["metadata"]
        if collection["identifier"] != band or not collection["rights"]:
            raise ValueError("missing collection permission statement")
        search = read(band + "-all")
        response = search["response"]
        docs = response["docs"]
        ids = {x["identifier"] for x in docs}
        if (response["numFound"] != len(ids) or len(ids) != len(docs) or response["start"] != 0
                or search["responseHeader"]["params"]["query"] != f"collection:{band} AND mediatype:etree"
                or any(band not in x["collection"] for x in docs) or item not in ids):
            raise ValueError("unexpected collection inventory")
        collections[band] = dict(items=len(ids), distinct_dates=len({x["date"][:10] for x in docs}),
                                 taper=Counter(x["taper"].strip().casefold() for x in docs),
                                 transferer=Counter(x["transferer"].strip().casefold() for x in docs),
                                 literal_bass_lucas_credits=sum(bool(BASS.search(x["description"])) for x in docs),
                                 licenses=Counter(x.get("licenseurl", "unspecified") for x in docs),
                                 native_rate_mentioned_in_capture_and_transfer=sum(
                                     all(RATE.search(x.get(k, "")) for k in ("source", "lineage")) for x in docs))
        detail = read(item)
        m = detail["metadata"]
        if m["identifier"] != item:
            raise ValueError("unexpected example")
        files = []
        for wav in detail["files"]:
            if wav.get("format") != "WAVE" or wav["source"] != "original":
                continue
            derivatives = [x for x in detail["files"] if x.get("format") == "Flac" and
                           x.get("original") == wav["name"] and x["source"] == "derivative"]
            if len(derivatives) != 1 or derivatives[0]["length"] != wav["length"]:
                raise ValueError("missing corresponding FLAC metadata")
            files.append(dict(name=wav["name"], seconds=wav["length"], bytes=int(wav["size"]),
                              archive_reported_wav_sha1=wav["sha1"],
                              archive_reported_flac_sha1=derivatives[0]["sha1"]))
        if not files:
            raise ValueError("expected original WAV entries")
        examples[item] = dict(source=m["source"], lineage=m["lineage"], license=m["licenseurl"],
                              files=files)
    return dict(snapshot_sha256=hashes, collections=collections, examples=examples, allocated_groups=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    print(json.dumps(summarize(parser.parse_args().snapshot), indent=2, sort_keys=True))
