from __future__ import annotations

import importlib.util
import io
import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/freeze-perceptual-degradation-odaq-reference-acquisition.py"
PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-acquisition-freeze.json"
)
ATTRIBUTION = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-odaq-attribution-audit-20260804-001.json"
)
FALLBACK = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "permissive-listening-source-fallback-plan.json"
)
SPEC = importlib.util.spec_from_file_location("odaq_reference_freeze", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def plan() -> dict:
    return load(PLAN)


def provider_record() -> dict:
    return {
        "id": MODULE.BASE.RECORD_ID,
        "doi": MODULE.BASE.RECORD_DOI,
        "metadata": {
            "publication_date": "2023-12-30",
            "title": "ODAQ: OPEN DATASET OF AUDIO QUALITY",
        },
        "files": [
            {
                "key": MODULE.BASE.ARCHIVE_KEY,
                "size": MODULE.BASE.ARCHIVE_BYTES,
                "checksum": MODULE.BASE.ARCHIVE_CHECKSUM,
                "links": {"self": "https://example.test/ODAQ.zip"},
            }
        ],
    }


class OdaqReferenceAcquisitionFreezeTest(unittest.TestCase):
    def test_committed_plan_validates(self) -> None:
        self.assertEqual([], MODULE.validate(plan()))

    def test_synthetic_inventory_selects_reference_members_only(self) -> None:
        attribution = load(ATTRIBUTION)
        archive_bytes = io.BytesIO()
        with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
            for group in attribution["listening_groups"]:
                folder = group["folder_id"]
                archive.writestr(MODULE.reference_member_name(folder), b"reference")
                archive.writestr(
                    f"{MODULE.BASE.LISTENING_PREFIX}{folder}/processed.wav",
                    b"processed",
                )
            archive.writestr(MODULE.BASE.SCORE_MEMBER, b"score")
        archive_bytes.seek(0)
        value = MODULE.build_plan(
            provider_record(),
            archive_bytes,
            load(FALLBACK),
            attribution,
        )
        self.assertEqual(16, len(value["references"]))
        self.assertEqual(
            {"reference.wav"},
            {item["member_basename"] for item in value["references"]},
        )
        self.assertFalse(value["read_boundary"]["audio_member_opened"])
        self.assertFalse(value["read_boundary"]["processed_condition_opened"])
        self.assertFalse(value["read_boundary"]["score_member_opened"])
        self.assertEqual([], MODULE.validate(value))

    def test_execution_cannot_be_authorized_by_freeze(self) -> None:
        value = plan()
        value["execution_boundary"]["source_track_selected"] = True
        value["execution_boundary"]["reference_audio_acquisition_authorized"] = True
        errors = MODULE.validate(value)
        self.assertIn(
            "execution boundary must remain false: source_track_selected", errors
        )
        self.assertIn(
            "execution boundary must remain false: reference_audio_acquisition_authorized",
            errors,
        )

    def test_processed_member_cannot_replace_reference(self) -> None:
        value = plan()
        value["references"][0]["member_basename"] = "processed.wav"
        errors = MODULE.validate(value)
        self.assertIn(
            f"non-reference member selected: {value['references'][0]['folder_id']}",
            errors,
        )

    def test_totals_and_identity_cardinality_are_bound(self) -> None:
        value = plan()
        value["selection"]["total_compressed_bytes"] += 1
        value["references"][1]["folder_id"] = value["references"][0]["folder_id"]
        errors = MODULE.validate(value)
        self.assertIn("compressed-byte total differs", errors)
        self.assertIn("reference identity cardinality differs", errors)


if __name__ == "__main__":
    unittest.main()
