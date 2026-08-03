from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "validate-perceptual-degradation-execution-gate.py"
GATE_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "metric-execution-gate.json"
)
SPEC = importlib.util.spec_from_file_location("perceptual_degradation_gate", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
GATE = json.loads(GATE_PATH.read_text(encoding="utf-8"))


class PerceptualDegradationExecutionGateTest(unittest.TestCase):
    def test_gate_is_valid_and_metric_execution_is_blocked(self) -> None:
        self.assertEqual([], MODULE.validate(GATE))
        self.assertFalse(GATE["perceptual_metric_execution_authorized"])
        self.assertFalse(GATE["retained_audio_metric_execution_authorized"])
        self.assertFalse(GATE["public_development_audio_metric_execution_authorized"])

    def test_gate_rejects_premature_metric_authorization(self) -> None:
        changed = copy.deepcopy(GATE)
        changed["perceptual_metric_execution_authorized"] = True
        changed["metric_families"]["visqol_audio_v3_3_3"]["execution_authorized"] = True
        errors = MODULE.validate(changed)
        self.assertIn("perceptual_metric_execution_authorized must remain false", errors)
        self.assertIn(
            "visqol_audio_v3_3_3.execution_authorized must remain false", errors
        )

    def test_gate_rejects_claimed_proxy_clearance(self) -> None:
        changed = copy.deepcopy(GATE)
        changed["metric_families"]["gstpeaq_proxy_v0_6_1"][
            "itu_technology_consent_or_licence_cleared"
        ] = True
        self.assertIn(
            "gstpeaq_proxy_v0_6_1.itu_technology_consent_or_licence_cleared must remain false",
            MODULE.validate(changed),
        )


if __name__ == "__main__":
    unittest.main()
