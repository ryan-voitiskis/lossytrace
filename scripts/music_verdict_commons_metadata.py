"""Read a saved Commons category and imageinfo responses without touching media."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def fields(entries):
    return {entry["name"]: entry["value"] for entry in entries}


def screen(root):
    catalog = json.loads((root/"category.json").read_bytes())
    expected = {r["pageid"] for r in catalog["query"]["categorymembers"]}
    pages = {}
    digest = hashlib.sha256()
    for path in [root/"category.json", *sorted(root.glob("batch-*.json"))]:
        data = path.read_bytes()
        digest.update(path.name.encode() + b"\0" + hashlib.sha256(data).digest())
        result = json.loads(data)
        if "continue" in result or "warnings" in result or "error" in result:
            raise ValueError("incomplete provider response")
        for row in result["query"].get("pages", []):
            if row["pageid"] in pages:
                raise ValueError("duplicate catalogue member")
            pages[row["pageid"]] = row
    if set(pages) != expected:
        raise ValueError("incomplete category readback")
    qualified_format = []
    for row in pages.values():
        i, = row["imageinfo"]
        meta = fields(i.get("metadata", []))
        audio = fields(meta.get("audio", []))
        info = fields(fields(meta.get("flac", [])).get("STREAMINFO", []))
        if (meta.get("fileformat") != "flac" or not audio.get("lossless")
                or any(info.get(k) != audio.get(k) for k in ("sample_rate", "channels", "bits_per_sample"))
                or info.get("sample_rate") not in (44100, 48000) or info.get("channels") not in (1, 2)
                or info.get("bits_per_sample") not in (16, 24)
                or info.get("samples_stream", 0) < 30*info["sample_rate"]):
            continue
        qualified_format.append(dict(pageid=row["pageid"], title=row["title"], sha1=i["sha1"],
                                     license_label=i["extmetadata"].get("LicenseShortName", {}).get("value")))
    return dict(snapshot_sha256=digest.hexdigest(), category_members=len(expected),
                format_and_duration_matches=len(qualified_format),
                license_labels=dict(Counter(r["license_label"] for r in qualified_format)),
                files=sorted(qualified_format, key=lambda f:f["pageid"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    print(json.dumps(screen(parser.parse_args().snapshot), indent=2))
