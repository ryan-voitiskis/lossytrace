from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "audio_integrity_verified_mp3_v29_policy.py"
SPEC = importlib.util.spec_from_file_location(
    "audio_integrity_verified_mp3_v29_policy",
    MODULE_PATH,
)
assert SPEC is not None and SPEC.loader is not None
POLICY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(POLICY)


def runner() -> dict:
    return {
        "feature_version": 0,
        "research_transform_grid_profile": POLICY.PROFILE,
        "source_facts": {"sample_rate_hz": 44_100},
        "compression_trace": {
            "active_frame_count": 100,
            "high_band_supported_frame_count": 100,
            "median_active_bin_fraction": 0.5,
            "spectral_edge_drop_db": 8.0,
            "spectral_edge_persistence": 0.1,
        },
        "transform_grid_probe": {
            "mp3_long_sine": {
                "block_samples": 576,
                "long_block_phase_peak_z_median": 3.0,
                "multi_candidate_phase_verification": {
                    "audio_block_count": 3,
                    "frames_per_phase": 16,
                    "control_phase_stride_samples": 24,
                    "candidate_radius_samples": 2,
                    "discovery_aggregate_phase_samples": 287,
                    "verified_phase_samples": 287,
                    "peak_z_median": 3.1,
                },
            },
            "long_vorbis": {
                "long_block_phase_aggregate_peak_z": 1.0,
                "long_block_phase_peak_z_median": 3.0,
            },
            "opus_long_celt": None,
            "opus_short_celt": None,
        },
    }


def low_bandwidth() -> dict:
    return {
        "supported": True,
        "declared_sample_rate_hz": 44_100,
        "power_share_10_20khz": 0.1,
        "low_edge_drop_db": 8.0,
        "low_edge_persistence": 0.1,
    }


class VerifiedMp3V29PolicyTests(unittest.TestCase):
    def test_contract_remains_development_only(self) -> None:
        contract = POLICY.contract()
        self.assertFalse(contract["candidate_frozen"])
        self.assertFalse(contract["public_verdict_enabled"])
        self.assertEqual(contract["feature_version"], 0)
        self.assertEqual(
            contract["verification_contract"][
                "minimum_audio_block_count"
            ],
            3,
        )
        self.assertEqual(
            contract["verification_contract"][
                "maximum_audio_block_count"
            ],
            4,
        )

    def test_verified_mp3_branch_requires_score_and_phase_reidentification(
        self,
    ) -> None:
        result = POLICY.assess(runner(), low_bandwidth())
        self.assertTrue(result["predicted_positive"])
        self.assertEqual(result["branches"], ["mp3_verified"])

        at_threshold = runner()
        at_threshold["transform_grid_probe"]["mp3_long_sine"][
            "multi_candidate_phase_verification"
        ]["peak_z_median"] = 3.0
        self.assertFalse(
            POLICY.assess(at_threshold, low_bandwidth())[
                "predicted_positive"
            ]
        )

        wrong_phase = runner()
        wrong_phase["transform_grid_probe"]["mp3_long_sine"][
            "multi_candidate_phase_verification"
        ]["verified_phase_samples"] = 290
        self.assertFalse(
            POLICY.assess(wrong_phase, low_bandwidth())[
                "predicted_positive"
            ]
        )

    def test_circular_phase_distance_wraps_at_the_mp3_period(self) -> None:
        wrapped = runner()
        verification = wrapped["transform_grid_probe"][
            "mp3_long_sine"
        ]["multi_candidate_phase_verification"]
        verification["discovery_aggregate_phase_samples"] = 575
        verification["verified_phase_samples"] = 1
        self.assertTrue(
            POLICY.assess(wrapped, low_bandwidth())["predicted_positive"]
        )

    def test_support_failure_stays_inconclusive_without_reading_verification(
        self,
    ) -> None:
        unsupported = copy.deepcopy(low_bandwidth())
        unsupported["power_share_10_20khz"] = 0.0
        missing_verification = runner()
        missing_verification["transform_grid_probe"]["mp3_long_sine"][
            "multi_candidate_phase_verification"
        ] = None
        result = POLICY.assess(missing_verification, unsupported)
        self.assertFalse(result["signal_supported"])
        self.assertEqual(result["assessment"], "inconclusive")

    def test_missing_verification_disables_only_the_mp3_branch(self) -> None:
        missing_verification = runner()
        missing_verification["transform_grid_probe"]["mp3_long_sine"][
            "multi_candidate_phase_verification"
        ] = None
        result = POLICY.assess(missing_verification, low_bandwidth())
        self.assertTrue(result["signal_supported"])
        self.assertFalse(result["predicted_positive"])
        self.assertEqual(result["branches"], [])

    def test_verification_shape_is_part_of_the_policy_contract(self) -> None:
        wrong_shape = runner()
        wrong_shape["transform_grid_probe"]["mp3_long_sine"][
            "multi_candidate_phase_verification"
        ]["frames_per_phase"] = 15
        with self.assertRaisesRegex(
            ValueError,
            "verification contract differs",
        ):
            POLICY.assess(wrong_shape, low_bandwidth())


if __name__ == "__main__":
    unittest.main()
