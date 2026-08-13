import concurrent.futures
import copy
import importlib.util
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scripts/perceptual_degradation_listening_allocation_journal.py"
)
SPEC = importlib.util.spec_from_file_location(
    "perceptual_degradation_listening_allocation_journal", SCRIPT
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class AllocationJournalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = MODULE.load_json(MODULE.PLAN_PATH)

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.path = self.root / "journal.sqlite3"
        self.journal = MODULE.AllocationJournal(self.path)
        self.config = MODULE._synthetic_config(
            stream_id="stream-test-audit-0001"
        )
        self.journal.initialize_stream(self.config)

    def tearDown(self):
        self.temporary.cleanup()

    def reserve(self, index: int, *, fault_point=None):
        request_id, binding, attestation = MODULE._request_parts(
            "test", str(index)
        )
        return self.journal.reserve(
            stream_id=self.config.stream_id,
            request_id=request_id,
            request_binding_sha256=binding,
            eligibility_attestation_sha256=attestation,
            fault_point=fault_point,
        )

    def test_frozen_plan_validates(self):
        self.assertEqual(MODULE.validate_plan(self.plan), [])

    def test_binding_mutation_is_rejected(self):
        mutated = copy.deepcopy(self.plan)
        mutated["bindings"]["allocator_v3"]["sha256"] = "0" * 64
        self.assertIn(
            "binding allocator_v3 sha256 differs",
            MODULE.validate_plan(mutated),
        )

    def test_stream_initialization_is_idempotent_but_immutable(self):
        self.assertFalse(self.journal.initialize_stream(self.config))
        changed = MODULE.StreamConfig(
            **{
                **self.config._asdict(),
                "manifest_sha256": MODULE.digest("changed"),
            }
        )
        with self.assertRaisesRegex(ValueError, "configuration conflict"):
            self.journal.initialize_stream(changed)

    def test_same_request_is_exactly_once_and_conflicts_fail(self):
        first = self.reserve(0)
        second = self.reserve(0)
        self.assertTrue(first["created"])
        self.assertFalse(first["idempotent_retry"])
        self.assertFalse(second["created"])
        self.assertTrue(second["idempotent_retry"])
        self.assertEqual(first["allocation_index"], second["allocation_index"])
        request_id, _, attestation = MODULE._request_parts("test", "0")
        with self.assertRaisesRegex(ValueError, "conflicting idempotent"):
            self.journal.reserve(
                stream_id=self.config.stream_id,
                request_id=request_id,
                request_binding_sha256=MODULE.digest("different-binding"),
                eligibility_attestation_sha256=attestation,
            )

    def test_concurrent_duplicate_calls_create_contiguous_unique_rows(self):
        calls = [index for index in range(24) for _ in range(3)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=12) as executor:
            results = list(executor.map(self.reserve, calls))
        self.assertEqual(sum(result["created"] for result in results), 24)
        self.assertEqual(
            sum(result["idempotent_retry"] for result in results), 48
        )
        verified = MODULE.verify_journal(
            self.path,
            expected_configs={self.config.stream_id: self.config},
        )
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["reservation_count"], 24)
        self.assertTrue(verified["streams"][0]["contiguous"])

    def test_logical_faults_rollback_or_recover_idempotently(self):
        for index, fault_point in enumerate(
            (
                "before_begin",
                "after_begin_before_insert",
                "after_insert_before_commit",
            )
        ):
            with self.assertRaises(MODULE.LogicalFault):
                self.reserve(index, fault_point=fault_point)
            self.assertTrue(self.reserve(index)["created"])
        with self.assertRaises(MODULE.CommittedReplyLost):
            self.reserve(3, fault_point="after_commit_before_reply")
        recovered = self.reserve(3)
        self.assertFalse(recovered["created"])
        self.assertTrue(recovered["idempotent_retry"])
        verified = MODULE.verify_journal(
            self.path,
            expected_configs={self.config.stream_id: self.config},
        )
        self.assertTrue(verified["valid"])
        self.assertEqual(verified["reservation_count"], 4)

    def test_append_only_triggers_block_reservation_mutation(self):
        self.reserve(0)
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(
                    "UPDATE reservations SET allocation_index = 4"
                )
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("DELETE FROM reservations")
        finally:
            connection.close()
        self.assertTrue(
            MODULE.verify_journal(
                self.path,
                expected_configs={self.config.stream_id: self.config},
            )["valid"]
        )

    def test_verifier_detects_hash_chain_tamper(self):
        for index in range(3):
            self.reserve(index)
        connection = sqlite3.connect(self.path, isolation_level=None)
        try:
            connection.execute("DROP TRIGGER reservations_no_update")
            connection.execute(
                "UPDATE reservations SET event_sha256 = ? "
                "WHERE allocation_index = 1",
                ("f" * 64,),
            )
        finally:
            connection.close()
        verified = MODULE.verify_journal(
            self.path,
            expected_configs={self.config.stream_id: self.config},
        )
        self.assertFalse(verified["valid"])
        self.assertTrue(
            any("event hash differs" in error for error in verified["errors"])
        )

    def test_schema_has_no_identity_response_or_outcome_columns(self):
        verified = MODULE.verify_journal(
            self.path,
            expected_configs={self.config.stream_id: self.config},
        )
        self.assertFalse(verified["identity_columns_present"])
        self.assertFalse(verified["response_or_outcome_columns_present"])

    def test_committed_report_is_bound_and_collection_disabled(self):
        report = MODULE.load_json(MODULE.REPORT_PATH)
        self.assertEqual(
            report["plan_sha256"], MODULE.sha256_file(MODULE.PLAN_PATH)
        )
        self.assertEqual(
            report["implementation_sha256"], MODULE.sha256_file(SCRIPT)
        )
        self.assertEqual(MODULE.validate_report(report), [])
        self.assertTrue(
            report["decision"][
                "candidate_passed_synthetic_single_database_audit"
            ]
        )
        self.assertFalse(report["decision"]["operational_policy_selected"])
        self.assertFalse(report["decision"]["human_collection_authorized"])
        self.assertFalse(report["decision"]["response_atomicity_proven"])


if __name__ == "__main__":
    unittest.main()
