import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "verify-audio-integrity-exact-hybrid-replay.py"
)
SPEC = importlib.util.spec_from_file_location("exact_hybrid_replay", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class ExactHybridReplayTest(unittest.TestCase):
    def test_maximum_difference(self):
        self.assertEqual(
            MODULE.maximum_absolute_difference([1.0, 2.0], [1.25, 1.5], "x"),
            0.5,
        )

    def test_maximum_difference_rejects_shape_change(self):
        with self.assertRaisesRegex(ValueError, "differ in length"):
            MODULE.maximum_absolute_difference([1.0], [], "x")


if __name__ == "__main__":
    unittest.main()
