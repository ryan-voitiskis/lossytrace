import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.audio_integrity_relocation import cleanup_target_matches


class RelocationTests(unittest.TestCase):
    def make_record(self, root: Path, old_root: Path) -> None:
        inventory = root / "inventory.json"
        inventory.write_text('{"schema_version":1}\n', encoding="utf-8")
        inventory_sha256 = hashlib.sha256(inventory.read_bytes()).hexdigest()
        (root / "relocation-001.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "operation": "same-filesystem-directory-rename",
                    "source": str(old_root),
                    "destination": str(root),
                    "verification": {
                        "device_and_inode_before": "1:2",
                        "device_and_inode_after": "1:2",
                        "retained_inventory": {
                            "file": inventory.name,
                            "sha256_before_and_after": inventory_sha256,
                        },
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_accepts_exact_and_verified_relocated_targets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            child = root / "corpus" / "run"
            child.mkdir(parents=True)
            old_root = root.parent / "old-audio-integrity-v1"
            self.make_record(root, old_root)
            self.assertTrue(cleanup_target_matches(child, str(child)))
            self.assertTrue(
                cleanup_target_matches(child, str(old_root / "corpus" / "run"))
            )

    def test_rejects_unverified_or_different_relocations(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            child = root / "corpus" / "run"
            child.mkdir(parents=True)
            old_root = root.parent / "old-audio-integrity-v1"
            self.assertFalse(
                cleanup_target_matches(child, str(old_root / "corpus" / "run"))
            )
            self.make_record(root, old_root)
            (root / "inventory.json").write_text("changed\n", encoding="utf-8")
            self.assertFalse(
                cleanup_target_matches(child, str(old_root / "corpus" / "run"))
            )


if __name__ == "__main__":
    unittest.main()
