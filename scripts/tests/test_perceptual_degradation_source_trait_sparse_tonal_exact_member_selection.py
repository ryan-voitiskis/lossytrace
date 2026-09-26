from __future__ import annotations

import csv
import importlib.util
import io
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/perceptual_degradation_source_trait_sparse_tonal_exact_member_selection.py"
SPEC = importlib.util.spec_from_file_location("selection", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SparseTonalSelectionTest(unittest.TestCase):
    def test_plan_and_committed_report_validate(self) -> None:
        plan = MODULE.load_json(MODULE.PLAN_PATH)
        self.assertEqual([], MODULE.validate_plan(plan))
        report = MODULE.load_json(MODULE.REPORT_PATH)
        expected = MODULE.build_report(plan)
        self.assertEqual(report["decision"], expected["decision"])
        self.assertTrue(report["access_boundary"]["private_tinysol_metadata_selection_replayed"])

    def test_selection_rule_is_order_independent(self) -> None:
        plan = MODULE.load_json(MODULE.PLAN_PATH)
        fields = ["Path", "Instrument (abbr.)", "Technique (abbr.)", "Dynamics", "Instance ID", "Needed digital retuning", "Pitch ID"]
        rows = []
        for pitch in range(60, 73):
            if pitch in (61, 67):
                continue
            path = plan["tinysol_selection"]["selected_metadata_path"] if pitch == 63 else f"Winds/Oboe/ordinario/test-{pitch}.wav"
            rows.append(dict(zip(fields, [path, "Ob", "ord", "mf", "0", "FALSE", str(pitch)])))
        with self.assertRaises(ValueError):
            MODULE.select_tinysol(reversed(rows), plan)

    def test_audio_and_assignment_remain_closed(self) -> None:
        report = MODULE.load_json(MODULE.REPORT_PATH)
        self.assertFalse(report["decision"]["audio_accessed"])
        self.assertFalse(report["decision"]["descriptor_confirmation_complete"])
        self.assertFalse(report["decision"]["source_trait_assignment_complete"])
        self.assertFalse(report["decision"]["source_trait_manifest_frozen"])


if __name__ == "__main__":
    unittest.main()
