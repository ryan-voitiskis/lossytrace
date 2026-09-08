from __future__ import annotations

import ast
import ctypes
import json
import math
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts")) if str(ROOT / "scripts") not in sys.path else None
import perceptual_degradation_alignment_v3 as V3
import perceptual_degradation_alignment_v4 as V4
import perceptual_degradation_alignment_runtime as FIX
import perceptual_degradation_correlation_native as N


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


class NativeEquivalenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary, cls.provenance = N.build(Path(cls.directory.name))
        cls.kernel = N.Kernel(cls.binary, cls.provenance["binary_sha256"])

    def check_search(self, a, b, lag=0, center=None, half=None, radius=9):
        center = len(a) // 2 if center is None else center
        half = len(a) // 3 if half is None else half
        start, end = max(0, center-half), min(len(a), center+half)
        window = a[start:end]
        expected = {lag+d: V3.correlate(window, b[start+lag+d:start+lag+d+len(window)], 0).record()
                    for d in range(-radius, radius+1)
                    if 0 <= start+lag+d and start+lag+d+len(window) <= len(b)}
        actual = {key: value.record() for key, value in self.kernel.results(a, b, lag, center, half, radius).items()}
        self.assertEqual(list(expected), list(actual))
        self.assertEqual(canonical(expected), canonical(actual))
        with patch.object(V4, "NATIVE_BACKEND", self.kernel):
            old = V3.local_lag(a, b, lag, center, half, radius)
            new = V4.local_lag(a, b, lag, center, half, radius)
        old["correlation"], new["correlation"] = old["correlation"].record(), new["correlation"].record()
        self.assertEqual(canonical(old), canonical(new))
        return actual

    def test_random_all_candidates_exact(self):
        rng = random.Random(740091)
        for size in (32, 67, 200, 501):
            for _ in range(12):
                a = [rng.uniform(-1, 1) for _ in range(size)]
                b = [rng.uniform(-1, 1) for _ in range(size+7)]
                self.check_search(a, b, lag=rng.randrange(-5, 6))

    def test_partial_sum_rounding_matches_fsum_bits(self):
        function = self.kernel.library.lt_test_sum
        function.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.POINTER(ctypes.c_double)]
        function.restype = ctypes.c_int
        rng = random.Random(672041)
        rows = [[], [0.0, -0.0], [1.0, 2**-53, 2**-1074], [-1.0, -2**-53, -2**-1074],
                [1.0, 2**-53, -1.0], [1.0, 2**-52, -2**-53, 2**-1074]]
        rows += [[math.ldexp(rng.uniform(-1, 1), rng.randrange(-1074, 1)) for _ in range(1000)] for _ in range(50)]
        for row in rows:
            for values in (row, list(reversed(row))):
                packed, result = (ctypes.c_double * len(values))(*values), ctypes.c_double()
                self.assertEqual(0, function(packed, len(values), ctypes.byref(result)))
                self.assertEqual(math.fsum(values).hex(), result.value.hex())

    def test_extreme_finite_subnormal_and_cancellation(self):
        rng = random.Random(44091)
        for scale_a in (1e-300, 1e300, 1.0, 2**-1074):
            for scale_b in (1e-300, 1e300, 1.0, 2**-1074):
                a = [rng.choice((-1.0, 0.0, 1.0, 0.25)) * scale_a for _ in range(97)]
                b = [rng.choice((-1.0, 0.0, 1.0, 0.25)) * scale_b for _ in range(97)]
                self.check_search(a, b)
        a = [math.ldexp(rng.uniform(-1, 1), rng.randrange(-1073, 1023)) for _ in range(300)]
        self.check_search(a, list(reversed(a)))

    def test_polarity_zero_and_constant_cosine(self):
        for a, b in (([1.0, -1.0]*40, [-1.0, 1.0]*40), ([0.0]*80, [1.0]*80),
                     ([1.0]*80, [0.0]*80), ([0.0]*80, [0.0]*80), ([0.125]*80, [0.125]*80)):
            self.check_search(a, b)

    def test_invalidity_precedes_zero_and_non_sampled_nan_is_ignored(self):
        for value in (float("nan"), float("inf"), -float("inf")):
            a, b = [0.0]*100, [0.0]*100
            b[50] = value
            self.check_search(a, b)
            self.check_search(b, a)
        a, b = [1.0]*32768, [1.0]*32768
        b[1] = float("nan")
        result = self.check_search(a, b, center=16384, half=16384, radius=0)
        self.assertIsNotNone(result[0]["value"])

    def test_floor_stride_boundary_and_full_window_length(self):
        rng = random.Random(2007)
        for window in (16383, 16384, 24000, 32767, 32768, 49152):
            a = [rng.uniform(-1, 1) for _ in range(window+40)]
            b = [rng.uniform(-1, 1) for _ in range(window+40)]
            result = self.check_search(a, b, center=window//2+20, half=window//2, radius=2)
            actual_length = 2*(window//2)
            expected = len(range(0, actual_length, max(1, actual_length//16384)))
            self.assertEqual(expected, result[0]["sampled_frames"])

    def test_integer_boolean_and_exotic_sequences_fall_back(self):
        for a in ([1, -1]*40, [True, False]*40, [10**400, 1]*40, range(80)):
            before = self.kernel.fallback_candidates
            self.check_search(a, list(a))
            self.assertGreater(self.kernel.fallback_candidates, before)

    def test_short_empty_and_clipped_boundaries(self):
        a = [1.0, -0.5]*40
        for center, half, lag, radius in ((0, 20, 0, 9), (80, 20, 0, 9), (40, 7, 0, 9),
                                         (40, 8, 500, 3), (40, 0, 0, 5), (40, 30, -7, 20)):
            self.check_search(a, a, lag, center, half, radius)

    def test_ties_near_ties_and_correlation_threshold_edges(self):
        self.check_search([1.0]*100, [1.0]*100, lag=3)
        a, b = [1.0, 0.0, -1.0, 0.0]*25, [0.0, 1.0, 0.0, -1.0]*25
        self.check_search(a, b, center=50, half=32, radius=1)
        with patch.object(V4, "NATIVE_BACKEND", self.kernel):
            self.assertEqual(-1, V4.local_lag(a, b, 0, 50, 32, 1)["lag_samples"])
        a = [1.0, -1.0]*50
        b = a.copy()
        b[60] = math.nextafter(b[60], 0.0)
        self.check_search(a, b, lag=1)
        a = [1.0, -1.0, 0.0, 0.0]*20
        for value in (math.nextafter(.2, 0.0), .2, math.nextafter(.2, 1.0)):
            b = [value, -value, math.sqrt(1-value*value), -math.sqrt(1-value*value)]*20
            self.check_search(a, b, radius=0)

    def test_capacity_or_environment_failure_uses_python(self):
        with patch.object(self.kernel, "call", return_value=-1):
            self.check_search([1.0, -.7]*40, [-.3, 1.0]*40)

    def test_native_unknown_status_and_wrong_binary_fail_closed(self):
        with self.assertRaises(ValueError):
            N.Kernel(self.binary, "0"*64)
        with patch.object(self.kernel, "call", return_value=17), self.assertRaises(RuntimeError):
            self.kernel.results([1.0]*80, [1.0]*80, 0, 40, 20, 3)

    def test_inputs_unchanged_and_native_path_exercised(self):
        a = tuple(float(i % 7-3) for i in range(100))
        before, count = (a, tuple(reversed(a))), self.kernel.candidates
        self.check_search(*before)
        self.assertEqual(before, (a, tuple(reversed(a))))
        self.assertGreater(self.kernel.candidates, count)

    def test_complete_small_alignment_matches_except_version_tag(self):
        a, _ = FIX.fixture("identity_baseline", frames=2400)
        variants = (a, tuple(tuple(-v for v in c) for c in a), (a[0], (0.0,)*2400),
                    tuple((0.0,)*3+c[:-3] for c in a))
        for b in variants:
            args = dict(reference_channels=a, test_channels=b, reference_channel_map=["L", "R"],
                        test_channel_map=["L", "R"], sample_rate_hz=200, recipe_identity="v4-small")
            expected = V3.align_channels(**args)
            with patch.object(V4, "NATIVE_BACKEND", self.kernel):
                actual = V4.align_channels(**args)
            self.assertEqual(V4.RECORD_KIND, actual.pop("record_kind"))
            expected.pop("record_kind")
            self.assertEqual(canonical(expected), canonical(actual))

    def test_constant_pearson_and_topology_are_unchanged(self):
        for kind in ("constant_envelope", "topology_mismatch"):
            a, b = FIX.fixture(kind, 100)
            args = dict(reference_channels=a, test_channels=b, reference_channel_map=["L", "R"],
                        test_channel_map=["M"] if len(b) == 1 else ["L", "R"],
                        sample_rate_hz=200, recipe_identity=kind)
            expected = V3.align_channels(**args)
            with patch.object(V4, "NATIVE_BACKEND", self.kernel):
                actual = V4.align_channels(**args)
            expected.pop("record_kind"), actual.pop("record_kind")
            self.assertEqual(canonical(expected), canonical(actual))

    def test_build_is_explicit_and_no_clobber(self):
        with self.assertRaises(FileExistsError):
            N.build(Path(self.directory.name))
        self.assertIsNone(V4.NATIVE_BACKEND)

    def test_other_alignment_functions_ast_identical(self):
        def definitions(module):
            return {node.name: ast.dump(node, include_attributes=False) for node in
                    ast.parse(Path(module.__file__).read_text()).body if isinstance(node, (ast.FunctionDef, ast.ClassDef))}
        old, new = definitions(V3), definitions(V4)
        old.pop("local_lag"), new.pop("local_lag")
        self.assertEqual(old, new)


if __name__ == "__main__":
    unittest.main()
