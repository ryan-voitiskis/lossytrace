from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import tempfile
import unittest
import wave
import zipfile
from decimal import Decimal, getcontext
from io import BytesIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-audio-integrity-v2-rwc.py"
SPEC = importlib.util.spec_from_file_location("rwc_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COLLECTION_ROWS = {
    "C": ("RWC_C023A", "23A", "Artist A"),
    "G": ("RWC_G058A", "58A", "Artist A Alias"),
    "J": ("RWC_J001", "1", "Excluded Artist"),
    "P": ("RWC_P001", "1", "Artist B"),
    "R": ("RWC_R001", "1", "Artist C"),
}


def pcm_wave(seed: int) -> tuple[bytes, int]:
    frame_count = 8
    frames = b"".join(
        bytes((seed + index, 0, seed + index + 1, 0))
        for index in range(frame_count)
    )
    output = BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(2)
        target.setframerate(44100)
        target.writeframes(frames)
    return output.getvalue(), frame_count


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def provider_binding(path: Path) -> dict[str, object]:
    return {
        "filename": path.name,
        "url": f"https://example.invalid/{path.name}",
        "bytes": path.stat().st_size,
        "provider_checksum": f"md5:{md5(path)}",
        "local_sha256": sha256(path),
    }


class RwcAuditTest(unittest.TestCase):
    def make_inputs(
        self, root: Path, duplicate_pcm: bool = False
    ) -> dict[str, object]:
        getcontext().prec = 80
        audio_paths: list[Path] = []
        frame_counts: dict[str, int] = {}
        seeds = {"C": 1, "G": 20, "J": 40, "P": 60, "R": 80}
        if duplicate_pcm:
            seeds["P"] = seeds["C"]
        for collection, (rwc_id, _piece, _artist) in COLLECTION_ROWS.items():
            path = root / f"RWC-{collection}.zip"
            payload, frame_count = pcm_wave(seeds[collection])
            frame_counts[rwc_id] = frame_count
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as target:
                target.writestr(f"RWC-{collection}/", b"")
                target.writestr(f"RWC-{collection}/{rwc_id}.wav", payload)
            audio_paths.append(path)

        metadata = root / "metadata.csv"
        columns = [
            "RWCID",
            "CollID",
            "PieceNo",
            "CDNo",
            "TrackNo",
            "Title",
            "Artist",
            "audio_start",
            "audio_end",
            "duration",
        ]
        with metadata.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, columns, delimiter=";")
            writer.writeheader()
            for collection, (rwc_id, piece, artist) in COLLECTION_ROWS.items():
                duration = Decimal(frame_counts[rwc_id]) / Decimal(44100)
                writer.writerow(
                    {
                        "RWCID": rwc_id,
                        "CollID": collection,
                        "PieceNo": piece,
                        "CDNo": "1",
                        "TrackNo": "1",
                        "Title": f"Fixture {collection}",
                        "Artist": artist,
                        "audio_start": "0",
                        "audio_end": format(duration, "f"),
                        "duration": format(duration, "f"),
                    }
                )

        family_rules = root / "family-rules.json"
        family_rules.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "state": "source_identity_rules_not_allocation",
                    "source_id": "rwc_music_v2_2026",
                    "metadata_revision": "fixture-revision",
                    "metadata_sha256": sha256(metadata),
                    "audio_generated": False,
                    "scores_opened": False,
                    "selection_authorized": False,
                    "eligibility_exclusions": [
                        {
                            "rule_id": "exclude-jazz-fixture",
                            "collection_id": "J",
                            "piece_number_minimum": 1,
                            "piece_number_maximum": 1,
                        }
                    ],
                    "family_merges": [
                        {
                            "family_id": "artist-a",
                            "artist_labels": ["Artist A", "Artist A Alias"],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        metadata_evidence = root / "metadata-evidence.json"
        metadata_evidence.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "state": "source_metadata_identity_evidence_only",
                    "source_id": "rwc_music_v2_2026",
                    "metadata_binding": {
                        "revision": "fixture-revision",
                        "sha256": sha256(metadata),
                    },
                    "conservative_group_boundary": {"eligible_group_count": 3},
                }
            ),
            encoding="utf-8",
        )
        changelog = root / "changelog.txt"
        changelog.write_text("RWC v2 fixture changelog\n", encoding="utf-8")

        rules = root / "rules.json"
        duplicate_group_count = 1 if duplicate_pcm else 0
        duplicate_excess = 1 if duplicate_pcm else 0
        duplicate_excluded = 2 if duplicate_pcm else 0
        rules.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "state": "source_identity_rules_not_allocation",
                    "source_id": "rwc_music_v2_2026",
                    "audio_generated": False,
                    "scores_opened": False,
                    "selection_authorized": False,
                    "artifacts": [provider_binding(path) for path in audio_paths],
                    "changelog_artifact": provider_binding(changelog),
                    "metadata_binding": {
                        "filename": metadata.name,
                        "bytes": metadata.stat().st_size,
                        "revision": "fixture-revision",
                        "sha256": sha256(metadata),
                    },
                    "artist_family_rules_binding": {
                        "filename": family_rules.name,
                        "sha256": sha256(family_rules),
                    },
                    "metadata_identity_evidence_binding": {
                        "filename": metadata_evidence.name,
                        "sha256": sha256(metadata_evidence),
                    },
                    "provider_record": {"doi": "fixture"},
                    "processing_chain": "fixture master-track processing boundary",
                    "expected": {
                        "metadata_row_count": 5,
                        "collection_audio_file_counts": {
                            collection: 1 for collection in MODULE.COLLECTION_IDS
                        },
                        "audio_format": {
                            "format_tag": 1,
                            "sample_format": "signed_integer_pcm",
                            "channel_count": 2,
                            "sample_rate_hz": 44100,
                            "bits_per_sample": 16,
                        },
                        "maximum_duration_error_samples": "0.000001",
                        "duplicate_pcm_digest_group_count": duplicate_group_count,
                        "duplicate_pcm_file_count_excess": duplicate_excess,
                        "duplicate_pcm_file_count_excluded": duplicate_excluded,
                        "known_instrumentation_variation_row_count": 1,
                        "metadata_artist_family_count": 3,
                        "source_group_count": 2 if duplicate_pcm else 3,
                    },
                }
            ),
            encoding="utf-8",
        )
        return {
            "audio": audio_paths,
            "changelog": changelog,
            "metadata": metadata,
            "family_rules": family_rules,
            "metadata_evidence": metadata_evidence,
            "rules": rules,
        }

    def audit(self, paths: dict[str, object]) -> dict[str, object]:
        return MODULE.audit(
            paths["audio"],
            paths["changelog"],
            paths["metadata"],
            paths["family_rules"],
            paths["metadata_evidence"],
            paths["rules"],
        )

    def test_audit_binds_all_archives_without_allocating_audio(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            report = self.audit(paths)
            self.assertEqual("source_identity_evidence_only", report["state"])
            self.assertEqual(5, report["observed"]["audio_file_count"])
            self.assertEqual(
                3,
                report["conservative_reference_boundary"]["eligible_group_count"],
            )
            self.assertEqual(
                4,
                report["conservative_reference_boundary"]["eligible_audio_file_count"],
            )
            self.assertFalse(report["selection_authorized"])
            self.assertEqual(5, len(report["archive_bindings"]))
            self.assertTrue(
                all(
                    binding["provider_checksum_verified"]
                    and binding["zip_crc_verified"]
                    for binding in report["archive_bindings"].values()
                )
            )

    def test_complete_replays_are_identical(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            self.assertEqual(self.audit(paths), self.audit(paths))

    def test_repeated_pcm_members_are_excluded_and_groups_recomputed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory), duplicate_pcm=True)
            report = self.audit(paths)
            self.assertEqual(2, report["observed"]["duplicate_pcm_file_count_excluded"])
            self.assertEqual(
                [["RWC_C023A", "RWC_P001"]],
                report["observed"]["duplicate_pcm_rwc_id_groups"],
            )
            self.assertEqual(
                2,
                report["conservative_reference_boundary"]["eligible_group_count"],
            )
            self.assertEqual(
                2,
                report["conservative_reference_boundary"]["eligible_audio_file_count"],
            )

    def test_audio_identity_must_reconcile_to_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            archive = next(path for path in paths["audio"] if path.name == "RWC-R.zip")
            replacement = Path(directory) / "replacement.zip"
            payload, _frames = pcm_wave(80)
            with zipfile.ZipFile(
                replacement, "w", compression=zipfile.ZIP_DEFLATED
            ) as target:
                target.writestr("RWC-R/", b"")
                target.writestr("RWC-R/RWC_R002.wav", payload)
            replacement.replace(archive)
            rules = json.loads(paths["rules"].read_text(encoding="utf-8"))
            rules["artifacts"] = [
                provider_binding(path) for path in paths["audio"]
            ]
            paths["rules"].write_text(json.dumps(rules), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "absent from metadata"):
                self.audit(paths)

    def test_metadata_duration_must_match_decoded_frame_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            rows: list[dict[str, str]]
            with paths["metadata"].open(encoding="utf-8", newline="") as source:
                reader = csv.DictReader(source, delimiter=";")
                columns = reader.fieldnames
                rows = list(reader)
            assert columns is not None
            rows[0]["duration"] = str(Decimal(rows[0]["duration"]) + Decimal("0.1"))
            rows[0]["audio_end"] = rows[0]["duration"]
            with paths["metadata"].open("w", encoding="utf-8", newline="") as target:
                writer = csv.DictWriter(target, columns, delimiter=";")
                writer.writeheader()
                writer.writerows(rows)
            self.refresh_metadata_bindings(paths)
            with self.assertRaisesRegex(ValueError, "duration differs"):
                self.audit(paths)

    def refresh_metadata_bindings(self, paths: dict[str, object]) -> None:
        metadata_sha256 = sha256(paths["metadata"])
        family_rules = json.loads(paths["family_rules"].read_text(encoding="utf-8"))
        family_rules["metadata_sha256"] = metadata_sha256
        paths["family_rules"].write_text(json.dumps(family_rules), encoding="utf-8")
        metadata_evidence = json.loads(
            paths["metadata_evidence"].read_text(encoding="utf-8")
        )
        metadata_evidence["metadata_binding"]["sha256"] = metadata_sha256
        paths["metadata_evidence"].write_text(
            json.dumps(metadata_evidence), encoding="utf-8"
        )
        rules = json.loads(paths["rules"].read_text(encoding="utf-8"))
        rules["metadata_binding"]["bytes"] = paths["metadata"].stat().st_size
        rules["metadata_binding"]["sha256"] = metadata_sha256
        rules["artist_family_rules_binding"]["sha256"] = sha256(
            paths["family_rules"]
        )
        rules["metadata_identity_evidence_binding"]["sha256"] = sha256(
            paths["metadata_evidence"]
        )
        paths["rules"].write_text(json.dumps(rules), encoding="utf-8")

    def test_provider_checksum_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            paths = self.make_inputs(Path(directory))
            rules = json.loads(paths["rules"].read_text(encoding="utf-8"))
            rules["artifacts"][0]["provider_checksum"] = "md5:" + "0" * 32
            paths["rules"].write_text(json.dumps(rules), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "provider checksum differs"):
                self.audit(paths)


if __name__ == "__main__":
    unittest.main()
