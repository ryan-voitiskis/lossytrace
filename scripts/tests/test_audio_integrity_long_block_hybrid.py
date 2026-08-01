import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "analyze-audio-integrity-long-block-hybrid.py"
)
SPEC = importlib.util.spec_from_file_location("long_block_hybrid", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def row(case_id, positive, feature, long_score):
    return {
        "case_id": case_id,
        "class": "positive" if positive else "negative",
        "expectation": (
            "controlled_positive" if positive else "negative"
        ),
        "source_group": case_id,
        "positive": positive,
        "features": {"feature": feature},
        "long": long_score,
        "cnn": 0.0,
    }


class LongBlockHybridTests(unittest.TestCase):
    def test_fit_template_uses_strict_negative_boundary(self):
        rows = [
            row("negative-low", False, 0.0, 0.2),
            row("negative-high", False, 1.0, 0.8),
            row("positive", True, 1.0, 0.9),
        ]
        rule = MODULE.fit_template(
            ("long", "feature", "greater_than"), rows
        )
        selected = MODULE.selected_ids(rule, rows)

        self.assertEqual(selected, {"positive"})
        self.assertNotIn("negative-high", selected)

    def test_greedy_rules_counts_only_new_positive_cases(self):
        first = ("long", "a", "greater_than")
        second = ("cnn", "b", "less_than")
        fitted = {
            first: {
                "score": "long",
                "guard_feature": "a",
                "guard_direction": "greater_than",
                "guard_threshold": 0.0,
                "score_boundary": 1.0,
            },
            second: {
                "score": "cnn",
                "guard_feature": "b",
                "guard_direction": "less_than",
                "guard_threshold": 1.0,
                "score_boundary": 0.5,
            },
        }
        rules, selected = MODULE.greedy_rules(
            fitted,
            {
                first: {"one", "two"},
                second: {"two", "three"},
            },
            2,
        )

        self.assertEqual(selected, {"one", "two", "three"})
        self.assertEqual(
            [rule["newly_detected_positive_count"] for rule in rules],
            [2, 1],
        )


if __name__ == "__main__":
    unittest.main()
