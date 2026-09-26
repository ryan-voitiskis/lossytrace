from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
import wave
import zipfile
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-vctk.py"
SPEC = importlib.util.spec_from_file_location("vctk_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


AUDIO_ROOT = "clean_trainset_56spk_wav/"
TRANSCRIPT_ROOT = "trainset_56spk_txt/"
UTTERANCE_KEYS = ("p001_001", "p001_002", "p002_001", "p002_002")


def pcm_wave(seed: int) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(48000)
        target.writeframes(bytes([seed, 0, seed + 1, 0, seed + 2, 0]))
    return output.getvalue()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def binding(path: Path) -> dict[str, object]:
    return {
        "filename": path.name,
        "bytes": path.stat().st_size,
        "local_sha256": sha256(path),
        "provider_checksum": f"md5:{md5(path)}",
    }


class VctkAuditTest(unittest.TestCase):
    def make_inputs(
        self, root: Path, duplicate_pcm: bool = False
    ) -> dict[str, Path]:
        paths = {
            "audio": root / "audio.zip",
            "log": root / "log.zip",
            "transcripts": root / "transcripts.zip",
            "speaker_info": root / "speaker-info.txt",
            "readme": root / "README.txt",
            "paper": root / "paper.pdf",
            "license": root / "license_text",
            "rules": root / "rules.json",
        }

        with zipfile.ZipFile(
            paths["audio"], "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            target.writestr(AUDIO_ROOT, b"")
            for index, key in enumerate(UTTERANCE_KEYS, 1):
                seed = 1 if duplicate_pcm and index in {1, 3} else index * 4
                target.writestr(f"{AUDIO_ROOT}{key}.wav", pcm_wave(seed))

        with zipfile.ZipFile(
            paths["log"], "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            target.writestr(
                "log_trainset_56spk.txt",
                "".join(f"{key} babble 0\n" for key in UTTERANCE_KEYS),
            )

        with zipfile.ZipFile(
            paths["transcripts"], "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            target.writestr(TRANSCRIPT_ROOT, b"")
            for key in UTTERANCE_KEYS:
                target.writestr(f"{TRANSCRIPT_ROOT}{key}.txt", f"text for {key}\n")

        paths["speaker_info"].write_text(
            "ID AGE GENDER ACCENTS REGION\n"
            "001 30 F English South\n"
            "002 31 M Scottish North\n",
            encoding="utf-8",
        )
        paths["readme"].write_text("bound VCTK README\n", encoding="utf-8")
        paths["paper"].write_bytes(b"%PDF-1.4\nbound primary paper fixture\n")
        paths["license"].write_text("bound license fixture\n", encoding="utf-8")

        duplicate_group_count = 1 if duplicate_pcm else 0
        duplicate_excess = 1 if duplicate_pcm else 0
        duplicate_excluded = 2 if duplicate_pcm else 0
        rules = {
            "schema_version": 1,
            "state": "source_identity_rules_not_allocation",
            "source_id": "vctk_clean_56spk_2017",
            "audio_generated": False,
            "scores_opened": False,
            "selection_authorized": False,
            "artifact": binding(paths["audio"]),
            "metadata_artifact": binding(paths["log"]),
            "supporting_artifacts": {
                "transcripts": binding(paths["transcripts"]),
                "speaker_info": binding(paths["speaker_info"]),
                "vctk_readme": binding(paths["readme"]),
                "primary_paper": binding(paths["paper"]),
                "license": binding(paths["license"]),
            },
            "provider_record": {
                "dataset_doi": "fixture",
                "base_corpus_doi": "fixture",
            },
            "expected": {
                "audio_file_count": 4,
                "speaker_audio_file_counts": {"p001": 2, "p002": 2},
                "speaker_metadata_row_count": 2,
                "gender_counts": {"F": 1, "M": 1},
                "accent_counts": {"English": 1, "Scottish": 1},
                "log_summary": {
                    "member_name": "log_trainset_56spk.txt",
                    "row_count": 4,
                    "speaker_count": 2,
                    "noise_counts": {"babble": 4},
                    "snr_db_counts": {"0": 4},
                },
                "transcript_summary": {
                    "canonical_transcript_count": 4,
                    "macos_sidecar_file_count": 0,
                    "directory_member_count": 1,
                    "directory_member_ids": ["trainset_56spk_txt"],
                    "unexpected_regular_member_count": 0,
                },
                "audio_format": {
                    "format_tag": 1,
                    "sample_format": "signed_integer_pcm",
                    "channel_count": 1,
                    "sample_rate_hz": 48000,
                    "bits_per_sample": 16,
                },
                "duplicate_pcm_digest_group_count": duplicate_group_count,
                "duplicate_pcm_file_count_excess": duplicate_excess,
                "duplicate_pcm_file_count_excluded": duplicate_excluded,
                "conservative_partition_group_count": 2,
                "source_group_count": 2,
            },
            "future_group_cap": {
                "state": "preregistered_not_applied_before_source_freeze",
                "selected_speakers_per_gender": 1,
                "ranking_algorithm": MODULE.CAP_RANKING_ALGORITHM,
                "ranking_input": MODULE.CAP_RANKING_INPUT,
                "ranking_prefix": MODULE.CAP_RANKING_PREFIX,
            },
        }
        paths["rules"].write_text(json.dumps(rules), encoding="utf-8")
        return paths

    def audit(self, paths: dict[str, Path]) -> dict[str, object]:
        return MODULE.audit(
            paths["audio"],
            paths["log"],
            paths["transcripts"],
            paths["speaker_info"],
            paths["readme"],
            paths["paper"],
            paths["license"],
            paths["rules"],
        )

    def refresh_binding(
        self, paths: dict[str, Path], rules_key: str, artifact_path: Path
    ) -> None:
        rules = json.loads(paths["rules"].read_text(encoding="utf-8"))
        if rules_key.startswith("supporting_artifacts."):
            key = rules_key.split(".", 1)[1]
            rules["supporting_artifacts"][key] = binding(artifact_path)
        else:
            rules[rules_key] = binding(artifact_path)
        paths["rules"].write_text(json.dumps(rules), encoding="utf-8")

    def test_audit_binds_provider_identities_without_allocating_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            report = self.audit(paths)
            self.assertEqual("source_identity_evidence_only", report["state"])
            self.assertEqual(2, report["observed"]["audio_speaker_count"])
            self.assertEqual(
                2,
                report["conservative_reference_boundary"]["eligible_group_count"],
            )
            self.assertEqual(
                4,
                report["conservative_reference_boundary"][
                    "eligible_audio_file_count"
                ],
            )
            self.assertFalse(report["selection_authorized"])
            self.assertTrue(
                report["archive_bindings"]["audio"]["provider_checksum_verified"]
            )
            self.assertTrue(report["readme_binding"]["provider_checksum_verified"])

    def test_every_member_of_repeated_pcm_group_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory), duplicate_pcm=True)
            report = self.audit(paths)
            self.assertEqual(
                2, report["observed"]["duplicate_pcm_file_count_excluded"]
            )
            self.assertEqual(
                2,
                report["conservative_reference_boundary"][
                    "eligible_audio_file_count"
                ],
            )

    def test_base_corpus_metadata_may_cover_unused_speakers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            with paths["speaker_info"].open("a", encoding="utf-8") as target:
                target.write("003 32 F Irish West\n")
            self.refresh_binding(
                paths, "supporting_artifacts.speaker_info", paths["speaker_info"]
            )
            rules = json.loads(paths["rules"].read_text(encoding="utf-8"))
            rules["expected"]["speaker_metadata_row_count"] = 3
            paths["rules"].write_text(json.dumps(rules), encoding="utf-8")
            report = self.audit(paths)
            self.assertEqual(
                ["p003"],
                report["observed"]["speaker_metadata_ids_absent_from_audio"],
            )

    def test_future_cap_domain_separator_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            rules = json.loads(paths["rules"].read_text(encoding="utf-8"))
            rules["future_group_cap"]["ranking_prefix"] = "changed\0"
            paths["rules"].write_text(json.dumps(rules), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "ranking rule differs"):
                self.audit(paths)

    def test_transcript_and_audio_identities_must_match(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            replacement = Path(directory) / "replacement.zip"
            with zipfile.ZipFile(paths["transcripts"]) as source, zipfile.ZipFile(
                replacement, "w", compression=zipfile.ZIP_DEFLATED
            ) as target:
                for info in source.infolist():
                    name = info.filename.replace("p002_002", "p002_003")
                    target.writestr(name, source.read(info))
            replacement.replace(paths["transcripts"])
            self.refresh_binding(
                paths, "supporting_artifacts.transcripts", paths["transcripts"]
            )
            with self.assertRaisesRegex(ValueError, "transcript/audio"):
                self.audit(paths)

    def test_audio_binding_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            rules = json.loads(paths["rules"].read_text(encoding="utf-8"))
            rules["artifact"]["local_sha256"] = "0" * 64
            paths["rules"].write_text(json.dumps(rules), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "audio byte binding differs"):
                self.audit(paths)

    def test_provider_checksum_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            rules = json.loads(paths["rules"].read_text(encoding="utf-8"))
            rules["metadata_artifact"]["provider_checksum"] = "md5:" + "0" * 32
            paths["rules"].write_text(json.dumps(rules), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "log provider checksum differs"):
                self.audit(paths)


if __name__ == "__main__":
    unittest.main()
