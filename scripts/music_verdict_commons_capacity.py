"""Upper bound on independent finished works in the retained direct Commons FLAC category."""
import argparse
from collections import Counter, defaultdict
import html
import json
from pathlib import Path
import re

from music_verdict_commons_metadata import fields, screen


# Reviewed content declarations on these specific pages of the bound snapshot.
EXCLUSIONS = {
    "memory_exercise": [106609587, 106609562, 106609563, 106609553, 106609558],
    "interview_or_discussion": [110122276, 108116052, 109739858, 108183945],
    "environment_or_sleep": [143027035, 38317953, 33451188, 38306311],
    "bird_recording": [188531112, 85917913],
    "explicit_excerpt": [44955346, 28486116],
}


def plain(ext, key):
    return " ".join(html.unescape(re.sub("<[^>]*>", " ", ext.get(key, {}).get("value", ""))).split())


def performer(row, info):
    ext = info["extmetadata"]
    credit, description, artist = (plain(ext, k) for k in ("Credit", "ImageDescription", "Artist"))
    if "Hans Duhan" in credit + " " + description:
        return "Hans Duhan"
    if artist in ("C418", "HOME", "Resonant Bodies") and row["title"].startswith("File:" + artist + " - "):
        return artist
    if "Swedish choir Harmonica sings" in description:
        return "Harmonica choir"
    if artist in ("Kitty", "Kitty (feat. ya boy sprightly)") and "Kitty's album" in description:
        return "Kitty"
    return None


def inspect(root):
    catalogue = screen(root)
    if catalogue["snapshot_sha256"] != "cb6dd5784192d3dc342f645b3242cca915f51749ba7d26c6226ff961f79bf33d":
        # The existing reader computes the bound digest from filenames and content.
        raise ValueError("unexpected Commons metadata snapshot")
    eligible = {r["pageid"] for r in catalogue["files"]}
    excluded = {page for ids in EXCLUSIONS.values() for page in ids}
    if not excluded <= eligible or len(excluded) != sum(map(len, EXCLUSIONS.values())):
        raise ValueError("content dispositions do not match eligible pages")
    technical = Counter()
    clusters = defaultdict(list)
    ungrouped = []
    for path in sorted(root.glob("batch-*.json")):
        for row in json.loads(path.read_bytes())["query"]["pages"]:
            page = row["pageid"]
            info, = row["imageinfo"]
            if page not in eligible:
                meta = fields(info["metadata"])
                stream = fields(fields(meta["flac"])["STREAMINFO"])
                reasons = []
                if stream["sample_rate"] not in (44100, 48000):
                    reasons.append("rate")
                if stream["samples_stream"] < 30 * stream["sample_rate"]:
                    reasons.append("duration")
                if not reasons:
                    raise ValueError("unexplained technical exclusion")
                technical["+".join(reasons)] += 1
            elif page not in excluded:
                name = performer(row, info)
                if name:
                    clusters[name].append(page)
                else:
                    ungrouped.append(page)
    retained = sum(map(len, clusters.values())) + len(ungrouped)
    three_credit_ceiling = retained - sum(len(clusters[name]) - 1 for name in ("C418", "HOME", "Hans Duhan"))
    if retained + len(excluded) != len(eligible) or len(eligible) + sum(technical.values()) != catalogue["category_members"]:
        raise ValueError("incomplete disposition")
    return dict(snapshot_sha256=catalogue["snapshot_sha256"], direct_category_files=catalogue["category_members"],
                technical_exclusions=dict(technical), supported_format=len(eligible), content_exclusions=EXCLUSIONS,
                complete_music_or_unresolved=retained, shared_performer_pages={k:sorted(v) for k,v in clusters.items()},
                unresolved_or_singleton_pages=sorted(ungrouped), independent_group_ceiling=len(clusters)+len(ungrouped),
                ceiling_using_only_three_largest_credits=three_credit_ceiling, groups_admitted=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    print(json.dumps(inspect(parser.parse_args().snapshot), indent=2, sort_keys=True))
