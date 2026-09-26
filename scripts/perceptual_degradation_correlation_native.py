"""Explicit opt-in native local-search backend; no auto-build or audio IO."""
from __future__ import annotations

import ctypes
import hashlib
import math
from pathlib import Path
import platform
import shutil
import subprocess

import perceptual_degradation_alignment_v3 as reference

SOURCE = Path(__file__).with_suffix(".c")
FLAGS = ("-O2", "-std=c11", "-shared", "-fPIC", "-fno-fast-math", "-ffp-contract=off",
         "-Wall", "-Wextra", "-Werror")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(directory):
    """Build only on explicit request, to a new caller-owned output path."""
    directory = Path(directory).resolve(strict=True)
    output = directory / ("correlation.dylib" if platform.system() == "Darwin" else "correlation.so")
    if output.exists():
        raise FileExistsError(output.name)
    compiler = Path(shutil.which("cc") or "missing-compiler").resolve(strict=True)
    version = subprocess.check_output([str(compiler), "--version"], timeout=10).decode().splitlines()[:3]
    subprocess.run([str(compiler), *FLAGS, str(SOURCE), "-o", str(output), "-lm"],
                   check=True, capture_output=True, timeout=60)
    output.chmod(0o500)
    return output, {"source_sha256": sha(SOURCE), "binary_sha256": sha(output),
                    "compiler_sha256": sha(compiler), "compiler_version": version,
                    "flags": list(FLAGS), "link_libraries": ["m"],
                    "platform": platform.system(), "machine": platform.machine(),
                    "os_release": platform.release(),
                    "compiler_dependency_closure_claimed": False}


class Kernel:
    def __init__(self, path, expected_sha256):
        if sha(path) != expected_sha256:
            raise ValueError("native binary binding differs")
        self.library = ctypes.CDLL(str(Path(path).resolve(strict=True)))
        double_ptr = ctypes.POINTER(ctypes.c_double)
        self.library.lt_environment.argtypes = []
        self.library.lt_environment.restype = ctypes.c_int
        self.call = self.library.lt_cosine
        self.call.argtypes = [double_ptr, double_ptr, ctypes.c_size_t, ctypes.c_size_t,
                              ctypes.c_int, double_ptr, double_ptr]
        self.call.restype = ctypes.c_int
        if self.library.lt_environment() != 1:
            raise ValueError("native arithmetic environment unsupported")
        self.candidates = 0
        self.fallback_candidates = 0
        self.search_counts = {}

    def results(self, a, b, global_lag, center, half_window, radius):
        """Same ascending complete lag inventory, slicing and floor stride as v3.

        Only exact-float list/tuple inputs enter native arithmetic. All other
        sequences and ints retain Python's validation/division semantics. Each
        native call evaluates one lag so Python handles alarms between lags.
        """
        start, end = max(0, center - half_window), min(len(a), center + half_window)
        window = a[start:end]
        lags = [global_lag + d for d in range(-radius, radius + 1)
                if 0 <= start + global_lag + d and start + global_lag + d + len(window) <= len(b)]
        geometry = (len(window), max(1, len(window) // reference.legacy.MAX_CORRELATION_SAMPLES), len(lags))
        self.search_counts[geometry] = self.search_counts.get(geometry, 0) + 1
        if not lags:
            return {}
        def fallback():
            self.fallback_candidates += len(lags)
            return {lag: reference.correlate(window, b[start+lag:start+lag+len(window)], 0) for lag in lags}
        base, stop = start + lags[0], start + lags[-1] + len(window)
        segment = b[base:stop]
        length = len(window)
        if (type(a) not in (tuple, list) or type(b) not in (tuple, list) or not 16 <= length <= 576008
                or not all(type(x) is float for x in (*window, *segment))):
            return fallback()
        stride = max(1, length // reference.legacy.MAX_CORRELATION_SAMPLES)
        x = window[::stride]
        if not all(math.isfinite(value) for value in x):
            return fallback()
        scale = max(map(abs, x))
        x = [value / scale for value in x] if scale else list(x)
        energy_x = math.fsum(value * value for value in x)
        packed_x = (ctypes.c_double * len(x))(*x)
        packed_b = (ctypes.c_double * len(segment))(*segment)
        numerator, energy_y = ctypes.c_double(), ctypes.c_double()
        results = {}
        for lag in lags:
            pointer = ctypes.cast(ctypes.byref(packed_b, (start + lag - base) * 8), ctypes.POINTER(ctypes.c_double))
            code = self.call(packed_x, pointer, len(x), stride, not scale,
                             ctypes.byref(numerator), ctypes.byref(energy_y))
            self.candidates += 1
            if code == -1:
                self.fallback_candidates += 1
                result = reference.correlate(window, b[start+lag:start+lag+length], 0)
            elif code in (1, 2):
                result = reference.Correlation(None, "zero_energy" if code == 1 else "invalid_numeric_input", length, len(x))
            elif code == 0:
                value = numerator.value / (math.sqrt(energy_x) * math.sqrt(energy_y.value))
                result = (reference.Correlation(None, "numeric_failure", length, len(x))
                          if not math.isfinite(value) or abs(value) > 1 + 1e-12 else
                          reference.Correlation(max(-1.0, min(1.0, value)), None, length, len(x)))
            else:
                raise RuntimeError("unknown native correlation status")
            results[lag] = result
        return results

    def record(self):
        return {"native_candidates": self.candidates, "fallback_candidates": self.fallback_candidates,
                "searches": [{"window_frames": key[0], "stride": key[1], "candidate_count": key[2], "search_count": count}
                             for key, count in sorted(self.search_counts.items())]}
