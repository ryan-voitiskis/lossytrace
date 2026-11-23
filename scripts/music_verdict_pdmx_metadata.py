"""Offline capacity and authorship screen of the two PDMX metadata files; never load notation or audio."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile
import unicodedata

from music_verdict_study import identity_components

BINDINGS = {"PDMX.csv": (225399738, "30392ccf38bb63ce70e7afae70f9c88c"),
            "metadata.tar.gz": (159444765, "5bc79445090dd2fe5e96cffa77a3461c")}
CC0 = "https://creativecommons.org/publicdomain/zero/1.0/"
OWN = re.compile(r"\b(?:i (?:wrote|composed|created) (?:this|the (?:music|piece|song))|my (?:own |original )composition)\b", re.I)
ADAPTATION = re.compile(r"\b(?:arrang(?:ed|ement)|transcri(?:bed|ption)|remix|orchestrat(?:ed|ion)|cover(?: of)?|adapted from)\b", re.I)


def normalize(s):
    return " ".join(unicodedata.normalize("NFKC", s).casefold().split())


def verify(root):
    record = json.loads((root / "record.json").read_bytes())
    if str(record["id"]) != "15571083":
        raise ValueError("unexpected PDMX release")
    files = {f["key"]: f for f in record["files"]}
    checks = {}
    for name, (size, digest) in BINDINGS.items():
        path = root / name
        if (files[name]["checksum"] != "md5:" + digest or files[name]["size"] != size or path.stat().st_size != size):
            raise ValueError("release manifest or file size mismatch")
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "md5").hexdigest() != digest:
                raise ValueError("metadata bytes differ from release")
        with path.open("rb") as stream:
            checks[name] = hashlib.file_digest(stream, "sha256").hexdigest()
    return checks


def inspect(root):
    bindings = verify(root)
    counts = Counter()
    rows = {}
    candidates = {}
    names = {}
    with (root / "PDMX.csv").open(newline="", encoding="utf-8") as stream:
        for r in csv.DictReader(stream):
            counts["indexed_scores"] += 1
            meta = Path(r["metadata"]).as_posix()
            if meta in rows:
                raise ValueError("duplicate metadata path")
            # Follow the provider's best_path links across the full index.
            linked = ["cluster:" + r["best_path"]] if r["best_path"] not in ("", "NA") else []
            rows[meta] = dict(source_id=r["path"], artist_ids=[], lineage_ids=linked)
            if r["license_conflict"] == "True":
                counts["copyright_conflict"] += 1
            if r["license_url"] != CC0 or r["license_conflict"] != "False" or r["is_original"] != "True":
                continue
            counts["cc0_consistent_flagged_original"] += 1
            if r["is_draft"] != "False" or r["has_custom_audio"] != "False" or r["has_paywall"] != "False":
                continue
            counts["also_non_draft_no_custom_audio_or_paywall"] += 1
            if (r["subset:all_valid"] != "True" or r["is_best_unique_arrangement"] != "True"
                    or float(r["song_length.seconds"]) < 30 or int(r["n_notes"]) < 1):
                continue
            candidates[meta] = int(r["n_tracks"])
    seen = set()
    excluded_raw = Counter()
    flag_disagreement = Counter()
    queryable = set()
    exact_credit = set()
    positive_text = set()
    adaptation_text = set()
    digital = set()
    example_ids = {"first_person":[], "arrangement":[], "exact_credit":[], "digital_lead":[]}
    with tarfile.open(root / "metadata.tar.gz", "r|gz", stream=True) as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".json"):
                continue
            key = Path(member.name).as_posix()
            if key not in rows or key in seen:
                raise ValueError("unindexed or duplicate metadata entry")
            seen.add(key)
            doc = json.load(archive.extractfile(member))
            data = doc["data"]
            s = data["score"]
            requested_id = Path(key).stem
            resolved_id = str(s["id"])
            rows[key]["lineage_ids"].extend(("score:" + requested_id, "score:" + resolved_id))
            if resolved_id != requested_id:
                counts["raw_score_id_differs_from_path"] += 1
                if key in candidates:
                    excluded_raw["raw_score_id_differs_from_path"] += 1
                continue
            credit = s.get("user") or {}
            uid = credit.get("id")
            if uid:
                rows[key]["artist_ids"].append("account:" + str(uid))
            song = (data.get("song") or {}).get("id")
            if song:
                rows[key]["lineage_ids"].append("song:" + str(song))
            name = normalize(s.get("composer_name") or "")
            if name and name not in {"na","n/a","unknown","anonymous","traditional","anon","various","composer"}:
                names[key] = name
            if key not in candidates:
                continue
            if not (s.get("is_original") and s.get("license") == "cc-zero"):
                flag_disagreement["original_or_license"] += 1
                continue
            if (not uid or s.get("is_private") or s.get("is_blocked") or data.get("opened_dispute")
                    or data.get("hidden") or data.get("is_blocked")):
                excluded_raw["no_account_or_private_blocked_disputed"] += 1
                continue
            queryable.add(key)
            description = s.get("body") or s.get("description") or ""
            if OWN.search(description):
                positive_text.add(key)
            if ADAPTATION.search(" ".join((s.get("title") or "", name, description))):
                adaptation_text.add(key)
            if key in names and names[key] == normalize(credit.get("name") or ""):
                exact_credit.add(key)
            if ((key in positive_text or key in exact_credit) and key not in adaptation_text
                    and re.search(r"\b(?:soundtrack|game music|video game|my game)\b", description, re.I)):
                digital.add(key)
            for label, subset in (("digital_lead", digital), ("first_person",positive_text), ("arrangement",adaptation_text), ("exact_credit",exact_credit)):
                if key in subset:
                    rank = hashlib.sha256(("lossytrace-pdmx-provenance-v1:" + key).encode()).hexdigest()
                    example_ids[label].append((rank, s["id"]))
    if rows.keys() != seen:
        raise ValueError("missing raw metadata")
    sets = {"digital_lead":digital, "score_screen":queryable, "multiple_notated_tracks":{k for k in queryable if candidates[k] >= 2},
            "exact_uploader_composer_credit":exact_credit, "first_person_description":positive_text,
            "adaptation_keyword":adaptation_text,
            "exact_credit_or_first_person_no_adaptation_keyword":(exact_credit | positive_text) - adaptation_text}
    by_id = {row["source_id"]:key for key,row in rows.items()}
    if len(by_id) != len(rows):
        raise ValueError("duplicate music-data path")
    groups = {}
    for mode in ("account_song_and_dataset_cluster", "also_shared_composer_string"):
        if mode == "also_shared_composer_string":
            for k, name in names.items():
                rows[k]["artist_ids"].append("composer:" + name)
        components = identity_components(list(rows.values()), ("artist_ids","lineage_ids"))
        lookup = {by_id[r["source_id"]]:i for i, members in enumerate(components) for r in members}
        groups[mode] = {label:len({lookup[k] for k in keys}) for label,keys in sets.items()}
    return dict(doi="10.5281/zenodo.15571083", sha256=bindings, filters=dict(counts),
                csv_candidates=len(candidates), raw_exclusions=dict(excluded_raw), disagreements=dict(flag_disagreement),
                stage_sizes={label:dict(scores=len(keys), uploader_accounts=len({rows[k]["artist_ids"][0] for k in keys}))
                             for label,keys in sets.items()}, reference_graph_counts=groups,
                manual_review_ids={label:[i for _,i in sorted(ids)[:5]] for label,ids in example_ids.items()})


if __name__ == "__main__":
    print(json.dumps(inspect(Path(sys.argv[1])), indent=2))
