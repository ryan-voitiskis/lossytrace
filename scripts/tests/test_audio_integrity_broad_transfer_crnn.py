import importlib.util
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "train-audio-integrity-broad-transfer-crnn.py"
)
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_broad_transfer_crnn",
    SCRIPT,
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def case(case_id, label, domain, group):
    prefix = (
        "dev-"
        if domain == "tier_b_private_full_mix"
        else "tier-b-nsynth-train-instrument-"
    )
    source_group = f"{prefix}{group}"
    return {
        "case_id": case_id,
        "expectation": (
            "negative" if label == 0 else "controlled_positive"
        ),
        "_label": label,
        "_training_domain": domain,
        "partition_group": source_group,
        "source_group": source_group,
        "relative_path": f"generated/{case_id}.flac",
    }


class BroadTransferCrnnTests(unittest.TestCase):
    def test_training_domain_is_explicit_and_fail_closed(self):
        self.assertEqual(
            MODULE.training_domain("dev-001"),
            "tier_b_private_full_mix",
        )
        self.assertEqual(
            MODULE.training_domain(
                "tier-b-nsynth-train-instrument-0001"
            ),
            "tier_b_nsynth_train",
        )
        with self.assertRaisesRegex(SystemExit, "no unambiguous domain"):
            MODULE.training_domain("tier-b-nsynth-instrument-0001")

    def test_validation_groups_are_domain_stratified_and_stable(self):
        cases = []
        for domain in MODULE.TRAINING_DOMAINS.values():
            for index in range(5):
                cases.append(
                    case(
                        f"{domain}-{index}-negative",
                        0,
                        domain,
                        str(index),
                    )
                )
                cases.append(
                    case(
                        f"{domain}-{index}-positive",
                        1,
                        domain,
                        str(index),
                    )
                )
        first = MODULE.validation_groups(cases, 123)
        second = MODULE.validation_groups(cases, 123)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        observed_domains = {
            next(
                item["_training_domain"]
                for item in cases
                if item["partition_group"] == group
            )
            for group in first
        }
        self.assertEqual(
            observed_domains,
            set(MODULE.TRAINING_DOMAINS.values()),
        )

    def test_training_count_validation_includes_pair_count(self):
        cases = []
        for domain in MODULE.TRAINING_DOMAINS.values():
            cases.append(case(f"{domain}-negative", 0, domain, "1"))
            cases.append(case(f"{domain}-positive", 1, domain, "1"))
        result = MODULE.validate_training_counts(
            cases,
            expected_groups=2,
            expected_cases=4,
            expected_negatives=2,
            expected_positives=2,
            expected_pairs=2,
            seed=123,
        )
        self.assertEqual(result["source_pair_count_per_complete_epoch"], 2)
        self.assertEqual(
            set(result["domains"]),
            set(MODULE.TRAINING_DOMAINS.values()),
        )

    def test_training_scoring_supplies_base_domain_without_mutating_cases(self):
        cases = [
            case(
                "private-negative",
                0,
                "tier_b_private_full_mix",
                "1",
            )
        ]
        original = MODULE.BASE.score_cases

        def fake_score_cases(model, scoring_cases, **kwargs):
            self.assertNotIn("_domain", cases[0])
            self.assertEqual(
                scoring_cases[0]["_domain"],
                "tier_b_private_full_mix",
            )
            return [
                {
                    "case_id": scoring_cases[0]["case_id"],
                    "domain": scoring_cases[0]["_domain"],
                }
            ]

        MODULE.BASE.score_cases = fake_score_cases
        try:
            results = MODULE.score_training_cases(None, cases)
        finally:
            MODULE.BASE.score_cases = original
        self.assertNotIn("_domain", cases[0])
        self.assertEqual(
            results[0]["_training_domain"],
            "tier_b_private_full_mix",
        )


if __name__ == "__main__":
    unittest.main()
