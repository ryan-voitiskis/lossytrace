from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BENCHMARK = load_script("benchmark-audio-integrity.py")
EXPLAINABLE = load_script("analyze-audio-integrity-explainable-policy.py")
FORENSIC = load_script("analyze-audio-integrity-forensic.py")
CNN_RULE_ENSEMBLE = load_script(
    "analyze-audio-integrity-cnn-rule-ensemble.py"
)
FROZEN_RULES = load_script(
    "evaluate-audio-integrity-frozen-rules.py"
)
FETCH_PUBLIC = load_script("fetch-audio-integrity-public-sources.py")
FORENSIC_PERFORMANCE = load_script(
    "measure-audio-integrity-forensic-performance.py"
)
PUBLIC_NEGATIVES = load_script(
    "stage-audio-integrity-public-negatives.py"
)
NSYNTH_HARD_NEGATIVES = load_script(
    "stage-audio-integrity-nsynth-hard-negatives.py"
)
PUBLIC_TRANSCODES = load_script(
    "stage-audio-integrity-public-transcodes.py"
)
RELEASE_GATE = load_script("gate-audio-integrity-release.py")
STAGING = load_script("stage-audio-integrity-pilot.py")
STABLE_RULES = load_script(
    "analyze-audio-integrity-stable-rule-set.py"
)


def manifest_case(
    case_id: str,
    source_group: str,
    split: str,
) -> dict:
    return {
        "case_id": case_id,
        "source_group": source_group,
        "relative_path": f"{case_id}.wav",
        "provenance_tier": "tier_a_confirmed_pcm",
        "split": split,
        "class": "fixture",
        "expectation": "negative",
    }


class ManifestTests(unittest.TestCase):
    def test_rejects_source_group_split_leakage(self) -> None:
        manifest = {
            "schema_version": 1,
            "corpus_id": "fixture",
            "corpus_version": 1,
            "audio_root_env": "FIXTURE_ROOT",
            "analysis_max_seconds": 1,
            "repetitions": 1,
            "cases": [
                manifest_case("development", "shared", "development"),
                manifest_case("held-out", "shared", "held_out"),
            ],
        }
        failures = BENCHMARK.validate_manifest(manifest)
        self.assertTrue(
            any("crosses splits" in failure for failure in failures),
            failures,
        )

    def test_rejects_partition_group_split_leakage(self) -> None:
        development = manifest_case("development", "source-a", "development")
        held_out = manifest_case("held-out", "source-b", "held_out")
        development["partition_group"] = "shared-performer"
        held_out["partition_group"] = "shared-performer"
        manifest = {
            "schema_version": 1,
            "corpus_id": "fixture",
            "corpus_version": 1,
            "audio_root_env": "FIXTURE_ROOT",
            "analysis_max_seconds": 1,
            "repetitions": 1,
            "cases": [development, held_out],
        }
        failures = BENCHMARK.validate_manifest(manifest)
        self.assertTrue(
            any(
                "partition_group 'shared-performer' crosses splits" in failure
                for failure in failures
            ),
            failures,
        )

    def test_resolve_beneath_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with self.assertRaises(SystemExit):
                BENCHMARK.resolve_beneath(root, "../outside.wav")


class CodecHoldoutTests(unittest.TestCase):
    def test_matrix_contains_eleven_unseen_settings(self) -> None:
        cases: list[dict] = []
        recipes: list[dict] = []
        STAGING.add_codec_holdout_variants(
            cases,
            recipes,
            "dev-001",
            "sources/dev-001.flac",
        )
        self.assertEqual(len(cases), 11)
        self.assertEqual(len(recipes), 11)
        self.assertEqual(
            {case["class"] for case in cases},
            {
                "aac_lc_96",
                "aac_lc_192",
                "aac_lc_320",
                "mp3_96",
                "mp3_192",
                "mp3_vbr_q2",
                "opus_64",
                "opus_128",
                "opus_192",
                "vorbis_q1",
                "vorbis_q7",
            },
        )
        self.assertTrue(
            all(case["expectation"] == "controlled_positive" for case in cases)
        )
        self.assertTrue(
            all(recipe["output_relative_path"].endswith(".flac") for recipe in recipes)
        )

    def test_excerpt_command_redacts_both_private_roots(self) -> None:
        command = [
            "ffmpeg",
            "-i",
            "/private/parent/sources/a.wav",
            "/private/output/sources/a.flac",
        ]
        redacted = STAGING.redacted_excerpt_command(
            command,
            parent_root=Path("/private/parent"),
            output_root=Path("/private/output"),
        )
        self.assertEqual(
            redacted,
            [
                "ffmpeg",
                "-i",
                "<PARENT_CORPUS>/sources/a.wav",
                "<AUDIO_ROOT>/sources/a.flac",
            ],
        )


class ResampleControlTests(unittest.TestCase):
    def test_selects_one_negative_untouched_case_per_development_group(
        self,
    ) -> None:
        manifest = {
            "cases": [
                {
                    "case_id": "b-original",
                    "source_group": "b",
                    "relative_path": "sources/b.wav",
                    "provenance_tier": "tier_b_trusted",
                    "split": "development",
                    "class": "untouched_lossless",
                    "expectation": "negative",
                },
                {
                    "case_id": "a-original",
                    "source_group": "a",
                    "relative_path": "sources/a.wav",
                    "provenance_tier": "tier_b_trusted",
                    "partition_group": "artist-a",
                    "split": "development",
                    "class": "untouched_lossless",
                    "expectation": "negative",
                },
                {
                    "case_id": "a-opus",
                    "source_group": "a",
                    "relative_path": "generated/a.opus.wav",
                    "provenance_tier": "tier_b_trusted",
                    "split": "development",
                    "class": "opus_96",
                    "expectation": "controlled_positive",
                },
            ]
        }
        selected = STAGING.untouched_development_cases(manifest)
        self.assertEqual(
            [case["case_id"] for case in selected],
            ["a-original", "b-original"],
        )
        self.assertEqual(selected[0]["partition_group"], "artist-a")

    def test_control_command_redacts_source_and_output_roots(self) -> None:
        command = [
            "ffmpeg",
            "-i",
            "/private/source/sources/a.wav",
            "/private/output/generated/control-001.wav",
        ]
        redacted = STAGING.redacted_control_command(
            command,
            source_root=Path("/private/source"),
            output_root=Path("/private/output"),
        )
        self.assertEqual(
            redacted,
            [
                "ffmpeg",
                "-i",
                "<SOURCE_CORPUS>/sources/a.wav",
                "<AUDIO_ROOT>/generated/control-001.wav",
            ],
        )


class NsynthHardNegativeTests(unittest.TestCase):
    def test_selects_evenly_spaced_notes_per_instrument(self) -> None:
        examples = {
            f"guitar_acoustic_001-{pitch:03}-100": {
                "note_str": f"guitar_acoustic_001-{pitch:03}-100",
                "instrument": 1,
                "instrument_str": "guitar_acoustic_001",
                "instrument_family_str": "guitar",
                "instrument_source_str": "acoustic",
                "pitch": pitch,
                "velocity": 100,
                "qualities_str": [],
            }
            for pitch in range(20, 30)
        }
        selected = NSYNTH_HARD_NEGATIVES.select_notes(examples)
        self.assertEqual(
            [item["pitch"] for item in selected[1]],
            [20, 21, 23, 24, 25, 26, 28, 29],
        )

    def test_pcm_reader_and_montage_preserve_exact_frame_contract(
        self,
    ) -> None:
        frame_count = NSYNTH_HARD_NEGATIVES.SOURCE_SAMPLE_RATE * 4
        encoded = io.BytesIO()
        with wave.open(encoded, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(
                NSYNTH_HARD_NEGATIVES.SOURCE_SAMPLE_RATE
            )
            output.writeframes(b"\x01\x00" * frame_count)
        frames, actual_count = NSYNTH_HARD_NEGATIVES.read_pcm_wav(
            encoded.getvalue(),
            "fixture",
        )
        self.assertEqual(actual_count, frame_count)
        notes = [
            {
                "pcm_frames": frames,
                "pcm_frame_count": actual_count,
            }
            for _ in range(NSYNTH_HARD_NEGATIVES.NOTES_PER_INSTRUMENT)
        ]
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "montage.wav"
            written = NSYNTH_HARD_NEGATIVES.write_montage_wav(
                path,
                notes,
                30,
            )
            self.assertEqual(
                written,
                NSYNTH_HARD_NEGATIVES.SOURCE_SAMPLE_RATE * 30,
            )
            with wave.open(str(path), "rb") as source:
                self.assertEqual(source.getnframes(), written)
                self.assertEqual(source.getframerate(), 16_000)


class FrozenRuleEvaluationTests(unittest.TestCase):
    def test_rule_requires_both_frozen_conditions(self) -> None:
        rule = {
            "first": {
                "feature": "compression_trace.band_rupture_score",
                "family": "band_rupture",
                "direction": "higher",
                "threshold": 0.5,
            },
            "second": {
                "feature": (
                    "transform_grid_probe.long_vorbis."
                    "phase_peak_z_median"
                ),
                "family": "transform_grid",
                "direction": "higher",
                "threshold": 3.0,
            },
        }
        passed, missing = FROZEN_RULES.evaluate_rule(
            {
                "compression_trace.band_rupture_score": 0.6,
                (
                    "transform_grid_probe.long_vorbis."
                    "phase_peak_z_median"
                ): 3.1,
            },
            rule,
        )
        self.assertTrue(passed)
        self.assertEqual(missing, [])
        passed, missing = FROZEN_RULES.evaluate_rule(
            {"compression_trace.band_rupture_score": 0.6},
            rule,
        )
        self.assertFalse(passed)
        self.assertEqual(
            missing,
            [
                (
                    "transform_grid_probe.long_vorbis."
                    "phase_peak_z_median"
                )
            ],
        )


class ExplainablePolicyTests(unittest.TestCase):
    def test_zero_negative_two_family_policy_selects_positive_rows(self) -> None:
        rows = [
            {
                "case_id": "negative-a",
                "source_group": "a",
                "class": "negative",
                "expectation": "negative",
                "features": {
                    "compression_trace.band_rupture_score": 0.1,
                    "compression_trace.spectral_edge_drop_db": 1.0,
                },
            },
            {
                "case_id": "negative-b",
                "source_group": "b",
                "class": "negative",
                "expectation": "negative",
                "features": {
                    "compression_trace.band_rupture_score": 0.2,
                    "compression_trace.spectral_edge_drop_db": 2.0,
                },
            },
            {
                "case_id": "positive-a",
                "source_group": "c",
                "class": "positive",
                "expectation": "controlled_positive",
                "features": {
                    "compression_trace.band_rupture_score": 0.8,
                    "compression_trace.spectral_edge_drop_db": 8.0,
                },
            },
            {
                "case_id": "positive-b",
                "source_group": "d",
                "class": "positive",
                "expectation": "controlled_positive",
                "features": {
                    "compression_trace.band_rupture_score": 0.9,
                    "compression_trace.spectral_edge_drop_db": 9.0,
                },
            },
        ]
        policy = EXPLAINABLE.best_two_family_policy(rows, 0.0)
        self.assertIsNotNone(policy)
        selected = EXPLAINABLE.select(rows, policy)
        self.assertEqual(selected, {"positive-a", "positive-b"})

    def test_greedy_rule_set_can_cover_distinct_codec_grids(self) -> None:
        rows = [
            {
                "case_id": "negative-a",
                "source_group": "a",
                "class": "negative",
                "expectation": "negative",
                "features": {
                    "compression_trace.band_rupture_score": 0.1,
                    "compression_trace.spectral_hole_ratio": 0.1,
                    "transform_grid_probe.mp3.phase_peak_concentration": 0.1,
                    "transform_grid_probe.vorbis.phase_peak_concentration": 0.1,
                },
            },
            {
                "case_id": "negative-b",
                "source_group": "b",
                "class": "negative",
                "expectation": "negative",
                "features": {
                    "compression_trace.band_rupture_score": 0.2,
                    "compression_trace.spectral_hole_ratio": 0.2,
                    "transform_grid_probe.mp3.phase_peak_concentration": 0.2,
                    "transform_grid_probe.vorbis.phase_peak_concentration": 0.2,
                },
            },
            {
                "case_id": "positive-mp3",
                "source_group": "c",
                "class": "mp3",
                "expectation": "controlled_positive",
                "features": {
                    "compression_trace.band_rupture_score": 0.9,
                    "compression_trace.spectral_hole_ratio": 0.1,
                    "transform_grid_probe.mp3.phase_peak_concentration": 0.9,
                    "transform_grid_probe.vorbis.phase_peak_concentration": 0.1,
                },
            },
            {
                "case_id": "positive-vorbis",
                "source_group": "d",
                "class": "vorbis",
                "expectation": "controlled_positive",
                "features": {
                    "compression_trace.band_rupture_score": 0.1,
                    "compression_trace.spectral_hole_ratio": 0.9,
                    "transform_grid_probe.mp3.phase_peak_concentration": 0.1,
                    "transform_grid_probe.vorbis.phase_peak_concentration": 0.9,
                },
            },
        ]
        policy = EXPLAINABLE.best_rule_set_policy(rows, 0.0, 2)
        self.assertIsNotNone(policy)
        selected = EXPLAINABLE.select(rows, policy)
        self.assertEqual(selected, {"positive-mp3", "positive-vorbis"})

    def test_external_candidate_is_applied_without_refitting(self) -> None:
        def candidate_row(
            case_id: str,
            source_group: str,
            expectation: str,
            rupture: float,
            edge: float,
            partition_group: str | None = None,
        ) -> dict:
            return {
                "case_id": case_id,
                "source_group": source_group,
                "partition_group": (
                    partition_group or f"partition-{source_group}"
                ),
                "class": expectation,
                "expectation": expectation,
                "runner": {
                    "compression_trace": {
                        "band_rupture_score": rupture,
                        "spectral_edge_drop_db": edge,
                    },
                    "stereo_trace": None,
                    "transform_grid_probe": None,
                },
            }

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            training = root / "training.json"
            evaluation = root / "evaluation.json"
            output = root / "report.json"
            shared = {
                "schema_version": 1,
                "feature_version": 0,
                "runner_sha256": "a" * 64,
                "harness_sha256": "b" * 64,
            }
            training.write_text(
                json.dumps(
                    {
                        **shared,
                        "results": [
                            candidate_row(
                                "negative-a", "a", "negative", 0.1, 1.0
                            ),
                            candidate_row(
                                "negative-b", "b", "negative", 0.2, 2.0
                            ),
                            candidate_row(
                                "positive-c",
                                "c",
                                "controlled_positive",
                                0.8,
                                8.0,
                            ),
                            candidate_row(
                                "positive-d",
                                "d",
                                "controlled_positive",
                                0.9,
                                9.0,
                            ),
                        ],
                    }
                ),
                encoding="utf-8",
            )
            evaluation.write_text(
                json.dumps(
                    {
                        **shared,
                        "results": [
                            candidate_row(
                                "external-negative",
                                "external",
                                "negative",
                                0.85,
                                8.5,
                            )
                        ],
                    }
                ),
                encoding="utf-8",
            )
            EXPLAINABLE.command(
                argparse.Namespace(
                    candidate=[training],
                    evaluation_candidate=[evaluation],
                    folds=2,
                    fold_seed=1,
                    maximum_negative_pass_rate=0.0,
                    maximum_rules=1,
                    allow_legacy_uncommitted_candidates=False,
                    output=output,
                )
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            external = report["external_evaluation"]
            self.assertFalse(external["thresholds_refit"])
            self.assertTrue(external["source_groups_disjoint"])
            self.assertTrue(external["partition_groups_disjoint"])
            self.assertEqual(external["summary"]["false_positive_count"], 1)
            self.assertEqual(
                external["selected_case_ids"],
                ["external-negative"],
            )
            overlapping = json.loads(
                evaluation.read_text(encoding="utf-8")
            )
            overlapping["results"][0]["partition_group"] = "partition-a"
            evaluation.write_text(
                json.dumps(overlapping),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                SystemExit,
                "overlapping partition groups",
            ):
                EXPLAINABLE.command(
                    argparse.Namespace(
                        candidate=[training],
                        evaluation_candidate=[evaluation],
                        folds=2,
                        fold_seed=1,
                        maximum_negative_pass_rate=0.0,
                        maximum_rules=1,
                        allow_legacy_uncommitted_candidates=False,
                        output=root / "overlapping-report.json",
                    )
                )

    def test_stable_rule_template_ignores_fitted_thresholds(self) -> None:
        first = {
            "families": ["band_rupture", "transform_grid"],
            "first": {
                "family": "band_rupture",
                "feature": "compression_trace.band_rupture_score",
                "direction": "higher",
                "requested_maximum_negative_rate": 0.2,
                "threshold": 0.1,
            },
            "second": {
                "family": "transform_grid",
                "feature": "transform_grid_probe.mp3.phase_score",
                "direction": "higher",
                "requested_maximum_negative_rate": 0.0,
                "threshold": 4.0,
            },
        }
        second = json.loads(json.dumps(first))
        second["first"]["threshold"] = 0.2
        second["second"]["threshold"] = 5.0
        self.assertEqual(
            STABLE_RULES.template_key(first),
            STABLE_RULES.template_key(second),
        )

    def test_phase_periodicity_is_a_forensic_transform_family(self) -> None:
        self.assertEqual(
            FORENSIC.feature_family(
                "transform_grid_probe.long_vorbis."
                "phase_consistent_peak_score"
            ),
            "transform_grid",
        )


class CnnRuleEnsembleTests(unittest.TestCase):
    @staticmethod
    def rows() -> list[dict]:
        rows = []
        for group, fold in (("group-a", 1), ("group-b", 2)):
            for expectation, score in (
                ("negative", 0.1),
                ("controlled_positive", 0.9),
            ):
                case_id = f"{group}-{expectation}"
                rows.append(
                    {
                        "case_id": case_id,
                        "source_group": group,
                        "partition_group": group,
                        "class": expectation,
                        "expectation": expectation,
                        "features": {
                            "compression_trace.band_rupture_score": score,
                            "compression_trace.spectral_edge_drop_db": (
                                score * 10
                            ),
                        },
                        "fold": fold,
                    }
                )
        return rows

    def test_cnn_rows_average_matching_grouped_reports(self) -> None:
        candidates = self.rows()
        reports = []
        for seed, offset in ((1, 0.0), (2, 0.1)):
            reports.append(
                {
                    "seed": seed,
                    "manifest_signature": "manifest",
                    "fingerprint_signature": "fingerprints",
                    "feature_cache_sha256": "cache",
                    "fold_seed": 3,
                    "early_stop_seed": 4,
                    "fold_count": 2,
                    "results": [
                        {
                            **{
                                key: row[key]
                                for key in (
                                    "case_id",
                                    "source_group",
                                    "partition_group",
                                    "class",
                                    "expectation",
                                    "fold",
                                )
                            },
                            "lossy_probability_mean": (
                                row["features"][
                                    "compression_trace."
                                    "band_rupture_score"
                                ]
                                + offset
                            ),
                        }
                        for row in candidates
                    ],
                }
            )
        combined = CNN_RULE_ENSEMBLE.cnn_rows(reports, candidates)
        positive = next(
            row
            for row in combined
            if row["case_id"] == "group-a-controlled_positive"
        )
        self.assertAlmostEqual(positive["cnn_ensemble_score"], 0.95)

    def test_nested_rule_selection_replays_fold_policies(self) -> None:
        rows = self.rows()
        fold_seed = 17
        groups = sorted({row["partition_group"] for row in rows})
        shuffled = groups.copy()
        CNN_RULE_ENSEMBLE.random.Random(fold_seed).shuffle(shuffled)
        group_fold = {
            group: index % 2 + 1
            for index, group in enumerate(shuffled)
        }
        policy = {
            "first": {
                "feature": "compression_trace.band_rupture_score",
                "direction": "higher",
                "threshold": 0.5,
            },
            "second": {
                "feature": "compression_trace.spectral_edge_drop_db",
                "direction": "higher",
                "threshold": 5.0,
            },
        }
        fold_reports = []
        selected = set()
        for fold in (1, 2):
            validation = [
                row
                for row in rows
                if group_fold[row["partition_group"]] == fold
            ]
            fold_selected = EXPLAINABLE.select(validation, policy)
            selected.update(fold_selected)
            fold_reports.append(
                {
                    "fold": fold,
                    "fitted_policy": policy,
                    "validation": EXPLAINABLE.summary(
                        validation,
                        fold_selected,
                    ),
                }
            )
        stable = {
            "method": {"fold_count": 2, "fold_seed": fold_seed},
            "selected_templates": [
                {
                    "folds": fold_reports,
                    "oof_summary": EXPLAINABLE.summary(rows, selected),
                }
            ],
            "nested_grouped_evaluation": EXPLAINABLE.summary(
                rows,
                selected,
            ),
        }
        self.assertEqual(
            CNN_RULE_ENSEMBLE.nested_rule_selection(stable, rows),
            {
                "group-a-controlled_positive",
                "group-b-controlled_positive",
            },
        )


class IntegrityManifestTests(unittest.TestCase):
    def test_named_integrity_manifest_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "result.json"
            artifact.write_text('{"ok": true}\n', encoding="utf-8")
            STAGING.write_integrity_manifest(
                root,
                "fixture-run",
                "artifact-integrity.json",
            )
            self.assertEqual(
                STAGING.verify_corpus_integrity(
                    root,
                    "fixture-run",
                    "artifact-integrity.json",
                ),
                [],
            )
            artifact.write_text('{"ok": null}\n', encoding="utf-8")
            failures = STAGING.verify_corpus_integrity(
                root,
                "fixture-run",
                "artifact-integrity.json",
            )
            self.assertTrue(
                any("SHA-256 differs" in failure for failure in failures),
                failures,
            )


class MemoryMeasurementTests(unittest.TestCase):
    def test_parses_darwin_peak_rss_bytes(self) -> None:
        self.assertEqual(
            BENCHMARK.parse_peak_rss(
                "  123456  maximum resident set size\n",
                "Darwin",
            ),
            123456,
        )

    def test_parses_linux_peak_rss_kibibytes(self) -> None:
        self.assertEqual(
            BENCHMARK.parse_peak_rss(
                "\tMaximum resident set size (kbytes): 123\n",
                "Linux",
            ),
            123 * 1024,
        )

    def test_forensic_performance_parses_darwin_peak_rss_bytes(self) -> None:
        self.assertEqual(
            FORENSIC_PERFORMANCE.parse_peak_rss(
                "  654321  maximum resident set size\n",
                "Darwin",
            ),
            654321,
        )

    def test_forensic_performance_accepts_stable_grid_profile(self) -> None:
        arguments = FORENSIC_PERFORMANCE.parser().parse_args(
            [
                "--manifest",
                "manifest.json",
                "--fingerprints",
                "fingerprints.json",
                "--audio-root",
                "audio",
                "--binary",
                "runner",
                "--grid-profile",
                "stable-v15",
                "--output",
                "report.json",
            ]
        )
        self.assertEqual(arguments.grid_profile, "stable-v15")


class PublicSourceRegistryTests(unittest.TestCase):
    def test_checked_in_registry_is_valid_and_permissively_licensed(self) -> None:
        registry = FETCH_PUBLIC.load_json(FETCH_PUBLIC.DEFAULT_REGISTRY)
        self.assertEqual(FETCH_PUBLIC.validate_registry(registry), [])
        self.assertGreaterEqual(len(registry["sources"]), 4)
        self.assertTrue(
            all(source["license"] == "CC BY 4.0" for source in registry["sources"])
        )

    def test_provider_digest_uses_declared_algorithm(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "artifact"
            path.write_bytes(b"fixture")
            self.assertEqual(
                FETCH_PUBLIC.provider_digest(
                    path,
                    "sha256:"
                    "f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d",
                ),
                "sha256:"
                "f16d05ec6b29248d2c61adb1e9263f78e4f7bace1b955014a2d17872cfe4064d",
            )

    def test_fetch_resumes_and_retries_transport_errors(self) -> None:
        command = FETCH_PUBLIC.curl_resume_command(
            "curl",
            Path("/private/.artifact.partial"),
            "https://example.test/artifact",
        )
        self.assertIn("--continue-at", command)
        self.assertIn("--retry-all-errors", command)
        self.assertEqual(command[command.index("--retry") + 1], "10")
        self.assertEqual(command[-1], "https://example.test/artifact")


class PublicNegativeStagingTests(unittest.TestCase):
    def test_guitarset_selects_largest_master_per_player(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "guitarset.zip"
            with zipfile.ZipFile(path, "w") as archive:
                for player in range(6):
                    archive.writestr(
                        f"{player:02}_short_mic.wav",
                        b"x",
                    )
                    archive.writestr(
                        f"{player:02}_long_mic.wav",
                        b"longer",
                    )
            with zipfile.ZipFile(path) as archive:
                selected = PUBLIC_NEGATIVES.select_guitarset(archive)
            self.assertEqual(len(selected), 6)
            self.assertTrue(
                all(info.filename.endswith("_long_mic.wav") for info in selected.values())
            )

    def test_rejects_parent_traversal_zip_member(self) -> None:
        info = zipfile.ZipInfo("../outside.wav")
        info.file_size = 10
        with self.assertRaises(SystemExit):
            PUBLIC_NEGATIVES.validate_member(info)

    def test_groove_ignores_blank_audio_filename_directory_entry(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "groove.zip"
            drummer_numbers = (1, 3, 4, 5, 6, 7, 8, 9, 10)
            rows = [
                (
                    f"drummer{number}",
                    f"drummer{number}/session1",
                    f"drummer{number}/session1/1",
                    "rock",
                    "120",
                    "beat",
                    "4-4",
                    f"drummer{number}/session1/example.mid",
                    f"drummer{number}/session1/example.wav",
                    "10.0",
                    "train",
                )
                for number in drummer_numbers
            ]
            rows.append(
                (
                    "drummer2",
                    "drummer2/session1",
                    "drummer2/session1/1",
                    "rock",
                    "120",
                    "beat",
                    "4-4",
                    "drummer2/session1/example.mid",
                    "",
                    "100.0",
                    "train",
                )
            )
            metadata = io.StringIO()
            writer = csv.writer(metadata)
            writer.writerow(
                (
                    "drummer",
                    "session",
                    "id",
                    "style",
                    "bpm",
                    "beat_type",
                    "time_signature",
                    "midi_filename",
                    "audio_filename",
                    "duration",
                    "split",
                )
            )
            writer.writerows(rows)
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("groove/", b"")
                archive.writestr("groove/info.csv", metadata.getvalue())
                for number in drummer_numbers:
                    archive.writestr(
                        f"groove/drummer{number}/session1/example.wav",
                        b"pcm",
                    )
            with zipfile.ZipFile(path) as archive:
                selected = PUBLIC_NEGATIVES.select_groove(archive)
            self.assertEqual(
                set(selected),
                {f"drummer-{number}" for number in drummer_numbers},
            )


class PublicTranscodeStagingTests(unittest.TestCase):
    def test_parser_exposes_stage_and_verify_commands(self) -> None:
        stage_arguments = PUBLIC_TRANSCODES.parser().parse_args(
            [
                "stage",
                "--parent-root",
                "parent",
                "--destination",
                "destination",
                "--run-id",
                "fixture-run",
                "--corpus-id",
                "fixture-corpus",
            ]
        )
        verify_arguments = PUBLIC_TRANSCODES.parser().parse_args(
            ["verify", "--root", "corpus"]
        )
        self.assertIs(stage_arguments.function, PUBLIC_TRANSCODES.stage)
        self.assertIs(verify_arguments.function, PUBLIC_TRANSCODES.verify)

    def test_excerpt_is_centered_and_never_negative(self) -> None:
        self.assertEqual(PUBLIC_TRANSCODES.excerpt_start(30.0, 90.0), 0.0)
        self.assertEqual(PUBLIC_TRANSCODES.excerpt_start(130.0, 90.0), 20.0)

    def test_recipe_matrix_has_controls_and_four_lossy_codecs(self) -> None:
        recipes = PUBLIC_TRANSCODES.recipe_definitions()
        self.assertEqual(len(recipes), 6)
        self.assertEqual(
            [recipe["expectation"] for recipe in recipes].count("negative"),
            2,
        )
        self.assertEqual(
            {
                recipe["class"]
                for recipe in recipes
                if recipe["expectation"] == "controlled_positive"
            },
            {
                "public_mp3_128_to_flac16",
                "public_aac_lc_128_to_flac16",
                "public_opus_96_to_flac16",
                "public_vorbis_native_q3_to_flac16",
            },
        )

    def test_transcode_command_redacts_parent_and_output_roots(self) -> None:
        command = [
            "ffmpeg",
            "-i",
            "/private/parent/audio/source.wav",
            "/private/output/generated/case.flac",
        ]
        self.assertEqual(
            PUBLIC_TRANSCODES.redacted_command(
                command,
                parent_root=Path("/private/parent"),
                output_root=Path("/private/output"),
            ),
            [
                "ffmpeg",
                "-i",
                "<PARENT_CORPUS>/audio/source.wav",
                "<AUDIO_ROOT>/generated/case.flac",
            ],
        )


class ReleaseGateTests(unittest.TestCase):
    @staticmethod
    def write_json(path: Path, value: dict) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def fingerprints(cases: list[dict], corpus_id: str) -> dict:
        return {
            "schema_version": 1,
            "corpus_id": corpus_id,
            "corpus_version": 1,
            "case_sha256": {
                case["case_id"]: hashlib.sha256(
                    case["case_id"].encode()
                ).hexdigest()
                for case in cases
            },
        }

    @staticmethod
    def cases(split: str, group_prefix: str, case_prefix: str) -> list[dict]:
        definitions = (
            ("pristine_pcm", "negative"),
            ("level_shift_pcm", "negative"),
            ("sharp_cut_pcm", "negative"),
            ("codec_low", "controlled_positive"),
        )
        cases = []
        for group_number in (1, 2):
            source_group = f"{group_prefix}{group_number:03}"
            for case_number, (class_name, expectation) in enumerate(
                definitions,
                1,
            ):
                case_id = (
                    f"{case_prefix}{group_number:03}{case_number:03}"
                )
                cases.append(
                    {
                        "case_id": case_id,
                        "source_group": source_group,
                        "partition_group": f"{group_prefix}part{group_number:03}",
                        "relative_path": f"cases/{case_id}.flac",
                        "provenance_tier": "tier_a_confirmed_pcm",
                        "split": split,
                        "class": class_name,
                        "expectation": expectation,
                        "private_note": "must not enter blind manifest",
                    }
                )
        return cases

    def seal_fixture(self, root: Path) -> dict[str, Path | dict]:
        cases = self.cases("held_out", "sg", "hc")
        manifest = {
            "schema_version": 1,
            "corpus_id": "fixture-private",
            "corpus_version": 1,
            "audio_root_env": "FIXTURE_AUDIO_ROOT",
            "analysis_max_seconds": 1,
            "repetitions": 3,
            "cases": cases,
            "recipes": [{"private": True}],
        }
        fingerprints = self.fingerprints(cases, manifest["corpus_id"])
        paths = {
            "manifest": root / "heldout.json",
            "fingerprints": root / "heldout-fingerprints.json",
            "blind": root / "blind.json",
            "labels": root / "labels.json",
            "seal": root / "seal.json",
        }
        self.write_json(paths["manifest"], manifest)
        self.write_json(paths["fingerprints"], fingerprints)
        result = RELEASE_GATE.command_seal(
            argparse.Namespace(
                manifest=paths["manifest"],
                fingerprints=paths["fingerprints"],
                seal_id="seal001",
                minimum_negative_source_groups=2,
                blind_manifest=paths["blind"],
                labels=paths["labels"],
                output=paths["seal"],
            )
        )
        self.assertEqual(result, 0)
        return {**paths, "manifest_value": manifest}

    def freeze_fixture(
        self,
        root: Path,
        sealed: dict[str, Path | dict],
    ) -> Path:
        cases = self.cases("development", "dg", "dc")
        manifest = {
            "schema_version": 1,
            "corpus_id": "fixture-development",
            "corpus_version": 1,
            "audio_root_env": "FIXTURE_AUDIO_ROOT",
            "analysis_max_seconds": 1,
            "repetitions": 3,
            "cases": cases,
        }
        fingerprints = self.fingerprints(cases, manifest["corpus_id"])
        report = {
            "schema_version": 1,
            "case_count": len(cases),
            "disposition": {
                "held_out_opened": False,
                "public_verdict_enabled": False,
            },
            "nested_grouped_evaluation": {
                "negative_count": 6,
                "false_positive_count": 0,
                "controlled_positive_count": 2,
                "detected_positive_count": 2,
                "detected_by_class": {"codec_low": 2},
            },
            "full_development_policy": {
                "first": {
                    "feature": "compression_trace.band_rupture_score",
                    "family": "band_rupture",
                    "direction": "higher",
                    "threshold": 0.5,
                },
                "second": {
                    "feature": "compression_trace.spectral_edge_drop_db",
                    "family": "spectral_edge",
                    "direction": "higher",
                    "threshold": 5.0,
                },
            },
        }
        manifest_path = root / "development.json"
        fingerprints_path = root / "development-fingerprints.json"
        report_path = root / "development-report.json"
        freeze_path = root / "freeze.json"
        runner_path = root / "audio-integrity-runner"
        runner_path.write_bytes(b"fixture runner")
        runner_sha256 = RELEASE_GATE.sha256_file(runner_path)
        harness_sha256 = RELEASE_GATE.sha256_file(
            RELEASE_GATE.BENCHMARK_HARNESS_PATH
        )
        candidate_path = root / "development-candidate.json"
        self.write_json(
            candidate_path,
            {
                "schema_version": 1,
                "feature_version": 0,
                "runner_sha256": runner_sha256,
                "harness_sha256": harness_sha256,
                "results": [
                    {
                        **case,
                        "runner": {
                            "audio_sha256": fingerprints["case_sha256"][
                                case["case_id"]
                            ],
                            "feature_version": 0,
                        },
                    }
                    for case in cases
                ],
            },
        )
        report["candidate_evidence"] = [
            {
                "report_sha256": RELEASE_GATE.sha256_file(candidate_path),
                "runner_sha256": runner_sha256,
                "harness_sha256": harness_sha256,
                "feature_version": 0,
                "case_count": len(cases),
            }
        ]
        self.write_json(manifest_path, manifest)
        self.write_json(fingerprints_path, fingerprints)
        self.write_json(report_path, report)
        result = RELEASE_GATE.command_freeze(
            argparse.Namespace(
                development_report=report_path,
                development_manifest=[manifest_path],
                development_fingerprints=[fingerprints_path],
                development_candidate=[candidate_path],
                runner=runner_path,
                heldout_seal=sealed["seal"],
                freeze_id="freeze001",
                minimum_development_recall=1.0,
                minimum_heldout_recall=0.3,
                maximum_false_positive_upper_95=0.7,
                minimum_negative_source_groups=2,
                minimum_invariant_source_groups=2,
                maximum_invariant_relative_delta=0.1,
                maximum_p95_runtime_overhead_percent=10.0,
                maximum_peak_memory_increase_percent=10.0,
                minimum_timing_repetitions=3,
                obvious_positive_class=["codec_low"],
                hard_negative_class=["sharp_cut_pcm"],
                reference_negative_class=["pristine_pcm"],
                invariant_control_class=["level_shift_pcm"],
                output=freeze_path,
            )
        )
        self.assertEqual(result, 0)
        return freeze_path

    def test_seal_removes_private_fields_and_is_unopened(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            sealed = self.seal_fixture(Path(temporary))
            blind = RELEASE_GATE.load_json(sealed["blind"])
            seal = RELEASE_GATE.load_json(sealed["seal"])
            self.assertNotIn("recipes", blind)
            self.assertTrue(blind["recipes_omitted"])
            self.assertTrue(
                all(
                    set(case)
                    == {
                        *RELEASE_GATE.BLIND_CASE_FIELDS,
                        "class",
                        "expectation",
                    }
                    for case in blind["cases"]
                )
            )
            self.assertTrue(
                all(case["class"] == "sealed_case" for case in blind["cases"])
            )
            self.assertEqual(seal["state"], "sealed_unopened")
            self.assertFalse(seal["labels_opened"])
            self.assertEqual(seal["evaluation_count"], 0)

    def test_freeze_then_one_shot_evaluation_passes_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            sealed = self.seal_fixture(root)
            freeze_path = self.freeze_fixture(root, sealed)
            freeze = RELEASE_GATE.load_json(freeze_path)
            implementation = freeze["implementation_commitment"]
            blind = RELEASE_GATE.load_json(sealed["blind"])
            fingerprints = RELEASE_GATE.load_json(sealed["fingerprints"])
            rows = []
            for case in blind["cases"]:
                original = next(
                    item
                    for item in sealed["manifest_value"]["cases"]
                    if item["case_id"] == case["case_id"]
                )
                features_by_class = {
                    "pristine_pcm": (0.1, 1.0),
                    "level_shift_pcm": (0.105, 1.05),
                    "sharp_cut_pcm": (0.2, 2.0),
                    "codec_low": (0.9, 9.0),
                }
                rupture, edge = features_by_class[original["class"]]
                rows.append(
                    {
                        **case,
                        "runner": {
                            "audio_sha256": fingerprints["case_sha256"][
                                case["case_id"]
                            ],
                            "feature_version": 0,
                            "repetitions": 3,
                            "runtime_overhead_percent": 1.0,
                            "compression_trace": {
                                "band_rupture_score": rupture,
                                "spectral_edge_drop_db": edge,
                            },
                            "stereo_trace": None,
                            "transform_grid_probe": None,
                        },
                    }
                )
            candidate_path = root / "candidate.json"
            self.write_json(
                candidate_path,
                {
                    "schema_version": 1,
                    "feature_version": 0,
                    "runner_sha256": implementation["runner_sha256"],
                    "harness_sha256": implementation[
                        "benchmark_harness_sha256"
                    ],
                    "analysis_max_seconds": 1,
                    "repetitions": 3,
                    "runtime": {"jobs": 1},
                    "results": rows,
                },
            )
            memory_path = root / "memory.json"
            self.write_json(
                memory_path,
                {
                    "schema_version": 1,
                    "manifest_sha256": RELEASE_GATE.sha256_file(
                        sealed["blind"]
                    ),
                    "fingerprints_sha256": RELEASE_GATE.sha256_file(
                        sealed["fingerprints"]
                    ),
                    "feature_version": 0,
                    "runner_sha256": implementation["runner_sha256"],
                    "harness_sha256": implementation[
                        "benchmark_harness_sha256"
                    ],
                    "case_count": len(rows),
                    "case_ids": sorted(row["case_id"] for row in rows),
                    "measurement_method": "isolated fixture",
                    "baseline_peak_rss_bytes": 1000,
                    "prototype_peak_rss_bytes": 1050,
                    "observations": [
                        {
                            "case_id": row["case_id"],
                            "baseline_peak_rss_bytes": 1000,
                            "prototype_peak_rss_bytes": 1050,
                        }
                        for row in rows
                    ],
                },
            )
            output_path = root / "evaluation.json"
            result = RELEASE_GATE.command_evaluate(
                argparse.Namespace(
                    freeze=freeze_path,
                    seal=sealed["seal"],
                    blind_manifest=sealed["blind"],
                    labels=sealed["labels"],
                    fingerprints=sealed["fingerprints"],
                    candidate=[candidate_path],
                    memory_report=memory_path,
                    confirm_seal_id="seal001",
                    output=output_path,
                )
            )
            self.assertEqual(result, 0)
            evaluation = RELEASE_GATE.load_json(output_path)
            self.assertTrue(evaluation["disposition"]["release_gate_passed"])
            self.assertFalse(
                evaluation["disposition"]["public_verdict_enabled"]
            )
            seal = RELEASE_GATE.load_json(sealed["seal"])
            self.assertEqual(seal["state"], "evaluated")
            self.assertTrue(seal["labels_opened"])
            self.assertEqual(seal["evaluation_count"], 1)
            with self.assertRaises(SystemExit):
                RELEASE_GATE.command_evaluate(
                    argparse.Namespace(
                        freeze=freeze_path,
                        seal=sealed["seal"],
                        blind_manifest=sealed["blind"],
                        labels=sealed["labels"],
                        fingerprints=sealed["fingerprints"],
                        candidate=[candidate_path],
                        memory_report=memory_path,
                        confirm_seal_id="seal001",
                        output=root / "evaluation-second.json",
                    )
                )

    def test_wilson_zero_of_150_upper_bound_is_below_2_5_percent(self) -> None:
        interval = RELEASE_GATE.wilson_interval(0, 150)
        self.assertIsNotNone(interval)
        self.assertLess(interval["high"], 0.025)


if __name__ == "__main__":
    unittest.main()
