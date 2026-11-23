"""Private primary-case construction. The caller supplies a qualified, bound source and allocation."""
from fractions import Fraction
import hashlib
import json

import soundfile as sf

import music_library_pilot_convert as codec
from music_library_pilot_nuisance import process
from music_verdict_calibration import CONDITIONS, STATES


def pcm_hash(raw):
    return hashlib.sha256(raw).hexdigest()


def packet_rate(path):
    data = json.loads(codec.run([codec.FFPROBE, "-v", "error", "-select_streams", "a:0",
                                 "-show_packets", "-show_entries", "packet=size,duration:stream=time_base",
                                 "-of", "json", path]))
    packets = data["packets"]
    seconds = Fraction(data["streams"][0]["time_base"]) * sum(int(p["duration"]) for p in packets)
    size = sum(int(p["size"]) for p in packets)
    return dict(packets=len(packets), packet_bytes=size, packet_duration_seconds=float(seconds),
                mean_packet_bits_per_second=float(size * 8 / seconds))


def construct_primary(source, expected_sha256, folder, *, group, source_id, partition, seed,
                      precondition="identity"):
    if (partition not in ("train", "selection", "calibration", "evaluation")
            or not all(isinstance(s, str) and s.strip() for s in (group, source_id))
            or type(seed) is not int or seed < 0 or precondition not in CONDITIONS
            or (partition != "train" and precondition != "identity")):
        raise ValueError("invalid source allocation or preprocessing recipe")
    if codec.sha(source) != expected_sha256:
        raise ValueError("source file commitment mismatch")
    with sf.SoundFile(source) as stream:
        rate, channels, frames = stream.samplerate, stream.channels, stream.frames
        if (stream.format not in ("FLAC", "WAV", "WAVEX") or stream.subtype not in ("PCM_16", "PCM_24")
                or rate not in (44100, 48000) or channels not in (1, 2) or frames < rate * 30):
            raise ValueError("source outside supported PCM scope")
        bits = int(stream.subtype[4:])
    native = codec.decode(source, bits)
    if len(native) != frames * codec.pcm_stride(bits, channels):
        raise ValueError("source header and decoded frame count disagree")
    folder.mkdir()  # The completion manifest is written only after all checks.
    encoder_source = folder / "base.wav"
    pre_seed = seed ^ 0x80000000
    base_bits = bits
    before = None
    if precondition != "identity":
        native, base_bits, before = process(native, bits, rate, precondition, pre_seed, channels=channels,
                                            match_resampled_length=True)
    codec.from_pcm(native, encoder_source, rate, base_bits, channels=channels)
    if codec.decode(encoder_source, base_bits) != native:
        raise ValueError("encoder input PCM mismatch")
    base_sha = pcm_hash(native)
    base_id = source_id + ":" + base_sha
    encodes = {}
    cases = []
    for state in STATES:
        pcm = native
        if state != "baseline":
            family, target = state.split("-")
            path = folder / (state + (".mp3" if family == "mp3" else ".m4a"))
            codec.encode(encoder_source, path, family, int(target))
            codec.validate_stream(path, rate, family, channels=channels)
            pcm, trimmed = codec.trim(codec.decode(path, base_bits), base_bits, frames, channels=channels)
            encodes[state] = dict(file=path.name, sha256=codec.sha(path), input_pcm_sha256=base_sha,
                                  target_kbps=int(target), trailing_decoder_frames_removed=trimmed,
                                  decoded_pcm_sha256=pcm_hash(pcm), **packet_rate(path))
        for condition in CONDITIONS:
            output, depth, processing = process(pcm, base_bits, rate, condition, seed, channels=channels,
                                                match_resampled_length=True)
            path = folder / f"{state}-{condition}.flac"
            codec.from_pcm(output, path, rate, depth, flac=True, channels=channels)
            with sf.SoundFile(path) as check:
                if (check.channels, check.samplerate, check.frames, check.subtype) != (
                        channels, rate, frames, f"PCM_{depth}"):
                    raise ValueError("output native format mismatch")
            if codec.decode(path, depth) != output:
                raise ValueError("FLAC readback differs from intended PCM")
            cases.append(dict(group=group, source_id=base_id, partition=partition, state=state,
                              condition=condition, path=path.name, sha256=codec.sha(path), rate=rate,
                              channels=channels, bits=depth, frames=frames, pcm_sha256=pcm_hash(output),
                              processing=processing))
    if codec.sha(source) != expected_sha256:
        raise ValueError("source changed during construction")
    manifest = dict(source_id=source_id, source_sha256=expected_sha256, base_pcm_sha256=base_sha,
                    precondition=precondition, preprocessing=before, preprocessing_seed=pre_seed, seed=seed,
                    base_file_sha256=codec.sha(encoder_source), encodes=encodes, cases=cases)
    codec.save(folder / "construction.json", manifest)
    return manifest
