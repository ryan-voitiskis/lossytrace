from __future__ import annotations

import csv
import importlib.util
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit-perceptual-degradation-odaq.py"
ATTRIBUTION_SCRIPT = (
    ROOT / "scripts" / "audit-perceptual-degradation-odaq-attribution.py"
)
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
ATTRIBUTION_SPEC = importlib.util.spec_from_file_location(
    "odaq_attribution_audit", ATTRIBUTION_SCRIPT
)
assert ATTRIBUTION_SPEC and ATTRIBUTION_SPEC.loader
ATTRIBUTION_MODULE = importlib.util.module_from_spec(ATTRIBUTION_SPEC)
sys.modules[ATTRIBUTION_SPEC.name] = ATTRIBUTION_MODULE
ATTRIBUTION_SPEC.loader.exec_module(ATTRIBUTION_MODULE)


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

    def test_attribution_audit_retains_required_cc_by_fields_only(self) -> None:
        prior = MODULE.audit_archive(record(), io.BytesIO(archive_bytes()))
        plan = MODULE.acquisition_plan(prior, "a" * 64)
        report = ATTRIBUTION_MODULE.audit_archive(
            record(), io.BytesIO(archive_bytes()), prior, plan
        )
        self.assertEqual([], ATTRIBUTION_MODULE.validate(report))
        self.assertEqual(1, report["selection"]["source_count"])
        self.assertEqual(1, report["selection"]["group_count"])
        licence = report["licence_records"][0]
        self.assertEqual("clean.wav", licence["title"])
        self.assertEqual("Author", licence["creator"])
        self.assertEqual("https://example.test/clean", licence["source_url"])
        self.assertEqual(
            "https://creativecommons.org/licenses/by/4.0/",
            licence["licence_url"],
        )
        self.assertTrue(licence["attribution_fields_complete"])
        self.assertTrue(licence["attribution_notice_ready"])
        group = report["listening_groups"][0]
        self.assertTrue(group["development_only"])
        self.assertFalse(group["actual_codec_condition"])
        self.assertFalse(group["final_validation_eligible"])
        self.assertFalse(report["audio_acquisition_authorized"])
        self.assertFalse(report["listening_score_access_authorized"])

    def test_attribution_audit_rejects_codec_or_final_overclaim(self) -> None:
        prior = MODULE.audit_archive(record(), io.BytesIO(archive_bytes()))
        plan = MODULE.acquisition_plan(prior, "a" * 64)
        report = ATTRIBUTION_MODULE.audit_archive(
            record(), io.BytesIO(archive_bytes()), prior, plan
        )
        report["listening_groups"][0]["actual_codec_condition"] = True
        report["listening_groups"][0]["final_validation_eligible"] = True
        errors = ATTRIBUTION_MODULE.validate(report)
        self.assertIn("ODAQ group must not be represented as actual codec audio", errors)
        self.assertIn("ODAQ group must remain outside final validation", errors)

    def test_attribution_placeholders_and_non_urls_are_incomplete(self) -> None:
        reader = csv.DictReader(
            io.StringIO(
                HEADER
                + "derived.wav;mix;n/a;Produced from the two rows above;Creator;"
                + "https://creativecommons.org/licenses/by/4.0/;48 kHz;PCM;"
                + "stereo;stereo PCM;10;test\n"
            ),
            delimiter=";",
        )
        attribution = ATTRIBUTION_MODULE.licence_record(next(reader))
        self.assertFalse(attribution["attribution_fields_complete"])
        self.assertFalse(attribution["attribution_notice_ready"])
        self.assertEqual(
            ["title", "source_url"], attribution["missing_attribution_fields"]
        )

    def test_attribution_resolves_explicit_preceding_source_dependencies(self) -> None:
        payload = HEADER + "\n".join(
            [
                "foreground.wav;speech;foreground.wav;https://example.test/fg;FG Creator;https://creativecommons.org/licenses/by/4.0/;48 kHz;PCM;mono;stereo PCM;10;test",
                "background.wav;music;background.wav;https://example.test/bg;BG Creator;https://creativecommons.org/publicdomain/zero/1.0/;48 kHz;PCM;stereo;stereo PCM;10;test",
                "derived.wav;mix;n/a;Produced using material detailed in the two rows above;Mix Creator;https://creativecommons.org/licenses/by/4.0/;48 kHz;PCM;stereo;stereo PCM;10;test",
            ]
        )
        rows = list(csv.DictReader(io.StringIO(payload), delimiter=";"))
        primary, dependencies = ATTRIBUTION_MODULE.resolved_licence_records(
            rows, ["derived"]
        )
        self.assertEqual(1, len(primary))
        self.assertEqual(2, len(dependencies))
        self.assertFalse(primary[0]["attribution_fields_complete"])
        self.assertTrue(primary[0]["attribution_notice_ready"])
        self.assertEqual("derived", primary[0]["attribution_notice_title"])
        self.assertEqual(
            "derived_mix_with_two_preceding_source_rows",
            primary[0]["attribution_resolution"],
        )
        self.assertEqual(
            {item["licence_record_id"] for item in dependencies},
            set(primary[0]["attribution_dependency_licence_record_ids"]),
        )

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
