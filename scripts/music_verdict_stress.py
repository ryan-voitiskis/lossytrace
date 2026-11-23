"""Research-only negative stress controls, kept separate from the primary case matrix."""
from collections import Counter

import numpy as np
import soundfile as sf

import music_library_pilot_convert as codec
from music_library_pilot_nuisance import pcm_samples, quantize
from music_verdict_construction import pcm_hash, read_bound_pcm
from music_verdict_evaluation import OUTCOMES


CONDITIONS = ("lowpass12k", "quiet", "sparse", "short")
LOWPASS = ",".join(f"lowpass=f=12000:p=2:t=q:w={q}:a=di:r=f64:n=0:b=0"
                   for q in ("0.541196100146197", "1.306562964876377"))


def _apply(condition, raw, samples, bits, rate, channels):
    if condition == "short":
        return raw[:20 * rate * codec.pcm_stride(bits, channels)], 0
    if condition == "lowpass12k":
        rendered = codec.ff(["-f", "f64le", "-ar", rate, "-ac", channels, "-i", "pipe:0",
                             "-af", LOWPASS, "-threads", 1, "-c:a", "pcm_f64le", "-f", "f64le",
                             "pipe:1"], samples.astype("<f8").tobytes())
        changed = np.frombuffer(rendered, dtype="<f8").reshape(samples.shape)
    elif condition == "quiet":
        changed = .01 * samples
    elif condition == "sparse":
        fade_frames = round(.01 * rate)
        ramp = .5 - .5 * np.cos(np.pi * np.arange(fade_frames) / (fade_frames - 1))
        period = np.zeros(4 * rate)
        period[:rate] = 1
        period[:fade_frames] = ramp
        period[rate - fade_frames:rate] = ramp[::-1]
        changed = samples * period[np.arange(len(samples)) % len(period), None]
    else:
        raise ValueError("unexpected stress condition")
    return quantize(changed, bits, channels=channels)


def construct_stress(source, expected_sha256, folder, *, group, source_id):
    if not all(isinstance(x, str) and x.strip() for x in (group, source_id)):
        raise ValueError("expected a bound group and source ID")
    raw, bits, rate, channels, frames = read_bound_pcm(source, expected_sha256)
    samples = pcm_samples(raw, bits, channels=channels)
    folder.mkdir()
    rows = []
    for condition in CONDITIONS:
        output, clipped = _apply(condition, raw, samples, bits, rate, channels)
        expected_frames = 20 * rate if condition == "short" else frames
        path = folder / f"{condition}.flac"
        codec.from_pcm(output, path, rate, bits, flac=True, channels=channels)
        with sf.SoundFile(path) as stream:
            if (stream.format, stream.subtype, stream.channels, stream.samplerate, stream.frames) != (
                    "FLAC", f"PCM_{bits}", channels, rate, expected_frames):
                raise ValueError("unexpected stress FLAC format")
        if codec.decode(path, bits) != output:
            raise ValueError("stress control PCM readback failed")
        rows.append(dict(condition=condition, frames=expected_frames, path=path.name,
                         sha256=codec.sha(path), pcm_sha256=pcm_hash(output), clipped_samples=clipped))
    if codec.sha(source) != expected_sha256:
        raise ValueError("source changed during construction")
    manifest = dict(panel="stress-negative-v1", group=group, source_id=source_id, rate=rate,
                    bits=bits, channels=channels, source_frames=frames, source_sha256=expected_sha256,
                    source_pcm_sha256=pcm_hash(raw), controls=rows)
    codec.save(folder / "stress.json", manifest)
    return manifest


def summarize_stress(policy, expected_groups, scores, *, partition):
    """A missing key is missing output. Numeric logits are passed through the locked policy."""
    if (partition != "evaluation" or not isinstance(expected_groups, (list, tuple))
            or not expected_groups or not all(isinstance(s, str) and s.strip() for s in expected_groups)
            or len(expected_groups) != len(set(expected_groups))):
        raise ValueError("expected unique preallocated evaluation groups")
    if not isinstance(scores, dict) or scores.keys() - set(expected_groups):
        raise ValueError("unexpected stress score inventory")
    counts = {c: Counter(dict.fromkeys(OUTCOMES, 0)) for c in CONDITIONS}
    for group in expected_groups:
        cells = scores.get(group, {})
        if not isinstance(cells, dict) or cells.keys() - set(CONDITIONS):
            raise ValueError("unexpected stress case")
        for c in CONDITIONS:
            if c not in cells:
                outcome = "missing"
            elif isinstance(cells[c], str) and cells[c] == "unsupported":
                outcome = "unsupported"
            else:
                outcome, _ = policy.score(cells[c])
            counts[c][outcome] += 1
    n = len(expected_groups)
    short = counts["short"]
    return dict(conditions={c: dict(expected=n, outcomes=dict(totals),
                                    observed_false_alert_rate=totals["likely_lossy_derived"] / n,
                                    decision_coverage=(totals["likely_lossy_derived"] +
                                                       totals["no_evidence_detected"]) / n)
                            for c, totals in counts.items()},
                short_unexpected_decisions=n - short["unsupported"] - short["missing"],
                short_missing=short["missing"])
