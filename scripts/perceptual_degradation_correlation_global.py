"""Explicit native global-search extension; no automatic build or audio IO."""
from __future__ import annotations

from collections import Counter
import ctypes
import math
from pathlib import Path
import platform
import shutil
import subprocess

import perceptual_degradation_alignment_v4 as reference
import perceptual_degradation_correlation_native as local

SOURCE = Path(__file__).with_suffix(".c")
FLAGS = local.FLAGS
MAX_FRAMES = 1048576
sha = local.sha


def build(directory):
    directory = Path(directory).resolve(strict=True)
    output = directory / ("correlation.dylib" if platform.system() == "Darwin" else "correlation.so")
    if output.exists() or output.is_symlink():
        raise FileExistsError(output.name)
    compiler = Path(shutil.which("cc") or "missing-compiler").resolve(strict=True)
    version = subprocess.check_output([str(compiler), "--version"], timeout=10).decode().splitlines()[:3]
    subprocess.run([str(compiler), *FLAGS, str(SOURCE), "-o", str(output), "-lm"],
                   check=True, capture_output=True, timeout=60)
    output.chmod(0o500)
    return output, {"source_sha256": sha(SOURCE), "included_source_sha256": sha(local.SOURCE),
                    "binary_sha256": sha(output), "compiler_sha256": sha(compiler),
                    "compiler_version": version, "flags": list(FLAGS), "link_libraries": ["m"],
                    "platform": platform.system(), "machine": platform.machine(),
                    "os_release": platform.release(), "compiler_dependency_closure_claimed": False}


class Kernel(local.Kernel):
    """Inherit unchanged local searches; global searches have separate counters."""
    def __init__(self, path, expected_sha256):
        super().__init__(path, expected_sha256)
        pointer = ctypes.POINTER(ctypes.c_double)
        self.global_call = self.library.lt_global_cosine
        self.global_call.argtypes = [pointer, pointer, ctypes.c_size_t, ctypes.c_size_t,
                                    pointer, pointer, pointer]
        self.global_call.restype = ctypes.c_int
        self.global_candidates = 0
        self.global_fallback_candidates = 0
        self.global_short_candidates = 0
        self.global_search_counts = Counter()
        self.global_geometry_counts = Counter()

    def global_results(self, a, b, lags):
        if (type(lags) not in (list, tuple) or any(type(lag) is not int for lag in lags)
                or len(set(lags)) != len(lags)):
            raise ValueError("unique integer candidate inventory required")
        self.global_search_counts[(len(a), len(b), len(lags))] += 1
        if not lags:
            return {}
        eligible = (type(a) in (list, tuple) and type(b) in (list, tuple)
                    and len(a) <= MAX_FRAMES and len(b) <= MAX_FRAMES
                    and all(type(v) is float for values in (a, b) for v in values))
        if not eligible:
            self.global_fallback_candidates += len(lags)
            return {lag: reference.correlate(a, b, lag) for lag in lags}
        packed_a, packed_b = (ctypes.c_double * len(a))(*a), (ctypes.c_double * len(b))(*b)
        pointer = ctypes.POINTER(ctypes.c_double)
        numerator, energy_a, energy_b = ctypes.c_double(), ctypes.c_double(), ctypes.c_double()
        results = {}
        for lag in lags:
            start_a, start_b, length = reference.legacy._overlap(len(a), len(b), lag)
            if length < 16:
                self.global_short_candidates += 1
                results[lag] = reference.Correlation(None, "insufficient_overlap", length, 0)
                continue
            stride = max(1, length // reference.legacy.MAX_CORRELATION_SAMPLES)
            count = len(range(0, length, stride))
            self.global_geometry_counts[(length, stride, count)] += 1
            code = self.global_call(
                ctypes.cast(ctypes.byref(packed_a, start_a * 8), pointer),
                ctypes.cast(ctypes.byref(packed_b, start_b * 8), pointer), count, stride,
                ctypes.byref(numerator), ctypes.byref(energy_a), ctypes.byref(energy_b))
            self.global_candidates += 1
            if code == -1:
                self.global_fallback_candidates += 1
                result = reference.correlate(a, b, lag)
            elif code in (1, 2):
                result = reference.Correlation(None, "zero_energy" if code == 1 else "invalid_numeric_input", length, count)
            elif code == 0:
                value = numerator.value / (math.sqrt(energy_a.value) * math.sqrt(energy_b.value))
                result = (reference.Correlation(None, "numeric_failure", length, count)
                          if not math.isfinite(value) or abs(value) > 1 + 1e-12 else
                          reference.Correlation(max(-1.0, min(1.0, value)), None, length, count))
            else:
                raise RuntimeError("unknown global correlation status")
            results[lag] = result
        return results

    def global_record(self):
        return {"native_candidates": self.global_candidates,
                "fallback_candidates": self.global_fallback_candidates,
                "short_overlap_candidates": self.global_short_candidates,
                "searches": [{"reference_frames": key[0], "test_frames": key[1],
                              "candidate_count": key[2], "search_count": value}
                             for key, value in sorted(self.global_search_counts.items())],
                "geometries": [{"overlap_frames": key[0], "stride": key[1],
                                "sampled_frames": key[2], "candidate_count": value}
                               for key, value in sorted(self.global_geometry_counts.items())]}
