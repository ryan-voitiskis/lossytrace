"""Verify two direct tracker exports, then make the six private single-stage controls."""
import argparse
import json
from pathlib import Path

import numpy as np
import soundfile as sf

import music_library_pilot_convert as codec
from music_verdict_beepbox_authored import check_wrapper, local_lag
from music_verdict_construction import packet_rate
from music_verdict_uge_sources import audit, SKYLINE

WEB_MANIFEST = "8f8b7dee0c744edc206717bb4d6e8750805534c60078932dacd34c2fc3c4c050"
SOURCE_WAV = "e33991eb70e88b5157427ec1fdf6637d6359f572a25d2164f39a6023fd0db410"


def construct(snapshot, output):
    work = audit(snapshot)["works"][SKYLINE]
    manifest = snapshot / "web-assets.json"
    if codec.sha(manifest) != WEB_MANIFEST:
        raise ValueError("editor asset inventory differs")
    for name, digest in json.loads(manifest.read_bytes()).items():
        if codec.sha(snapshot / "web" / name) != digest:
            raise ValueError("editor build differs")
    wav = snapshot / "skyline-1.wav"
    if any(codec.sha(path) != SOURCE_WAV for path in (wav, snapshot / "skyline-2.wav")):
        raise ValueError("one-pass render differs")
    pcm = codec.decode(wav, 16)
    sample_rate = 44100
    frames = len(pcm) // 4
    if not 0 <= frames - sample_rate * work["seconds_at_64hz"] < 2048:
        raise ValueError("export duration differs from linear score by at least one capture block")
    direct = check_wrapper(wav, pcm)
    channel = np.frombuffer(pcm, dtype="<i2").reshape(-1, 2)[:, 0]
    output.mkdir()
    credits = (f"{work['title']} by {work['artist']}. Source published under CC0.\n"
               "https://github.com/Beatscribe/homebrew_vgm/tree/5a82f88b87bb442499685c494b7a96278121b4c7\n"
               "One authored pass exported using GBS Music. Private LossyTrace codec constructions.\n")
    (output / "CREDITS.txt").write_text(credits)
    baseline = output / "direct.flac"
    codec.from_pcm(pcm, baseline, sample_rate, 16, flac=True)
    variants = {}
    for family, target in codec.CASES:
        key = f"{family}-{target}"
        intermediate = output / (key + (".mp3" if family == "mp3" else ".m4a"))
        codec.encode(wav, intermediate, family, target)
        codec.validate_stream(intermediate, sample_rate, family)
        decoded, tail = codec.trim(codec.decode(intermediate, 16), 16, frames)
        if pcm == decoded:
            raise ValueError("codec output unexpectedly equals source")
        flac = output / (key + ".flac")
        codec.from_pcm(decoded, flac, sample_rate, 16, flac=True)
        signal = np.frombuffer(decoded, dtype="<i2").reshape(-1, 2)[:, 0]
        variants[key] = dict(intermediate_sha256=codec.sha(intermediate),
                             decoded_tail_frames_removed=tail, **packet_rate(intermediate),
                             **check_wrapper(flac, decoded),
                             alignment=[local_lag(channel, signal, start)
                                        for start in (sample_rate, frames // 2, frames - sample_rate)])
    sources = [Path(__file__), Path(codec.__file__), Path(__file__).with_name("music_verdict_uge_sources.py"),
               Path(__file__).with_name("music_verdict_beepbox_authored.py"),
               Path(__file__).with_name("music_verdict_construction.py")]
    codec.save(output / "construction.json", dict(
        score_sha256=work["score_sha256"], editor_manifest_sha256=WEB_MANIFEST, direct=direct,
        frames=frames, native_rate=sample_rate, channels=2, bits=16, direct_flac=check_wrapper(baseline, pcm),
        variants=variants, split=None, scripts={s.name:codec.sha(s) for s in sources},
        toolchain=codec.toolchain(), numpy=np.__version__, libsndfile=sf.__libsndfile_version__))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    construct(args.snapshot, args.output)
