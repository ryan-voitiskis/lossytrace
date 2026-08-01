import hashlib
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "verify-audio-integrity-retained-inventory.py"
)
SPEC = importlib.util.spec_from_file_location("retained_inventory", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RetainedInventoryTests(unittest.TestCase):
    def test_relocates_only_paths_beneath_the_recorded_source(self):
        relocation = {"source": "/old/root", "destination": "/new/root"}
        self.assertEqual(
            MODULE.relocate("/old/root/corpus/file", relocation),
            Path("/new/root/corpus/file"),
        )
        with self.assertRaisesRegex(ValueError, "outside"):
            MODULE.relocate("/different/root/file", relocation)

    def test_file_verification_records_hash_and_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "fixture.bin"
            path.write_bytes(b"fixture")
            expected = hashlib.sha256(b"fixture").hexdigest()
            verification = MODULE.Verification()
            verification.file("fixture", path, expected, 7)
            self.assertEqual(verification.checks[0]["sha256"], expected)
            with self.assertRaisesRegex(ValueError, "byte count differs"):
                verification.file("bad", path, expected, 8)


if __name__ == "__main__":
    unittest.main()
