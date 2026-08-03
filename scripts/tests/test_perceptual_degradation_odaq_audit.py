from __future__ import annotations

import importlib.util
import io
import json
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-perceptual-degradation-odaq.py"
AUDIT_PATH = (
    ROOT
    / "research"
    / "toolchains"
    / "evidence"
    / "perceptual-degradation-odaq-score-blind-audit-20260803-001.json"
)
PLAN_PATH = (
    ROOT
    / "benchmarks"
    / "perceptual-degradation-v1"
    / "public-development-acquisition-plan.json"
)
SPEC = importlib.util.spec_from_file_location("odaq_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


HEADER = (
    ";content;original file name;source;author;license;original fs / depth;"
    "original coding;original format;current format;duration (s);notes\n"
)


def record() -> dict:
    return {
        "id": MODULE.RECORD_ID,
        "doi": MODULE.RECORD_DOI,
        "metadata": {"publication_date": "2023-12-20", "title": "ODAQ"},
        "files": [
            {
                "key": MODULE.ARCHIVE_KEY,
                "size": MODULE.ARCHIVE_BYTES,
                "checksum": MODULE.ARCHIVE_CHECKSUM,
                "links": {"self": "https://example.test/ODAQ.zip"},
            }
        ],
    }


def archive_bytes(*, duplicate_reference: bool = False) -> bytes:
    payload = io.BytesIO()
    rows = [
        (
            "clean.wav;music;clean.wav;https://example.test/clean;Author;"
            "https://creativecommons.org/licenses/by/4.0/;48 kHz / 24 bit;"
            "PCM;stereo;stereo PCM;10;test"
        ),
        (
            "lossy.wav;music;lossy.m4a;https://example.test/lossy;Author;"
            "http://creativecommons.org/publicdomain/zero/1.0/;44.1 kHz;"
            "AAC LC 256 kbs;stereo;stereo PCM;10;test"
        ),
        (
            "noncommercial.wav;speech;noncommercial.wav;https://example.test/nc;"
            "Author;https://creativecommons.org/licenses/by-nc/4.0/;48 kHz;"
            "PCM;stereo;stereo PCM;10;test"
        ),
    ]
    with zipfile.ZipFile(payload, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            MODULE.LICENSE_MEMBER,
            HEADER + "\n".join(rows) + "\n[1] citation;;;;;;;;;;;\n",
        )
        archive.writestr(
            MODULE.DISCLAIMER_MEMBER,
            "Processed audio inherits the licence of the original file.",
        )
        archive.writestr(MODULE.SCORE_MEMBER, "scores must remain unopened")
        for folder in ("TM_clean", "SH_lossy", "DE_noncommercial"):
            prefix = f"{MODULE.LISTENING_PREFIX}{folder}/"
            archive.writestr(prefix + "reference.wav", b"reference")
            archive.writestr(prefix + "condition.wav", b"condition")
            if duplicate_reference and folder == "TM_clean":
                archive.writestr(prefix + "nested/reference.wav", b"duplicate")
    return payload.getvalue()


class OdaqAuditTest(unittest.TestCase):
    def test_committed_evidence_remains_score_blind_and_fail_closed(self) -> None:
        audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
        plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        self.assertEqual([], MODULE.validate_frozen_evidence(audit, plan))
        self.assertEqual(
            MODULE.sha256_bytes(AUDIT_PATH.read_bytes()),
            plan["audit_binding"]["sha256"],
        )

    def test_audit_excludes_lossy_origin_and_noncommercial_source(self) -> None:
        report = MODULE.audit_archive(record(), io.BytesIO(archive_bytes()))
        self.assertFalse(report["read_boundary"]["score_member_opened"])
        self.assertFalse(report["read_boundary"]["audio_member_opened"])
        self.assertEqual(1, report["observed"]["eligible_listening_group_count"])
        by_id = {item["folder_id"]: item for item in report["listening_groups"]}
        self.assertTrue(by_id["TM_clean"]["development_eligible"])
        self.assertEqual(
            ["original_source_was_lossy_coded"],
            by_id["SH_lossy"]["exclusion_reasons"],
        )
        self.assertEqual(
            ["licence_outside_cc_by_or_cc0_scope"],
            by_id["DE_noncommercial"]["exclusion_reasons"],
        )

    def test_plan_remains_fail_closed(self) -> None:
        report = MODULE.audit_archive(record(), io.BytesIO(archive_bytes()))
        plan = MODULE.acquisition_plan(report, "a" * 64)
        self.assertFalse(plan["access_boundary"]["audio_download_authorized"])
        self.assertFalse(
            plan["access_boundary"]["listening_score_access_authorized"]
        )
        self.assertFalse(
            plan["access_boundary"]["perceptual_metric_execution_authorized"]
        )
        self.assertEqual(["TM_clean"], plan["selection"]["eligible_folder_ids"])
        self.assertEqual([], MODULE.validate_frozen_evidence(report, plan))

    def test_archive_binding_is_enforced(self) -> None:
        changed = json.loads(json.dumps(record()))
        changed["files"][0]["checksum"] = "md5:" + "0" * 32
        with self.assertRaisesRegex(ValueError, "checksum differs"):
            MODULE.audit_archive(changed, io.BytesIO(archive_bytes()))

    def test_missing_reference_is_rejected(self) -> None:
        payload = io.BytesIO(archive_bytes())
        rewritten = io.BytesIO()
        with zipfile.ZipFile(payload) as source, zipfile.ZipFile(
            rewritten, "w", compression=zipfile.ZIP_DEFLATED
        ) as target:
            for info in source.infolist():
                if info.filename.endswith("TM_clean/reference.wav"):
                    continue
                target.writestr(info.filename, source.read(info))
        with self.assertRaisesRegex(ValueError, "one reference"):
            MODULE.audit_archive(record(), io.BytesIO(rewritten.getvalue()))


if __name__ == "__main__":
    unittest.main()
