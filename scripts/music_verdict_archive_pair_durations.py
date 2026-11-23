"""Offline parent/derivative duration concordance on retained WAV archive leads."""
import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from music_verdict_potpourri_metadata import screen
from music_verdict_raretunes_metadata import summarize


def seconds(value):
    result = Decimal(0)
    for part in value.split(":"):
        result = 60 * result + Decimal(part)
    return result


def count(folder, shortlist):
    totals = Counter()
    mismatches = []
    for path in sorted(folder.glob("*.json")):
        item = json.loads(path.read_bytes())
        files = item.get("files", [])
        for wav in files:
            if wav.get("source") != "original" or wav.get("format") != "WAVE":
                continue
            totals["original_wavs"] += 1
            duration = seconds(wav["length"])
            children = [f for f in files if f.get("source") == "derivative" and f.get("original") == wav["name"]]
            close_mp3 = close_flac = False
            discrepant = []
            for f in children:
                if f["format"] not in ("VBR MP3", "Flac", "24bit Flac"):
                    continue
                mp3 = f["format"] == "VBR MP3"
                kind = "mp3" if mp3 else "flac"
                totals[kind + "_children"] += 1
                difference = abs(seconds(f["length"]) - duration)
                if difference <= 2:
                    totals[kind + "_within_two_seconds"] += 1
                    close_mp3 |= mp3
                    close_flac |= not mp3
                elif mp3:
                    discrepant.append(dict(name=f["name"], declared_length=f["length"]))
            if discrepant:
                identifier = item["metadata"]["identifier"]
                mismatches.append(dict(item=identifier, parent=wav["name"], declared_parent_length=wav["length"],
                                       discrepant_mp3=discrepant))
                totals["affected_parents_also_with_matching_mp3"] += int(close_mp3)
                totals["affected_parents_also_with_matching_flac"] += int(close_flac)
                totals["affected_parents_in_previous_shortlist"] += int(identifier in shortlist)
    return dict(counts=dict(totals), parents_with_discrepant_mp3=len(mismatches), records=mismatches)


def audit(validation):
    rare = validation / "source-metadata-20261123-001"
    pot = validation / "commons-music-metadata-20261123-001"
    r, p = summarize(rare), screen(pot)
    if (r["sorted_metadata_digest"] != "d4341face274e60317f5bd484af9b537f956ac3a1b3d409671684a7b684916a9" or
        p["captured_item_metadata_sha256"] != "bf03844257bba21b9b0ed2b3169892a74d33621e12002d5d0bafcc905e0dd8c7"):
        raise ValueError("unexpected captured item metadata")
    # Match the exact inventory hashed above, including rows with no original WAV.
    if len(list((rare / "nc-sa").glob("*.json"))) != r["reviewed_nc_sa"] or (
            len(list((pot / "cc0").glob("*.json"))) != p["cc0_catalog_items"] - len(p["absent_responses"])):
        raise ValueError("unexpected metadata directory contents")
    return dict(raretunes=count(rare / "nc-sa", set(r["candidates_for_manual_review"])),
                potpourri=count(pot / "cc0", set(p["candidate_ids"])))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation", type=Path)
    print(json.dumps(audit(parser.parse_args().validation), indent=2, sort_keys=True))
