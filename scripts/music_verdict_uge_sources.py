"""Read the pinned v5 tracker scores, including unused patterns and trailing routines."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

REVISION = "5a82f88b87bb442499685c494b7a96278121b4c7"
TREE_SHA256 = "6da4b5116c9bf66c50a35b5828a146f82f0540cbd058d556daffd9c6e67b658a"
FOLDER = "GB/free_demos/music_uge/"
SKYLINE = "bs-cyb-city-night-nodrum.uge"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def tracker(data):
    offset = 0

    def take(count):
        nonlocal offset
        raw = data[offset:offset + count]
        if len(raw) != count:
            raise ValueError("truncated UGE record")
        offset += count
        return raw

    def u32():
        return int.from_bytes(take(4), "little")

    def text():
        field = take(256)
        return field[1:1 + field[0]].decode()

    if u32() != 5:
        raise ValueError("requires UGE v5")
    title, artist, comment = text(), text(), text()
    instruments = [take(310) for _ in range(45)]
    if [struct.unpack_from("<I", i)[0] for i in instruments] != [0]*15 + [1]*15 + [2]*15:
        raise ValueError("unexpected instrument bank")
    waves = take(512)
    if max(waves) > 15:
        raise ValueError("invalid four-bit waveform")
    initial_speed = u32()
    patterns = {}
    for _ in range(u32()):
        index = u32()
        if index in patterns:
            raise ValueError("duplicate pattern identity")
        patterns[index] = list(struct.iter_unpack("<iiiB", take(64 * 13)))
    channels = []
    for _ in range(4):
        count = u32()
        if count < 2:
            raise ValueError("empty order list")
        channels.append(struct.unpack(f"<{count}I", take(count * 4))[:-1])
    if not (take(64) == bytes(64) and offset == len(data)):
        raise ValueError("unexpected custom routines or trailing data")
    notes = []
    events = Counter()
    ticks = 0
    speed = initial_speed
    for order, pattern_ids in enumerate(zip(*channels, strict=True)):
        for step, cells in enumerate(zip(*(patterns[k] for k in pattern_ids), strict=True)):
            for channel, (note, inst, fx, arg) in enumerate(cells):
                if note != 90:
                    notes.append([order, step, channel, note])
                if fx or arg:
                    events[fx] += 1
                if fx in (6, 11, 13):
                    raise ValueError("routine or non-linear sequence needs separate review")
                if fx == 15:
                    if arg == 0:
                        raise ValueError("unsupported zero speed")
                    speed = arg
            ticks += speed
    return dict(title=title, artist=artist, comment=comment, version=5, initial_speed=initial_speed,
                orders=len(channels[0]), stored_patterns=len(patterns), notes=len(notes),
                notes_sha256=sha(json.dumps(notes, separators=(",", ":")).encode()),
                instrument_bank_sha256=sha(b"".join(instruments)), wavetable_sha256=sha(waves),
                effect_counts=dict(sorted(events.items())), single_pass_ticks=ticks,
                seconds_at_64hz=ticks / 64, score_sha256=sha(data))


def audit(root):
    tree = (root / "tree.json").read_bytes()
    if sha(tree) != TREE_SHA256 or (root / "revision").read_text().strip() != REVISION:
        raise ValueError("unrecognized source tree")
    rows = json.loads(tree)
    if rows["truncated"]:
        raise ValueError("incomplete source tree")
    docs = {"README.md", "GB/free_demos/README.MD"}
    works, notices = {}, {}
    for f in rows["tree"]:
        path = f["path"]
        if path not in docs and not (path.startswith(FOLDER) and path.endswith(".uge")):
            continue
        data = (root / path).read_bytes()
        if hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest() != f["sha"]:
            raise ValueError("publisher blob mismatch")
        if path in docs:
            notices[path] = sha(data)
        else:
            works[Path(path).name] = tracker(data)
    return dict(revision=REVISION, source_tree_sha256=TREE_SHA256, notices=notices, works=works)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    print(json.dumps(audit(parser.parse_args().snapshot), indent=2))
