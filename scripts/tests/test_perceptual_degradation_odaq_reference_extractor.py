from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/acquire-perceptual-degradation-odaq-references.py"
FREEZE = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-acquisition-freeze.json"
)
PREPARATION_PLAN = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "odaq-reference-extractor-preparation-plan.json"
)
SPEC = importlib.util.spec_from_file_location("odaq_reference_extractor", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def pcm_wav(seed: int) -> bytes:
    value = io.BytesIO()
    with wave.open(value, "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(48_000)
        frames = bytearray()
        for index in range(256):
            sample = ((index * (seed + 1)) % 2000) - 1000
            frames.extend(int(sample).to_bytes(2, "little", signed=True) * 2)
        output.writeframes(bytes(frames))
    return value.getvalue()


def fixture() -> tuple[dict, bytes]:
    groups = [
        ("LP_fixture-a", "fixture-a"),
        ("DE_fixture-b", "fixture-b"),
    ]
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        for index, (folder_id, _) in enumerate(groups):
            archive.writestr(MODULE.member_name(folder_id), pcm_wav(index))
            archive.writestr(
                f"{MODULE.BASE.LISTENING_PREFIX}{folder_id}/processed.wav",
                pcm_wav(index + 10),
            )
        archive.writestr(MODULE.BASE.SCORE_MEMBER, b"scores-closed")
    encoded = archive_bytes.getvalue()
    references = []
    with zipfile.ZipFile(io.BytesIO(encoded)) as archive:
        for folder_id, source_id in groups:
            info = archive.getinfo(MODULE.member_name(folder_id))
            references.append(
                {
                    "folder_id": folder_id,
                    "source_id": source_id,
                    **MODULE.zip_binding(info),
                    "licence_record_ids": [f"licence-{source_id}"],
                    "artifact_family_code": folder_id.split("_", 1)[0],
                }
            )
    return {"references": references}, encoded


class OdaqReferenceExtractorTest(unittest.TestCase):
    def test_committed_preparation_plan_validates(self) -> None:
        plan = json.loads(PREPARATION_PLAN.read_text(encoding="utf-8"))
        self.assertEqual([], MODULE.validate_preparation_plan(plan))

    def test_preparation_plan_cannot_authorize_live_acquisition(self) -> None:
        plan = json.loads(PREPARATION_PLAN.read_text(encoding="utf-8"))
        plan["access_boundary"]["provider_audio_acquisition_authorized"] = True
        plan["decision"]["live_authorization_present"] = True
        errors = MODULE.validate_preparation_plan(plan)
        self.assertIn(
            "access boundary must remain false: provider_audio_acquisition_authorized",
            errors,
        )
        self.assertIn(
            "extractor decision boundary must remain false: live_authorization_present",
            errors,
        )

    def test_committed_freeze_validates_and_remains_unauthorized(self) -> None:
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        self.assertEqual([], MODULE.validate_freeze(freeze))
        self.assertEqual(
            MODULE.REFERENCE_FREEZE_SHA256,
            MODULE.sha256_file(FREEZE),
        )
        errors = MODULE.validate_live_authorization(
            freeze, freeze, MODULE.sha256_file(FREEZE)
        )
        self.assertIn("reference acquisition is not authorized", errors)
        self.assertIn("responsible-human source choice is absent", errors)
        self.assertIn("physical playback declaration is absent", errors)

    def test_freeze_boundary_keys_are_exact(self) -> None:
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        freeze["execution_boundary"].pop("source_track_selected")
        freeze["claim_boundary"]["invented_claim"] = False
        errors = MODULE.validate_freeze(freeze)
        self.assertIn("reference freeze execution boundary keys differ", errors)
        self.assertIn("reference freeze claim boundary keys differ", errors)

    def test_live_command_refuses_before_provider_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            original = MODULE.BASE.fetch_record
            MODULE.BASE.fetch_record = lambda: self.fail("provider access occurred")
            try:
                with self.assertRaisesRegex(SystemExit, "not authorized"):
                    MODULE.command_acquire(
                        argparse.Namespace(
                            freeze=FREEZE,
                            authorization=FREEZE,
                            output_root=Path(temporary) / "private",
                        )
                    )
            finally:
                MODULE.BASE.fetch_record = original

    def test_uncommitted_authorization_refuses_before_provider_access(self) -> None:
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        authorization = {
            "schema_version": 1,
            "state": "reference_audio_acquisition_authorized",
            "parent_freeze_sha256": MODULE.sha256_file(FREEZE),
            "source_track": "permissive_odaq_cc_by_cc0",
            "responsible_human_source_choice_present": True,
            "physical_playback_declaration_present": True,
            "reference_audio_acquisition_authorized": True,
            "processed_condition_access_authorized": False,
            "listening_score_access_authorized": False,
            "stimulus_generation_authorized": False,
            "perceptual_metric_execution_authorized": False,
            "listener_response_collection_authorized": False,
            "provider": freeze["provider"],
            "references": freeze["references"],
        }
        self.assertEqual(
            [],
            MODULE.validate_live_authorization(
                authorization, freeze, MODULE.sha256_file(FREEZE)
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            authorization_path = Path(temporary) / "authorization.json"
            authorization_path.write_text(json.dumps(authorization), encoding="utf-8")
            original = MODULE.BASE.fetch_record
            MODULE.BASE.fetch_record = lambda: self.fail("provider access occurred")
            try:
                with self.assertRaisesRegex(SystemExit, "committed and clean"):
                    MODULE.command_acquire(
                        argparse.Namespace(
                            freeze=FREEZE,
                            authorization=authorization_path,
                            output_root=Path(temporary) / "private",
                        )
                    )
            finally:
                MODULE.BASE.fetch_record = original

    def test_range_budget_is_bounded_but_covers_frozen_references(self) -> None:
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        compressed = freeze["selection"]["total_compressed_bytes"]
        maximum_rounding = (
            2 * MODULE.LIVE_BLOCK_BYTES * len(freeze["references"])
        )
        self.assertGreater(
            MODULE.LIVE_MAXIMUM_RANGE_BYTES,
            compressed + maximum_rounding,
        )
        self.assertLess(
            MODULE.LIVE_MAXIMUM_RANGE_BYTES,
            freeze["provider"]["archive_bytes"],
        )

    def test_synthetic_extraction_is_atomic_opaque_and_resumable(self) -> None:
        plan, encoded = fixture()
        plan_sha256 = "a" * 64
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "private"
            state = MODULE.extract_references(
                plan=plan,
                plan_sha256=plan_sha256,
                source=io.BytesIO(encoded),
                output_root=root,
                minimum_free_bytes=0,
                disk_free=lambda _: 10**9,
            )
            self.assertEqual("reference_acquisition_complete", state["state"])
            self.assertEqual(2, state["completed_count"])
            self.assertFalse(state["processed_condition_opened"])
            self.assertFalse(state["listening_score_opened"])
            files = sorted((root / "sources").iterdir())
            self.assertEqual(2, len(files))
            self.assertTrue(all(path.name.startswith("odaq-ref-") for path in files))
            self.assertFalse(any((root / ".partial").iterdir()))
            replay = MODULE.extract_references(
                plan=plan,
                plan_sha256=plan_sha256,
                source=io.BytesIO(encoded),
                output_root=root,
                minimum_free_bytes=0,
                disk_free=lambda _: 10**9,
            )
            self.assertEqual(state, replay)

    def test_zip_binding_mismatch_stops_before_member_write(self) -> None:
        plan, encoded = fixture()
        plan = copy.deepcopy(plan)
        plan["references"][0]["crc32"] = "00000000"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "private"
            with self.assertRaisesRegex(ValueError, "ZIP binding differs"):
                MODULE.extract_references(
                    plan=plan,
                    plan_sha256="b" * 64,
                    source=io.BytesIO(encoded),
                    output_root=root,
                    minimum_free_bytes=0,
                    disk_free=lambda _: 10**9,
                )
            self.assertEqual([], list((root / "sources").iterdir()))

    def test_disk_reserve_stops_before_member_write(self) -> None:
        plan, encoded = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "private"
            with self.assertRaisesRegex(ValueError, "cross disk reserve"):
                MODULE.extract_references(
                    plan=plan,
                    plan_sha256="c" * 64,
                    source=io.BytesIO(encoded),
                    output_root=root,
                    minimum_free_bytes=100,
                    disk_free=lambda _: 100,
                )
            self.assertEqual([], list((root / "sources").iterdir()))

    def test_corrupted_retained_member_stops_resume(self) -> None:
        plan, encoded = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "private"
            state = MODULE.extract_references(
                plan=plan,
                plan_sha256="d" * 64,
                source=io.BytesIO(encoded),
                output_root=root,
                minimum_free_bytes=0,
                disk_free=lambda _: 10**9,
            )
            retained = root / state["completed"][0]["relative_path"]
            retained.write_bytes(b"corrupt")
            with self.assertRaisesRegex(ValueError, "byte length differs"):
                MODULE.extract_references(
                    plan=plan,
                    plan_sha256="d" * 64,
                    source=io.BytesIO(encoded),
                    output_root=root,
                    minimum_free_bytes=0,
                    disk_free=lambda _: 10**9,
                )

    def test_tampered_resume_path_is_rejected_before_retained_access(self) -> None:
        plan, encoded = fixture()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "private"
            MODULE.extract_references(
                plan=plan,
                plan_sha256="f" * 64,
                source=io.BytesIO(encoded),
                output_root=root,
                minimum_free_bytes=0,
                disk_free=lambda _: 10**9,
            )
            state_path = root / "acquisition.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["completed"][0]["relative_path"] = "../outside.wav"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "journal differs: retained path"):
                MODULE.extract_references(
                    plan=plan,
                    plan_sha256="f" * 64,
                    source=io.BytesIO(encoded),
                    output_root=root,
                    minimum_free_bytes=0,
                    disk_free=lambda _: 10**9,
                )

    def test_repository_output_and_unsafe_identifier_are_rejected(self) -> None:
        plan, encoded = fixture()
        with self.assertRaisesRegex(ValueError, "outside the repository"):
            MODULE.extract_references(
                plan=plan,
                plan_sha256="e" * 64,
                source=io.BytesIO(encoded),
                output_root=ROOT / "forbidden-private-output",
                minimum_free_bytes=0,
            )
        with self.assertRaisesRegex(ValueError, "unsafe"):
            MODULE.member_name("../escape")


if __name__ == "__main__":
    unittest.main()
