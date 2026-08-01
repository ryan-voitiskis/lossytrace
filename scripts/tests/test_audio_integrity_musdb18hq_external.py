import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


POLICY = load_script(
    "audio_integrity_conservative_v28_policy",
    ROOT / "scripts/audio_integrity_conservative_v28_policy.py",
)
STAGER = load_script(
    "stage_audio_integrity_musdb18hq_external",
    ROOT / "scripts/stage-audio-integrity-musdb18hq-external.py",
)
EVALUATOR = load_script(
    "evaluate_audio_integrity_musdb18hq_external",
    ROOT / "scripts/evaluate-audio-integrity-musdb18hq-external.py",
)


def write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def runner(
    *,
    mp3_aggregate: float = 1.4,
    vorbis_aggregate: float = 2.0,
    mp3_median: float = 1.0,
    vorbis_median: float = 1.0,
    edge_drop: float = 4.0,
    edge_persistence: float = 0.01,
) -> dict:
    return {
        "feature_version": 0,
        "source_facts": {"sample_rate_hz": 44_100},
        "compression_trace": {
            "active_frame_count": 100,
            "high_band_supported_frame_count": 80,
            "median_active_bin_fraction": 0.2,
            "spectral_edge_drop_db": edge_drop,
            "spectral_edge_persistence": edge_persistence,
        },
        "research_transform_grid_profile": POLICY.PROFILE,
        "transform_grid_probe": {
            "mp3_long_sine": {
                "long_block_phase_aggregate_peak_z": mp3_aggregate,
                "long_block_phase_peak_z_median": mp3_median,
            },
            "long_vorbis": {
                "long_block_phase_aggregate_peak_z": vorbis_aggregate,
                "long_block_phase_peak_z_median": vorbis_median,
            },
            "opus_long_celt": None,
            "opus_short_celt": None,
        },
    }


def low_bandwidth(*, upper_share: float = 0.1) -> dict:
    return {
        "supported": True,
        "declared_sample_rate_hz": 44_100,
        "power_share_10_20khz": upper_share,
        "low_edge_drop_db": 5.0,
        "low_edge_persistence": 0.01,
    }


class ConservativePolicyTests(unittest.TestCase):
    def test_thresholds_are_strict_at_the_frozen_boundaries(self):
        result = POLICY.assess(runner(), low_bandwidth())

        self.assertTrue(result["signal_supported"])
        self.assertFalse(result["predicted_positive"])
        self.assertEqual(result["assessment"], "no_lossy_signature_detected")

    def test_each_transform_branch_can_supply_the_second_reason_family(self):
        variants = [
            runner(mp3_aggregate=1.400001),
            runner(vorbis_aggregate=2.000001),
            runner(mp3_median=0.249999, vorbis_median=1.0),
        ]

        for value in variants:
            with self.subTest(value=value):
                result = POLICY.assess(value, low_bandwidth())
                self.assertTrue(result["predicted_positive"])
                self.assertEqual(
                    set(result["reason_families"]),
                    {
                        "persistent_spectral_edge",
                        "transform_frame_periodicity",
                    },
                )

    def test_low_bandwidth_support_failure_prevents_a_positive(self):
        result = POLICY.assess(
            runner(mp3_aggregate=20.0),
            low_bandwidth(upper_share=0.0),
        )

        self.assertFalse(result["signal_supported"])
        self.assertFalse(result["predicted_positive"])
        self.assertEqual(result["assessment"], "inconclusive")

    def test_edge_guard_is_required(self):
        result = POLICY.assess(
            runner(mp3_aggregate=20.0, edge_drop=3.0),
            low_bandwidth(),
        )

        self.assertFalse(result["predicted_positive"])

    def test_inclusive_support_and_persistence_boundaries_are_stable(self):
        value = runner(
            mp3_aggregate=1.400001,
            edge_persistence=POLICY.EDGE_PERSISTENCE_THRESHOLD,
        )
        value["compression_trace"]["active_frame_count"] = 400
        value["compression_trace"][
            "high_band_supported_frame_count"
        ] = POLICY.MINIMUM_HIGH_BAND_FRAMES
        value["compression_trace"][
            "median_active_bin_fraction"
        ] = POLICY.MINIMUM_ACTIVE_BIN_FRACTION
        low = low_bandwidth(
            upper_share=POLICY.LOW_UPPER_BAND_POWER_SHARE
        )

        result = POLICY.assess(value, low)

        self.assertTrue(result["signal_supported"])
        self.assertTrue(result["predicted_positive"])

        value["compression_trace"][
            "median_active_bin_fraction"
        ] = POLICY.MINIMUM_ACTIVE_BIN_FRACTION - 0.000001
        unsupported = POLICY.assess(value, low)
        self.assertFalse(unsupported["signal_supported"])
        self.assertEqual(unsupported["assessment"], "inconclusive")


class MusdbPlanTests(unittest.TestCase):
    def test_plan_has_two_aac_encoders_and_locked_invariants(self):
        acquisition = {
            "source_output_inventory_sha256": "inventory",
            "completed": [
                {
                    "source_id": f"musdb18hq-{index:03d}",
                    "relative_path": (
                        f"sources/musdb18hq-{index:03d}.wav"
                    ),
                    "output_sha256": f"{index:064x}",
                }
                for index in range(1, 151)
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            acquisition_path = Path(directory) / "acquisition.json"
            acquisition_path.write_text(
                json.dumps(acquisition),
                encoding="utf-8",
            )
            plan = STAGER.build_plan(acquisition_path, acquisition)

        self.assertEqual(plan["corpus"]["source_count"], 150)
        self.assertEqual(plan["corpus"]["case_count"], 1_770)
        self.assertEqual(plan["corpus"]["group_count"], 1_650)
        self.assertEqual(plan["corpus"]["negative_count"], 600)
        self.assertEqual(
            plan["corpus"]["controlled_positive_count"],
            1_170,
        )
        self.assertEqual(plan["corpus"]["invariant_source_count"], 30)
        self.assertEqual(
            plan["corpus"]["class_counts"][
                "musdb_aac_lc_128_to_flac16"
            ],
            150,
        )
        self.assertEqual(
            plan["corpus"]["class_counts"][
                "musdb_aac_at_128_to_flac16"
            ],
            150,
        )
        self.assertEqual(
            plan["corpus"]["class_counts"][
                "musdb_aac_lc_128_to_aiff24"
            ],
            30,
        )
        self.assertTrue(
            all(
                case["split"] == "held_out"
                and case["provenance_tier"]
                == "tier_a_confirmed_pcm"
                for case in plan["manifest"]["cases"]
            )
        )
        resample_filters = {
            group["pre_filter"]
            for group in plan["transformation_groups"]
            if group["group_id"].endswith(
                "-pcm-resample-32000-44100"
            )
        }
        self.assertEqual(
            resample_filters,
            {
                "aresample=32000:resampler=swr,"
                "aresample=44100:resampler=swr"
            },
        )

    def test_pending_journal_recovers_without_overwriting(self):
        group = {
            "group_id": "musdb18hq-001-aac-at-128",
            "source_id": "musdb18hq-001",
            "source_relative_path": "sources/musdb18hq-001.wav",
            "operation": "lossy_round_trip",
            "intermediate_extension": ".m4a",
            "encoder": "aac_at",
            "encoder_arguments": ["-b:a", "128k"],
            "outputs": [
                {
                    "case": {
                        "case_id": (
                            "musdb18hq-001-aac-at-128-to-flac16"
                        ),
                        "relative_path": (
                            "audio/"
                            "musdb18hq-001-aac-at-128-to-flac16.flac"
                        ),
                    },
                    "output_kind": "flac16",
                    "post_filter": None,
                }
            ],
        }
        payload = b"journaled-lossless-output"
        digest = hashlib.sha256(payload).hexdigest()
        record = {
            "group_id": group["group_id"],
            "source_id": group["source_id"],
            "plan_group_sha256": STAGER.canonical_sha256(group),
            "intermediate": None,
            "outputs": [
                {
                    "case_id": group["outputs"][0]["case"]["case_id"],
                    "relative_path": group["outputs"][0]["case"][
                        "relative_path"
                    ],
                    "sha256": digest,
                    "bytes": len(payload),
                }
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            partial_root = root / ".partial"
            partial_root.mkdir()
            (root / "audio").mkdir()
            state_path = root / "staging-state.json"
            state = {"completed": [], "completed_group_count": 0}
            state_path.write_text(json.dumps(state), encoding="utf-8")
            partial = (
                partial_root
                / "musdb18hq-001-aac-at-128-to-flac16.partial.flac"
            )
            partial.write_bytes(payload)
            journal = (
                partial_root
                / "musdb18hq-001-aac-at-128.journal.json"
            )
            journal.write_text(
                json.dumps({"record": record}),
                encoding="utf-8",
            )

            STAGER.recover_journal(
                root=root,
                state_path=state_path,
                state=state,
                group=group,
                journal_path=journal,
                partial_root=partial_root,
            )

            final = root / record["outputs"][0]["relative_path"]
            self.assertEqual(final.read_bytes(), payload)
            self.assertFalse(partial.exists())
            self.assertFalse(journal.exists())
            recovered = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(recovered["completed_group_count"], 1)
            self.assertEqual(
                recovered["completed"][0]["group_id"],
                group["group_id"],
            )

    def test_committed_journal_cleanup_is_safe_and_idempotent(self):
        group = {
            "group_id": "musdb18hq-001-pcm-reference",
            "source_id": "musdb18hq-001",
            "source_relative_path": "sources/musdb18hq-001.wav",
            "operation": "lossless_hardlink",
            "outputs": [
                {
                    "case": {
                        "case_id": (
                            "musdb18hq-001-pcm-reference-wav16"
                        ),
                        "relative_path": (
                            "audio/"
                            "musdb18hq-001-pcm-reference-wav16.wav"
                        ),
                    },
                    "output_kind": "wav16",
                    "post_filter": None,
                }
            ],
        }
        payload = b"committed-lossless-output"
        record = {
            "group_id": group["group_id"],
            "source_id": group["source_id"],
            "source_relative_path": group["source_relative_path"],
            "plan_group_sha256": STAGER.canonical_sha256(group),
            "intermediate": None,
            "outputs": [
                {
                    "case_id": group["outputs"][0]["case"]["case_id"],
                    "relative_path": group["outputs"][0]["case"][
                        "relative_path"
                    ],
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
            ],
        }
        journal_value = {"record": record}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            partial_root = root / ".partial"
            partial_root.mkdir()
            (root / "audio").mkdir()
            final = root / record["outputs"][0]["relative_path"]
            final.write_bytes(payload)
            state_path = root / "staging-state.json"
            state = {
                "completed": [record],
                "completed_group_count": 1,
                "recovery_cleanups": [],
            }
            state_path.write_text(json.dumps(state), encoding="utf-8")
            journal = (
                partial_root
                / "musdb18hq-001-pcm-reference.journal.json"
            )
            journal_text = json.dumps(journal_value)
            journal.write_text(journal_text, encoding="utf-8")

            STAGER.remove_committed_journal(
                root=root,
                partial_root=partial_root,
                state_path=state_path,
                state=state,
                group=group,
                record=record,
            )

            self.assertFalse(journal.exists())
            self.assertEqual(final.read_bytes(), payload)
            recovered = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(len(recovered["recovery_cleanups"]), 1)
            self.assertEqual(
                recovered["recovery_cleanups"][0]["reason"],
                "committed_journal_after_state_checkpoint",
            )

            journal.write_text(journal_text, encoding="utf-8")
            STAGER.remove_committed_journal(
                root=root,
                partial_root=partial_root,
                state_path=state_path,
                state=recovered,
                group=group,
                record=record,
            )
            self.assertFalse(journal.exists())
            self.assertEqual(len(recovered["recovery_cleanups"]), 1)


class ExternalEvaluatorTests(unittest.TestCase):
    def test_complete_fixture_passes_and_one_false_positive_rejects(self):
        negative_classes = sorted(EVALUATOR.NEGATIVE_CLASSES)
        positive_classes = sorted(
            EVALUATOR.SCOPED_CLASSES | EVALUATOR.DIFFICULT_CLASSES
        )
        invariant_variants = sorted(
            EVALUATOR.AAC_INVARIANT_CLASSES
            - {"musdb_aac_lc_128_to_flac16"}
        )
        cases = []
        for index in range(1, 151):
            source_group = f"musdb18hq-{index:03d}"
            classes = negative_classes + positive_classes
            if index <= 30:
                classes += invariant_variants
            for class_name in classes:
                expectation = (
                    "negative"
                    if class_name in EVALUATOR.NEGATIVE_CLASSES
                    else "controlled_positive"
                )
                cases.append(
                    {
                        "case_id": f"{source_group}-{class_name}",
                        "source_group": source_group,
                        "partition_group": source_group,
                        "split": "held_out",
                        "provenance_tier": "tier_a_confirmed_pcm",
                        "class": class_name,
                        "expectation": expectation,
                        "relative_path": (
                            f"audio/{source_group}-{class_name}.flac"
                        ),
                    }
                )
        self.assertEqual(len(cases), EVALUATOR.EXPECTED_CASE_COUNT)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            manifest_path = root / "manifest.json"
            fingerprints_path = root / "fingerprints.json"
            plan_path = root / "plan.json"
            performance_path = root / "performance.json"
            precommit_path = root / "precommit.json"
            measurement_path = root / "measurement.json"
            support_path = root / "support.json"
            output_path = root / "evaluation.json"

            manifest = {
                "schema_version": 1,
                "corpus_id": "fixture",
                "cases": cases,
            }
            fingerprints = {
                "schema_version": 1,
                "corpus_id": "fixture",
                "case_sha256": {
                    case["case_id"]: hashlib.sha256(
                        case["case_id"].encode()
                    ).hexdigest()
                    for case in cases
                },
            }
            plan = {"manifest": manifest}
            performance = {
                "method": {"transform_grid_profile": EVALUATOR.PROFILE},
                "summary": {
                    "p95_wall_time_overhead_percent": 3.0,
                    "p95_peak_rss_increase_percent": 6.0,
                },
                "commitments": {"runner_sha256": "benchmark-runner"},
            }
            write_json(manifest_path, manifest)
            write_json(fingerprints_path, fingerprints)
            write_json(plan_path, plan)
            write_json(performance_path, performance)

            precommit = {
                "schema_version": 1,
                "state": "frozen_before_external_transfer",
                "candidate_id": EVALUATOR.CANDIDATE_ID,
                "candidate_frozen": True,
                "external_transfer_feature_scores_opened": False,
                "release_heldout_opened": False,
                "public_verdict_enabled": False,
                "feature_version": 0,
                "transform_profile": EVALUATOR.PROFILE,
                "policy": POLICY.contract(),
                "corpus_plan": {
                    "path": str(plan_path),
                    "sha256": hashlib.sha256(
                        plan_path.read_bytes()
                    ).hexdigest(),
                },
                "tools": {
                    "evaluator_sha256": hashlib.sha256(
                        (
                            ROOT
                            / "scripts/"
                            "evaluate-audio-integrity-musdb18hq-external.py"
                        ).read_bytes()
                    ).hexdigest(),
                    "policy_module_sha256": hashlib.sha256(
                        (
                            ROOT
                            / "scripts/"
                            "audio_integrity_conservative_v28_policy.py"
                        ).read_bytes()
                    ).hexdigest(),
                    "external_runner_sha256": "external-runner",
                    "benchmark_runner_sha256": "benchmark-runner",
                    "low_bandwidth_probe_sha256": "support-probe",
                },
                "evidence": {
                    "performance_report_sha256": hashlib.sha256(
                        performance_path.read_bytes()
                    ).hexdigest(),
                },
                "external_transfer_gate": {
                    "maximum_tier_a_negative_false_positive_count": 0,
                    "minimum_supported_recall_per_scoped_class": 0.9,
                    "minimum_support_coverage_per_scoped_class": 0.75,
                    "scoped_classes": sorted(EVALUATOR.SCOPED_CLASSES),
                    "difficult_classes": sorted(
                        EVALUATOR.DIFFICULT_CLASSES
                    ),
                    "hard_negative_classes": sorted(
                        EVALUATOR.NEGATIVE_CLASSES
                    ),
                    "aac_invariant_source_group_count": 30,
                    "maximum_aac_invariant_mismatch_source_groups": 0,
                    "required_positive_reason_families": [
                        "persistent_spectral_edge",
                        "transform_frame_periodicity",
                    ],
                    "maximum_p95_runtime_overhead_percent": 10.0,
                    "minimum_independent_source_groups": 150,
                },
                "memory_contract": {
                    "no_new_full_spectrogram_sized_allocation": True,
                },
            }
            write_json(precommit_path, precommit)
            precommit_sha256 = hashlib.sha256(
                precommit_path.read_bytes()
            ).hexdigest()
            manifest_sha256 = hashlib.sha256(
                manifest_path.read_bytes()
            ).hexdigest()
            fingerprints_sha256 = hashlib.sha256(
                fingerprints_path.read_bytes()
            ).hexdigest()
            opening = {
                "state": "external_transfer_feature_scores_opened",
                "candidate_precommit_sha256": precommit_sha256,
                "release_heldout_opened": False,
                "public_verdict_enabled": False,
            }
            measurement_rows = []
            support_rows = []
            for case in cases:
                audio_sha256 = fingerprints["case_sha256"][
                    case["case_id"]
                ]
                positive = case["expectation"] == "controlled_positive"
                measurement_rows.append(
                    {
                        **case,
                        "audio_sha256": audio_sha256,
                        "runner": runner(
                            mp3_aggregate=2.0 if positive else 1.4,
                            edge_drop=4.0 if positive else 0.0,
                        ),
                    }
                )
                support_rows.append(
                    {
                        **case,
                        "audio_sha256": audio_sha256,
                        "features": low_bandwidth(),
                    }
                )
            measurement = {
                "schema_version": 1,
                "state": "frozen_external_transfer_measurement_complete",
                "candidate_id": EVALUATOR.CANDIDATE_ID,
                "candidate_frozen": True,
                "external_transfer_feature_scores_opened": True,
                "release_heldout_opened": False,
                "public_verdict_enabled": False,
                "profile": EVALUATOR.PROFILE,
                "opening": opening,
                "candidate_precommit": {"sha256": precommit_sha256},
                "manifest": {"sha256": manifest_sha256},
                "fingerprints": {"sha256": fingerprints_sha256},
                "runner": {"sha256": "benchmark-runner"},
                "harness": {"sha256": "external-runner"},
                "case_count": len(measurement_rows),
                "results": measurement_rows,
            }
            support_report = {
                "schema_version": 1,
                "state": "frozen_external_transfer_support_measurement",
                "candidate_id": EVALUATOR.CANDIDATE_ID,
                "candidate_frozen": True,
                "external_transfer_feature_scores_opened": True,
                "release_heldout_opened": False,
                "public_verdict_enabled": False,
                "method_id": "low-bandwidth-support-discovery-v0",
                "opening": opening,
                "candidate_precommit": {"sha256": precommit_sha256},
                "manifest": {"sha256": manifest_sha256},
                "fingerprints": {"sha256": fingerprints_sha256},
                "tool": {"sha256": "support-probe"},
                "case_count": len(support_rows),
                "cases": support_rows,
            }
            write_json(measurement_path, measurement)
            write_json(support_path, support_report)

            arguments = [
                "evaluate-audio-integrity-musdb18hq-external.py",
                "--precommit",
                str(precommit_path),
                "--policy-module",
                str(
                    ROOT
                    / "scripts/audio_integrity_conservative_v28_policy.py"
                ),
                "--measurement",
                str(measurement_path),
                "--support-report",
                str(support_path),
                "--manifest",
                str(manifest_path),
                "--fingerprints",
                str(fingerprints_path),
                "--performance-report",
                str(performance_path),
                "--output",
                str(output_path),
            ]
            with mock.patch("sys.argv", arguments):
                self.assertEqual(EVALUATOR.main(), 0)
            passed = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertTrue(passed["gate"]["passed"])
            self.assertEqual(
                passed["disposition"],
                "external_transfer_passed_release_heldout_still_sealed",
            )

            failing_measurement = json.loads(
                json.dumps(measurement)
            )
            failing_runner = failing_measurement["results"][0]["runner"]
            failing_runner["compression_trace"][
                "spectral_edge_drop_db"
            ] = 4.0
            failing_runner["compression_trace"][
                "spectral_edge_persistence"
            ] = 0.01
            failing_runner["transform_grid_probe"]["mp3_long_sine"][
                "long_block_phase_aggregate_peak_z"
            ] = 2.0
            failing_measurement_path = root / "measurement-failing.json"
            failing_output_path = root / "evaluation-failing.json"
            write_json(failing_measurement_path, failing_measurement)
            failing_arguments = list(arguments)
            failing_arguments[
                failing_arguments.index(str(measurement_path))
            ] = str(failing_measurement_path)
            failing_arguments[
                failing_arguments.index(str(output_path))
            ] = str(failing_output_path)
            with mock.patch("sys.argv", failing_arguments):
                self.assertEqual(EVALUATOR.main(), 1)
            rejected = json.loads(
                failing_output_path.read_text(encoding="utf-8")
            )
            self.assertFalse(rejected["gate"]["passed"])
            self.assertEqual(
                rejected["gate"]["observed_false_positives"],
                1,
            )
            self.assertEqual(
                rejected["disposition"],
                "candidate_rejected_external_transfer_consumed",
            )


if __name__ == "__main__":
    unittest.main()
