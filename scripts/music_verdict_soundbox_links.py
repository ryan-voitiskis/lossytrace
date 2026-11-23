"""Compare retained editable scores to the executed timeline of separately parsed game exports."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import struct
import zlib


ROOT = Path(__file__).resolve().parents[1]
ARRANGEMENTS = ROOT / "research/music-verdict-v1/js13k-scores-20261124.json"
SOURCES = {
    "island-not-found": ("post-mortem.md", "1df389954ae6bf6f5b10e8a11a9ab77bd13cbe9cca72c92241ed8f0d2aa554b1"),
    "miami-mice": ("text/music_nd_Sound.md", "c1bb6260bcbb9b17169dceffecc01695c1070852b8de3d9a3a96f81018baebe0"),
    "submersible-warship-2063": ("README.md", "cb0bb7aeab34952d5cbafeeefdd745fbbbcdd96fdd2e473c4fa431ec63e0c9e2"),
    "witchcup1276": ("README.md", "87a32532dfc2c998947b2c55e48c60d0ed8efea1b663a94cb9c642a5fef7004e"),
}


def bound(path, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("retained score evidence changed")
    return raw


def digest(value):
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def score(url_data):
    packed = base64.urlsafe_b64decode(url_data + "=" * (-len(url_data) % 4))
    version = packed[4]
    if packed[:4] != b"SBox" or version not in (12, 14) or packed[5] != 2:
        raise ValueError("expected one of the two reviewed DEFLATE score formats")
    decoder = zlib.decompressobj(-15)
    raw = decoder.decompress(packed[6:], 256 * 1024)
    if not decoder.eof or decoder.unused_data:
        raise ValueError("incomplete, excessive or trailing score data")
    row_frames, end, rows, channels = struct.unpack_from("<IHBB", raw)
    width = 28 if version == 12 else 29
    position = 8
    if len(raw) != position + channels * (width + end + 1 + 36 * rows * 6):
        raise ValueError("score dimensions disagree with payload")
    if not (0 < rows and 0 < channels <= 16 and end < 512 and row_frames > 0):
        raise ValueError("unexpected published score dimensions")
    timeline = []
    notes = []
    for channel in range(channels):
        instrument = list(raw[position:position + width])
        position += width
        schedule = raw[position:position + end + 1]
        position += end + 1
        empty = [[0] * (4 * rows), [0] * (2 * rows)]
        patterns = [empty]
        for _ in range(36):
            pitches = list(raw[position:position + rows * 4])
            effects = list(raw[position + rows * 4:position + rows * 6])
            patterns.append([pitches, effects])
            position += 6 * rows
        played = [patterns[i] for i in schedule]
        timeline.append([instrument, played])
        for bar, (pitches, _) in enumerate(played):
            for index, pitch in enumerate(pitches):
                if pitch:
                    notes.append([(bar * rows + index % rows) * row_frames,
                                  channel, index // rows, pitch])
    return dict(version=version, packed_sha256=hashlib.sha256(packed).hexdigest(),
                frames=(end + 1) * rows * row_frames, channels=channels, note_count=len(notes),
                notes=digest(sorted(notes)), program=digest([row_frames, rows, end, timeline]))


def compare(snapshot):
    shipped = json.loads(bound(ARRANGEMENTS, "37a5bdcf34e64587cde77e8adcbad09000654faaf94e3287d1ec6d500b600957"))["arrangements"]
    found = {}
    for project, (file, sha) in SOURCES.items():
        text = bound(snapshot / project / file, sha).decode()
        results = []
        for token in re.findall(r"https?://sb\.bitsnbites\.eu/\?data=([a-zA-Z0-9_-]+)", text):
            detail = score(token)
            candidates = [r for r in shipped if r["name"] == project]
            detail["identical_note_export_lines"] = [
                r["source_line"] for r in candidates if r["note_event_sha256"] == detail["notes"]]
            detail["identical_program_export_lines"] = [
                r["source_line"] for r in candidates if r["expanded_program_sha256"] == detail["program"]]
            results.append(detail)
        found[project] = results
    return found


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    print(json.dumps(compare(parser.parse_args().snapshot), indent=2))
