"""Count shared tracker objects across the retained public Game Boy project trees."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path

LABELS = {"MIT", "CC0-1.0", "Unlicense", "CC-BY-4.0", "Apache-2.0", "Zlib"}


def audit(folder):
    projects = {}
    digests = {}
    for topic in ("gb-studio", "gbstudio", "hugetracker"):
        data = (folder / (topic + "-1.json")).read_bytes()
        digests[topic] = hashlib.sha256(data).hexdigest()
        page = json.loads(data)
        if page["incomplete_results"] or page["total_count"] != len(page["items"]):
            raise ValueError("incomplete topic result")
        projects.update({r["id"]: r for r in page["items"]})
    eligible = {k:r for k, r in projects.items() if (r.get("license") or {}).get("spdx_id") in LABELS}
    reviewed = {}
    objects = defaultdict(list)
    for file in sorted((folder / "trees").glob("*.json")):
        project = eligible[int(file.stem)]
        name = project["full_name"]
        data = file.read_bytes()
        tree = json.loads(data)
        if tree["truncated"] or tree["url"].split("/git/trees/")[0] != project["url"]:
            raise ValueError("incomplete or mismatched tree")
        files = {r["path"]: r["sha"] for r in tree["tree"] if r["type"] == "blob"
                 and r["path"].lower().endswith((".uge", ".mod"))}
        for path, sha in files.items():
            objects[sha].append((name, path))
        reviewed[name] = dict(tree_sha=tree["sha"], captured_sha256=hashlib.sha256(data).hexdigest(),
                              tracker_files=len(files), distinct_tracker_blobs=len(set(files.values())))
    return dict(topic_sha256=digests, unique_projects=len(projects), selected_by_repository_label=len(eligible),
                trees_read=len(reviewed), tracker_file_occurrences=sum(map(len, objects.values())),
                distinct_tracker_blobs=len(objects),
                shared_between_repositories=sum(len({name for name, _ in rows}) > 1 for rows in objects.values()),
                reviewed=reviewed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    print(json.dumps(audit(parser.parse_args().snapshot), indent=2, sort_keys=True))
