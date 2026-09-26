from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import tarfile
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-tinysol.py"
SPEC = importlib.util.spec_from_file_location("tinysol_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


COLUMNS = [
    "Path",
    "Fold",
    "Family",
    "Instrument (abbr.)",
    "Instrument (in full)",
    "Technique (abbr.)",
    "Technique (in full)",
    "Pitch",
    "Pitch ID",
    "Dynamics",
    "Dynamics ID",
    "Instance ID",
    "String ID (if applicable)",
    "Needed digital retuning",
]


def pcm_wave(seed: int) -> bytes:
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(44100)
        target.writeframes(bytes([seed, 0, seed + 1, 0]))
    return output.getvalue()


class TinySolAuditTest(unittest.TestCase):
    def test_observed_instance_five_maps_to_alt5(self) -> None:
        self.assertEqual(
            "alt5",
            MODULE.expected_instance_token(
                {"Instance ID": "5", "String ID (if applicable)": ""}
            ),
        )

    def test_string_id_is_one_based_while_instance_id_is_zero_based(self) -> None:
        self.assertEqual(
            "4c",
            MODULE.expected_instance_token(
                {"Instance ID": "3", "String ID (if applicable)": "4.0"}
            ),
        )

    def make_inputs(self, root: Path) -> tuple[Path, Path, Path]:
        metadata = root / "metadata.csv"
        rows = [
            {
                "Path": "Brass/Bass_Tuba/ordinario/BTb-ord-A1-pp-N-N.wav",
                "Fold": "0",
                "Family": "Brass",
                "Instrument (abbr.)": "BTb",
                "Instrument (in full)": "Bass Tuba",
                "Technique (abbr.)": "ord",
                "Technique (in full)": "ordinario",
                "Pitch": "A1",
                "Pitch ID": "33",
                "Dynamics": "pp",
                "Dynamics ID": "0",
                "Instance ID": "0",
                "String ID (if applicable)": "",
                "Needed digital retuning": "FALSE",
            },
            {
                "Path": "Brass/Bass_Tuba/ordinario/BTb-ord-A#1-pp-N-T10u.wav",
                "Fold": "1",
                "Family": "Brass",
                "Instrument (abbr.)": "BTb",
                "Instrument (in full)": "Bass Tuba",
                "Technique (abbr.)": "ord",
                "Technique (in full)": "ordinario",
                "Pitch": "A#1",
                "Pitch ID": "34",
                "Dynamics": "pp",
                "Dynamics ID": "0",
                "Instance ID": "0",
                "String ID (if applicable)": "",
                "Needed digital retuning": "TRUE",
            },
            {
                "Path": "Brass/Bass_Tuba/ordinario/BTb-ord-B1-pp-N-T10u_R100u.wav",
                "Fold": "2",
                "Family": "Brass",
                "Instrument (abbr.)": "BTb",
                "Instrument (in full)": "Bass Tuba",
                "Technique (abbr.)": "ord",
                "Technique (in full)": "ordinario",
                "Pitch": "B1",
                "Pitch ID": "35",
                "Dynamics": "pp",
                "Dynamics ID": "0",
                "Instance ID": "0",
                "String ID (if applicable)": "",
                "Needed digital retuning": "TRUE",
            },
        ]
        with metadata.open("w", newline="", encoding="utf-8") as target:
            writer = csv.DictWriter(target, fieldnames=COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        audio = root / "audio.tar.gz"
        with tarfile.open(audio, "w:gz") as archive:
            for seed, row in enumerate(rows, start=1):
                payload = pcm_wave(seed)
                member = tarfile.TarInfo(row["Path"])
                member.size = len(payload)
                archive.addfile(member, BytesIO(payload))

        def artifact(path: Path) -> dict[str, object]:
            return {
                "filename": path.name,
                "bytes": path.stat().st_size,
                "provider_checksum": "md5:"
                + hashlib.md5(
                    path.read_bytes(), usedforsecurity=False
                ).hexdigest(),
            }

        rules = root / "rules.json"
        rules.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "state": "source_identity_rules_not_allocation",
                    "source_id": "tinysol_6_0",
                    "record_id": 3685367,
                    "record_version": "6.0",
                    "audio_generated": False,
                    "scores_opened": False,
                    "selection_authorized": False,
                    "artifacts": {
                        "audio": artifact(audio),
                        "metadata": artifact(metadata),
                    },
                    "expected": {
                        "ancillary_regular_members": [],
                        "archive_member_root_prefix": "",
                        "audio_format": {
                            "bits_per_sample": 16,
                            "channel_count": 1,
                            "format_tag": 1,
                            "sample_format": "signed_integer_pcm",
                            "sample_rate_hz": 44100,
                        },
                        "directory_member_count": 0,
                        "conservative_partition_group_count": 1,
                        "digitally_retuned_row_count": 2,
                        "family_counts": {"Brass": 3},
                        "fold_counts": {"0": 1, "1": 1, "2": 1},
                        "instruments": [
                            {
                                "abbreviation": "BTb",
                                "family": "Brass",
                                "folder": "Bass_Tuba",
                                "full_name": "Bass Tuba",
                                "row_count": 3,
                            }
                        ],
                        "metadata_columns": COLUMNS,
                        "metadata_row_count": 3,
                        "natural_reference_row_count": 1,
                        "resampled_and_tuned_row_count": 1,
                        "resampled_row_count": 1,
                        "source_group_count": 1,
                        "tuning_only_row_count": 1,
                    },
                }
            ),
            encoding="utf-8",
        )
        return audio, metadata, rules

    def update_artifact_binding(
        self, rules: Path, kind: str, artifact_path: Path
    ) -> None:
        value = json.loads(rules.read_text(encoding="utf-8"))
        value["artifacts"][kind]["bytes"] = artifact_path.stat().st_size
        value["artifacts"][kind]["provider_checksum"] = "md5:" + hashlib.md5(
            artifact_path.read_bytes(), usedforsecurity=False
        ).hexdigest()
        rules.write_text(json.dumps(value), encoding="utf-8")

    def test_audit_keeps_one_conservative_partition_group(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio, metadata, rules = self.make_inputs(Path(directory))
            report = MODULE.audit(audio, metadata, rules)
            self.assertEqual(3, report["observed"]["archive_audio_file_count"])
            self.assertEqual(
                1,
                report["conservative_reference_boundary"][
                    "eligible_audio_file_count"
                ],
            )
            self.assertEqual(
                1, report["conservative_reference_boundary"]["eligible_group_count"]
            )
            self.assertEqual(
                {"natural": 1, "resampled_and_tuned": 1, "tuning_only": 1},
                report["observed"]["retuning_class_counts"],
            )
            self.assertEqual(1, report["observed"]["resampled_parent_mapping_count"])
            self.assertEqual(
                [
                    {
                        "derived_archive_member_id": (
                            "Brass/Bass_Tuba/ordinario/"
                            "BTb-ord-B1-pp-N-T10u_R100u.wav"
                        ),
                        "parent_archive_member_id": (
                            "Brass/Bass_Tuba/ordinario/"
                            "BTb-ord-A#1-pp-N-T10u.wav"
                        ),
                    }
                ],
                report["observed"]["resampled_parent_mappings"],
            )
            self.assertTrue(
                report["archive_bindings"]["audio"]["gzip_tar_stream_verified"]
            )
            self.assertTrue(report["paths_redacted"])
            self.assertFalse(report["selection_authorized"])

    def test_archive_provider_binding_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio, metadata, rules = self.make_inputs(Path(directory))
            value = json.loads(rules.read_text(encoding="utf-8"))
            value["artifacts"]["audio"]["provider_checksum"] = "md5:" + "0" * 32
            rules.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "audio artifact binding differs"):
                MODULE.audit(audio, metadata, rules)

    def test_retuning_flag_must_match_filename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio, metadata, rules = self.make_inputs(Path(directory))
            text = metadata.read_text(encoding="utf-8")
            metadata.write_text(
                text.replace(",FALSE\n", ",TRUE\n", 1),
                encoding="utf-8",
            )
            self.update_artifact_binding(rules, "metadata", metadata)
            with self.assertRaisesRegex(
                ValueError, "retuning flag and filename differ"
            ):
                MODULE.audit(audio, metadata, rules)


if __name__ == "__main__":
    unittest.main()
