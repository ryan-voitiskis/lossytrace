"""Bounded constructed equivalence tests; no retained waveform or codec IO."""
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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import perceptual_degradation_alignment_v4 as V4
import perceptual_degradation_alignment_v5 as V5
import perceptual_degradation_alignment_runtime as fixtures
import perceptual_degradation_correlation_global as N


def canonical(value):
    return json.dumps(value, sort_keys=True, allow_nan=False).encode()


class GlobalEquivalenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.binary, cls.provenance = N.build(cls.directory.name)

    def setUp(self):
        self.kernel = N.Kernel(self.binary, self.provenance["binary_sha256"])

    def compare(self, a, b, lags=tuple(range(-9, 10))):
        expected = {lag: V4.correlate(a, b, lag).record() for lag in lags}
        actual = {lag: result.record() for lag, result in self.kernel.global_results(a, b, lags).items()}
        self.assertEqual(list(expected), list(actual))
        self.assertEqual(canonical(expected), canonical(actual))
        return actual

    def test_random_all_candidates_exact(self):
        rng = random.Random(580042)
        for size in (16, 31, 97, 251, 501):
            for _ in range(12):
                self.compare([rng.uniform(-1, 1) for _ in range(size)],
                             [rng.uniform(-1, 1) for _ in range(size+7)])

    def test_extreme_finite_scales_and_cancellation(self):
        rng = random.Random(180223)
        for x in (1e-300, 1e300, 1.0, 2**-1074):
            for y in (1e-300, 1e300, 1.0, 2**-1074):
                self.compare([rng.choice((-1.0, 0.0, .25, 1.0))*x for _ in range(97)],
                             [rng.choice((-1.0, 0.0, .25, 1.0))*y for _ in range(97)])
        a = [math.ldexp(rng.uniform(-1, 1), rng.randrange(-1073, 1023)) for _ in range(200)]
        self.compare(a, list(reversed(a)))

    def test_zero_constant_signed_and_invalid_precedence(self):
        for a, b in (([0.0]*80, [0.0]*80), ([1.0]*80, [0.0]*80),
                     ([.125]*80, [.125]*80), ([1.0, -1.0]*40, [-1.0, 1.0]*40)):
            self.compare(a, b)
        for invalid in (float("nan"), float("inf"), -float("inf")):
            a, b = [0.0]*80, [0.0]*80
            a[40] = invalid
            self.compare(a, b)
            self.compare(b, a)

    def test_stride_boundaries_and_unsampled_nan(self):
        rng = random.Random(201417)
        for size in (16383, 16384, 24000, 32767, 32768, 49152):
            a = [rng.uniform(-1, 1) for _ in range(size)]
            self.compare(a, list(reversed(a)), [-2, -1, 0, 1, 2])
        a, b = [1.0]*32768, [1.0]*32768
        b[1] = float("nan")
        self.assertIsNotNone(self.compare(a, b, [0])[0]["value"])
        self.assertIsNone(self.compare(a, b, [1])[1]["value"])

    def test_short_empty_large_lag_and_order(self):
        for size in (0, 1, 15, 16, 17, 31):
            a = [1.0]*size
            self.compare(a, a, [1000000, -1000000, 7, 0, -7])
        self.assertEqual({}, self.kernel.global_results([], [], []))

    def test_exotic_and_oversize_use_python_semantics(self):
        for a in ([1, -1]*40, [True, False]*40, [10**400, 1]*40, range(80)):
            self.compare(a, list(a))
        with patch.object(N, "MAX_FRAMES", 79):
            self.compare([1.0]*80, [1.0]*80)
        self.assertGreater(self.kernel.global_fallback_candidates, 0)

    def test_environment_capacity_and_unknown_status(self):
        with patch.object(self.kernel, "global_call", return_value=-1):
            self.compare([1.0, -.3]*40, [-.5, 1.0]*40)
        with patch.object(self.kernel, "global_call", return_value=17), self.assertRaises(RuntimeError):
            self.kernel.global_results([1.0]*80, [1.0]*80, [0])

    def test_invalid_candidate_inventory_rejected(self):
        for lags in ([True], [0.0], [0, 0], range(4)):
            with self.assertRaises(ValueError):
                self.kernel.global_results([1.0]*80, [1.0]*80, lags)

    def test_candidate_inventory_and_inputs_preserved(self):
        a, b = tuple(float(i%7-3) for i in range(100)), tuple(float(i%5-2) for i in range(103))
        before = canonical([a, b])
        self.compare(a, b, [-1000, -1, 0, 1, 1000])
        self.assertEqual(before, canonical([a, b]))
        record = self.kernel.global_record()
        self.assertEqual(3, record["native_candidates"])
        self.assertEqual(2, record["short_overlap_candidates"])
        self.assertEqual(0, record["fallback_candidates"])
        self.assertEqual(5, sum(r["candidate_count"]*r["search_count"] for r in record["searches"]))
        self.assertEqual(3, sum(r["candidate_count"] for r in record["geometries"]))

    def test_ties_near_ties_and_threshold_neighbors(self):
        self.compare([1.0]*100, [1.0]*100)
        a = [1.0, -1.0, 0.0, 0.0]*25
        for value in (math.nextafter(.2, 0.0), .2, math.nextafter(.2, 1.0)):
            b = [value, -value, math.sqrt(1-value*value), -math.sqrt(1-value*value)]*25
            self.compare(a, b)
        b = a.copy()
        b[60] = math.nextafter(b[60], 0.0)
        self.compare(a, b)

    def test_unchanged_local_search_entrypoint_and_numerics(self):
        self.assertIs(N.Kernel.results, N.local.Kernel.results)
        a = [float(i%13-6) for i in range(100)]
        expected = {lag: V4.correlate(a[20:80], a[20+lag:80+lag], 0).record() for lag in range(-3, 4)}
        actual = {lag: c.record() for lag, c in self.kernel.results(a, a, 0, 50, 30, 3).items()}
        self.assertEqual(canonical(expected), canonical(actual))

    def test_complete_small_alignment_matches_except_version(self):
        a, _ = fixtures.fixture("identity_baseline", frames=2400)
        variants = [a, tuple(tuple(-v for v in c) for c in a), (a[0], (0.0,)*2400),
                    tuple((0.0,)*3+c[:-3] for c in a), tuple(c[:1000]+c[1001:]+(0.0,) for c in a)]
        for b in variants:
            args = dict(reference_channels=a, test_channels=b, reference_channel_map=["L", "R"],
                        test_channel_map=["L", "R"], sample_rate_hz=200, recipe_identity="v5-small")
            with patch.object(V4, "NATIVE_BACKEND", self.kernel):
                expected = V4.align_channels(**args)
            with patch.object(V5, "NATIVE_BACKEND", self.kernel):
                actual = V5.align_channels(**args)
            expected.pop("record_kind")
            self.assertEqual(V5.RECORD_KIND, actual.pop("record_kind"))
            self.assertEqual(canonical(expected), canonical(actual))

    def test_no_backend_and_invalid_controls_preserve_records(self):
        for kind in ("identity_baseline", "constant_envelope", "topology_mismatch"):
            a, b = fixtures.fixture(kind, frames=120)
            args = dict(reference_channels=a, test_channels=b, reference_channel_map=["L", "R"],
                        test_channel_map=["M"] if len(b) == 1 else ["L", "R"],
                        sample_rate_hz=20, recipe_identity=kind)
            expected = V4.align_channels(**args)
            actual = V5.align_channels(**args)
            expected.pop("record_kind"), actual.pop("record_kind")
            self.assertEqual(canonical(expected), canonical(actual))

    def test_inherited_summation_rounding_and_binary_binding(self):
        fn = self.kernel.library.lt_test_sum
        fn.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.c_size_t, ctypes.POINTER(ctypes.c_double)]
        fn.restype = ctypes.c_int
        for values in ([1.0, 2**-53, 2**-1074], [-1.0, -2**-53, -2**-1074], [1.0, 2**-53, -1.0]):
            result = ctypes.c_double()
            self.assertEqual(0, fn((ctypes.c_double*len(values))(*values), len(values), ctypes.byref(result)))
            self.assertEqual(math.fsum(values).hex(), result.value.hex())
        with self.assertRaises(ValueError):
            N.Kernel(self.binary, "0"*64)
        with self.assertRaises(FileExistsError):
            N.build(self.directory.name)

    def test_alignment_ast_only_global_dispatch_changes(self):
        def definitions(module):
            return {n.name: n for n in ast.parse(Path(module.__file__).read_text()).body
                    if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
        old, new = definitions(V4), definitions(V5)
        a, b = old.pop("_channel"), new.pop("_channel")
        self.assertEqual({k: ast.dump(v) for k, v in old.items()}, {k: ast.dump(v) for k, v in new.items()})
        def sampled_index(fn):
            return next(i for i, n in enumerate(fn.body) if isinstance(n, ast.Assign)
                        and any(isinstance(t, ast.Name) and t.id == "sampled" for t in n.targets))
        a.body.pop(sampled_index(a)), b.body.pop(sampled_index(b))
        self.assertEqual(ast.dump(a), ast.dump(b))
        self.assertIsNone(V4.NATIVE_BACKEND)
        self.assertIsNone(V5.NATIVE_BACKEND)


if __name__ == "__main__":
    unittest.main()
