"""Reproduce and independently check the four generated stress controls at native formats."""
import argparse
from itertools import product
from pathlib import Path

import numpy as np
import soundfile as sf

import music_library_pilot_convert as codec
from music_library_pilot_nuisance import quantize
from music_verdict_candidate import analysis_intervals
from music_verdict_stress import construct_stress

TONES = (1000, 12000, 18000)


def run(folder):
    folder.mkdir()
    results = []
    for rate, bits, channels in product((44100, 48000), (16, 24), (1, 2)):
        name = f"{rate}-{bits}-{channels}"
        # End partway through the last fade-in to exercise truncated sparse periods.
        frames = 32 * rate + 123
        t = np.arange(frames) / rate
        signal = np.column_stack([sum(.13 * np.sin(2 * np.pi * f * t + .7 * ch + .3)
                                      for f in TONES) for ch in range(channels)])
        raw, clipped = quantize(signal, bits, channels=channels)
        if clipped:
            raise ValueError("fixture clipped")
        path = folder / (name + ".wav")
        codec.from_pcm(raw, path, rate, bits, channels=channels)
        source, _ = sf.read(path, dtype="int32", always_2d=True)
        source >>= 32 - bits
        manifest = construct_stress(path, codec.sha(path), folder / name, group=name, source_id=name)
        measurements = {}
        for row in manifest["controls"]:
            c = row["condition"]
            samples, observed_rate = sf.read(folder / name / row["path"], dtype="int32", always_2d=True)
            samples >>= 32 - bits
            if observed_rate != rate or row["clipped_samples"]:
                raise ValueError("unexpected readback format or clipping")
            if c == "short":
                np.testing.assert_array_equal(samples, source[:20 * rate])
                try:
                    analysis_intervals(len(samples), rate)
                except ValueError as exc:
                    if "unsupported duration" not in str(exc):
                        raise
                else:
                    raise ValueError("short control entered analysis")
            else:
                analysis_intervals(len(samples), rate)
            if c == "quiet":
                np.testing.assert_array_equal(samples, np.rint(source * .01))
            if c == "sparse":
                phase = np.arange(frames) % (rate * 4)
                edge = np.minimum(phase, rate - 1 - phase)
                fraction = np.clip(edge / (round(.01 * rate) - 1), 0, 1)
                reference = source * (.5 * (1 - np.cos(np.pi * fraction)))[:, None]
                np.testing.assert_array_equal(samples, np.rint(reference))
            if c == "lowpass12k":
                input_bins = np.fft.rfft(source[rate:2 * rate], axis=0)
                output_bins = np.fft.rfft(samples[rate:2 * rate], axis=0)
                for f in TONES:
                    db = 20 * np.log10(np.abs(output_bins[f] / input_bins[f]))
                    expected = -10 * np.log10(1 + (np.tan(np.pi * f / rate) /
                                                    np.tan(np.pi * 12000 / rate)) ** 8)
                    np.testing.assert_allclose(db, expected, rtol=0, atol=.025)
                    measurements[str(f)] = db.round(5).tolist()
        results.append(dict(fixture=name, frames=frames, stress_manifest=codec.sha(folder/name/"stress.json"),
                            lowpass_response_db=measurements))
    codec.save(folder / "summary.json", dict(generated_sources=len(results), controls=4 * len(results),
                                             formal_groups=0, model_fits=0, rows=results))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    run(parser.parse_args().output)
