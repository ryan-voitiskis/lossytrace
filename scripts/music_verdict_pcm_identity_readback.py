"""Check wrapper-independent identities on retained, previously constructed finished works."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import music_library_pilot_convert as codec
from music_verdict_pcm_identity import DOMAIN, identify
from music_verdict_study import identity_components


RESEARCH = Path(__file__).resolve().parents[1] / "research/music-verdict-v1"


def sources(root):
    beep = json.loads((RESEARCH / "beepbox-construction-20261124.json").read_bytes())
    for work in beep["works"]:
        title = work["render"]["title"]
        folder = root / "beepbox-authored-20261124-002" / title.lower().replace(" ", "-")
        for filename, entry in work["originals"].items():
            yield title, "direct", folder / filename, entry
        for entry in work["variants"]:
            state = f"{entry['family']}-{entry['kbps']}"
            yield title, state, folder / (state + ".flac"), entry
    island = json.loads((RESEARCH / "island-construction-20261124.json").read_bytes())["files"]
    for name in ("score.wav", "direct.flac", "roundtrip.flac"):
        folder = "island-render-20261124-003" if name == "score.wav" else "island-construction-pair-20261124-001"
        yield "Island Not Found", "mp3-128" if name == "roundtrip.flac" else "direct", root / folder / name, island[name]
    uge = json.loads((RESEARCH / "uge-construction-20261124.json").read_bytes())
    yield "3am Skyline", "direct", root / "beatscribe-tracker-20261124-001/skyline-1.wav", uge["direct"]
    folder = root / "uge-codec-construction-20261124-002"
    yield "3am Skyline", "direct", folder / "direct.flac", uge["direct_flac"]
    for state, entry in uge["variants"].items():
        yield "3am Skyline", state, folder / (state + ".flac"), entry


def verify(root):
    rows = []
    result = {}
    for title, state, path, entry in sources(root):
        key = identify(path, entry["file_sha256"])
        demux = path.suffix[1:]
        raw = codec.decode(path, 16, container=demux)
        if hashlib.sha256(raw).hexdigest() != entry["s16le_sha256"]:
            raise ValueError("historical native sample commitment changed")
        canonical = codec.ff(["-f", demux, "-i", path, "-map", "0:a:0", "-c:a", "pcm_s32le",
                              "-f", "s32le", "pipe:1"])
        header = struct.pack("<IHQ", key["rate"], key["channels"], key["frames"])
        h = hashlib.sha256(DOMAIN + header)
        h.update(canonical)
        if len(canonical) != key["frames"] * key["channels"] * 4 or h.hexdigest() != key["canonical_pcm_sha256"]:
            raise ValueError("decoder disagreement on canonical PCM")
        keys = result.setdefault(title, {})
        if state in keys and keys[state] != key["canonical_pcm_sha256"]:
            raise ValueError("lossless wrappers disagree")
        keys[state] = key["canonical_pcm_sha256"]
        rows.append(dict(**key, lineage_ids=[title]))
    return dict(files=len(rows), file_hash_groups=len(identity_components(rows, ("audio_sha256",))),
                exact_pcm_groups=len(identity_components(rows, ("canonical_pcm_sha256",))),
                source_work_groups=len(identity_components(rows, ("canonical_pcm_sha256", "lineage_ids"))),
                pcm_by_work_and_construction=result, formal_allocations=0)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("validation", type=Path)
    print(json.dumps(verify(parser.parse_args().validation), indent=2))
