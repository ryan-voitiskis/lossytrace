from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-rwc-metadata.py"
SPEC = importlib.util.spec_from_file_location("rwc_metadata_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class RwcMetadataAuditTest(unittest.TestCase):
    def make_inputs(self, root: Path) -> tuple[Path, Path]:
        metadata_path = root / "metadata.csv"
        rules_path = root / "rules.json"
        rows = [
            ["RWC_J001", "J", "1", "Repeated Work", "Excluded Player"],
            ["RWC_G002", "G", "2", "Song X", "Jane Doe"],
            ["RWC_P003", "P", "3", "Song Y", "Jane Doe Trio"],
            ["RWC_R004", "R", "4", "Silent Night", "Other Sound"],
            ["RWC_J036", "J", "36", "Silent Night", "Third Voice"],
        ]
        with metadata_path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.writer(target, delimiter=";")
            writer.writerow(["RWCID", "CollID", "PieceNo", "Title", "Artist"])
            writer.writerows(rows)
        digest = hashlib.sha256(metadata_path.read_bytes()).hexdigest()
        rules = {
            "schema_version": 1,
            "state": "source_identity_rules_not_allocation",
            "source_id": "rwc_music_v2_2026",
            "metadata_revision": "revision-1",
            "metadata_sha256": digest,
            "audio_generated": False,
            "scores_opened": False,
            "selection_authorized": False,
            "eligibility_exclusions": [
                {
                    "rule_id": "exclude_repeat",
                    "collection_id": "J",
                    "piece_number_minimum": 1,
                    "piece_number_maximum": 35,
                }
            ],
            "family_merges": [
                {
                    "family_id": "jane_doe",
                    "artist_labels": ["Jane Doe", "Jane Doe Trio"],
                }
            ],
            "reviewed_label_overlap_pairs": [
                {
                    "artist_labels": ["Jane Doe", "Jane Doe Trio"],
                    "decision": "merge",
                }
            ],
            "expected": {
                "metadata_row_count": 5,
                "global_exact_artist_label_count": 5,
                "excluded_row_count": 1,
                "eligible_row_count": 4,
                "eligible_exact_artist_label_count": 4,
                "artist_family_count": 3,
                "reviewed_overlap_pair_count": 1,
            },
        }
        rules_path.write_text(json.dumps(rules), encoding="utf-8")
        return metadata_path, rules_path

    def test_audit_excludes_repeated_work_and_merges_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metadata_path, rules_path = self.make_inputs(Path(directory))
            report = MODULE.audit(metadata_path, rules_path, "revision-1")
            self.assertEqual(3, report["observed"]["artist_family_count"])
            self.assertEqual(1, report["observed"]["excluded_row_count"])
            self.assertEqual(
                1, report["observed"]["duplicate_normalized_work_title_group_count"]
            )
            self.assertFalse(report["audio_acquired"])
            self.assertFalse(report["selection_authorized"])
            self.assertTrue(report["paths_redacted"])

    def test_overlap_decision_must_match_family_merge(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            metadata_path, rules_path = self.make_inputs(Path(directory))
            rules = json.loads(rules_path.read_text(encoding="utf-8"))
            rules["reviewed_label_overlap_pairs"][0]["decision"] = "separate"
            rules_path.write_text(json.dumps(rules), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "decision differs"):
                MODULE.audit(metadata_path, rules_path, "revision-1")


if __name__ == "__main__":
    unittest.main()
