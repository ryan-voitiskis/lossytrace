"""Constructed data and mocked codec/CI boundaries only; no real canary run."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import perceptual_degradation_digital_canary_v5 as M
from test_perceptual_degradation_digital_development import fixture, fake_codec


def raw_alignment(**kwargs):
    return {"record_kind": M.alignment.RECORD_KIND,
            "case_id": M.alignment.legacy.case_id(kwargs["recipe_identity"]),
            "public_verdict_enabled": False, "status": "unsupported",
            "support": {"reasons": ["insufficient_active_audio"]},
            "alignment": {"summary": {"active_seconds": 0.0, "aligned_frames": 0}}}


def backend():
    result = Mock()
    result.record.return_value = {"native_candidates": 12, "fallback_candidates": 0,
                                  "searches": [{"window_frames": 32, "stride": 1, "candidate_count": 12, "search_count": 1}]}
    result.global_record.return_value = {
        "native_candidates": 12, "fallback_candidates": 0, "short_overlap_candidates": 0,
        "searches": [{"reference_frames": 32, "test_frames": 32, "candidate_count": 12, "search_count": 1}],
        "geometries": [{"overlap_frames": 32, "stride": 1, "sampled_frames": 32, "candidate_count": 12}]}
    return result


class CanaryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="canary-unit-")
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.records, self.plan = fixture(self.root)
        self.source = self.records[-1]
        self.parent = self.base / "output"
        self.parent.mkdir()
        self.tools = {key: self.base / key for key in ("ffmpeg", "ffprobe", "oggenc")}

    def tearDown(self):
        self.temp.cleanup()

    def process(self, source, recipe, root, parent, tools, kernel, sha):
        original = M.old.pcm_channels(M.old.bounded_bytes(root / source["relative_path"]))[0]
        with patch.object(M.old, "reserve"), patch.object(M.native, "Kernel", return_value=backend()), \
                patch.object(M.alignment, "align_channels", side_effect=raw_alignment), \
                patch.object(M.subprocess, "run", side_effect=AssertionError("no real codec")):
            return M.process_case(source, recipe, root, parent, tools, kernel, sha,
                                  invoke_fn=fake_codec(recipe, original))

    def replay(self):
        return M.run_replay(self.source, self.root, self.parent, self.tools, self.base / "kernel", "a" * 64,
                            process_fn=self.process)

    def test_public_plan_and_transitive_bindings(self):
        plan = M.load_plan()
        self.assertFalse(plan["execution_authorized"])
        self.assertEqual(12, plan["accounting"]["total_comparisons"])
        self.assertEqual(8, plan["accounting"]["maximum_encode_decode_pairs"])
        self.assertEqual([M.old.recipes()[i] for i in (1, 3, 5, 7)], plan["recipes"])
        self.assertNotEqual(M.AUTHORIZATION, M.old.AUTHORIZATION)

    def test_plan_rejects_changed_recipe_limits_claims_and_bindings(self):
        plan = M.old.load_json(M.PLAN)
        for mutate in (lambda p: p["recipes"][0]["encode_argv"].append("-y"),
                       lambda p: p["resources"].update(minimum_free_gib=14),
                       lambda p: p["claim_boundary"].update(perceptual_support=True),
                       lambda p: p["bindings"].pop("alignment_v5"),
                       lambda p: p["selection"].update(substitution_permitted=True),
                       lambda p: p["native_build"].update(compiler_sha256="0" * 64)):
            changed = copy.deepcopy(plan)
            mutate(changed)
            real = M.old.load_json
            with patch.object(M.old, "load_json", side_effect=lambda path, *args: changed if path == M.PLAN else real(path, *args)):
                with self.assertRaises(ValueError):
                    M.load_plan()

    def test_metadata_selection_reads_no_waveforms(self):
        real = M.old.bounded_bytes
        seen = []
        def read(path, *args):
            seen.append(path.name)
            self.assertNotEqual(".wav", path.suffix)
            return real(path, *args)
        with patch.object(M.old, "bounded_bytes", side_effect=read):
            self.assertEqual(self.source, M.selected_inventory(self.root, self.plan))
        self.assertEqual(["delivery.json", "attribution.json"], seen)

    def test_selection_is_length_then_identity_independent_of_record_order(self):
        records = copy.deepcopy(self.records)
        records[-2]["output_pcm_geometry"]["frame_count"] = records[-1]["output_pcm_geometry"]["frame_count"]
        self.assertEqual(records[-2], M.select_record(records))
        self.assertEqual(records[-2], M.select_record(list(reversed(records))))

    def test_selected_integrity_reads_only_selected_waveform(self):
        real = M.old.bounded_bytes
        with patch.object(M.old, "bounded_bytes", wraps=real) as read:
            M.verify_selected(self.root, self.source)
        self.assertEqual([self.root / self.source["relative_path"]], [call.args[0] for call in read.call_args_list])

    def test_inventory_corruption_symlink_and_attribution_rejected(self):
        with patch.object(M.old, "load_json", return_value={"completed": []}):
            with self.assertRaises(ValueError):
                M.selected_inventory(self.root, self.plan)
        with patch.object(M.old, "bounded_bytes", side_effect=ValueError("changed")):
            with self.assertRaises(ValueError):
                M.selected_inventory(self.root, self.plan)
        source = self.root / self.records[0]["relative_path"]
        source.rename(source.with_suffix(".saved"))
        source.symlink_to(source.with_suffix(".saved"))
        with self.assertRaises(ValueError):
            M.selected_inventory(self.root, self.plan)

    def test_declared_geometry_and_hash_checked_before_selected_read(self):
        real = M.old.load_json(self.root / "delivery.json")
        real["completed"][0]["output_pcm_geometry"]["frame_count"] = True
        with patch.object(M.old, "load_json", return_value=real):
            with self.assertRaises(ValueError):
                M.selected_inventory(self.root, self.plan)
        changed = copy.deepcopy(self.source)
        changed["output_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            M.verify_selected(self.root, changed)

    def test_duplicate_metadata_identity_is_rejected_at_member_boundary(self):
        state = M.old.load_json(self.root / "delivery.json")
        state["completed"][1] = copy.deepcopy(state["completed"][0])
        inventory = M.old.digest(json.dumps(state["completed"], sort_keys=True, separators=(",", ":")).encode())
        state["output_inventory_sha256"] = inventory
        plan = copy.deepcopy(self.plan)
        plan["cohort"]["delivery_inventory_sha256"] = inventory
        with patch.object(M.old, "load_json", return_value=state):
            with self.assertRaisesRegex(ValueError, "duplicate member identity"):
                M.selected_inventory(self.root, plan)

    def test_authorization_failure_precedes_all_private_and_native_access(self):
        args = SimpleNamespace(ci_run_id="123")
        with patch.object(M, "load_plan", return_value={}), patch.object(M, "authorize", side_effect=ValueError("closed")), \
                patch.object(M, "native_preflight") as native, patch.object(M.old, "outside_repository") as private:
            with self.assertRaisesRegex(ValueError, "closed"):
                M.execute(args)
        native.assert_not_called()
        private.assert_not_called()

    def test_missing_new_authorization_and_old_authorization_both_fail(self):
        with patch.object(M.sys, "flags", SimpleNamespace(isolated=1)):
            with patch.object(M, "AUTHORIZATION", self.base / "absent.json"):
                with self.assertRaises(ValueError):
                    M.authorize({"proposal_id": M.PROPOSAL_ID}, "123")
            with patch.object(M, "AUTHORIZATION", M.old.AUTHORIZATION):
                with self.assertRaisesRegex(ValueError, "new exact canary"):
                    M.authorize({"proposal_id": M.PROPOSAL_ID}, "123")

    def auth_fixture(self):
        return {"schema_version": 1, "proposal_id": M.PROPOSAL_ID,
                "proposal_sha256": M.old.binding.sha_file(M.PLAN),
                "runner_sha256": M.old.binding.sha_file(Path(M.__file__)),
                "standing_authorization_sha256": M.old.binding.sha_file(M.ROOT / M.BINDINGS["standing_authorization"]),
                "responsible_user_execution_approved": True,
                "one_selected_reference_two_six_case_replays_authorized": True,
                "metric_playback_listener_training_authorized": False}

    def test_clean_commit_exact_head_ci_and_isolation_required(self):
        auth = self.auth_fixture()
        head = "a" * 40
        good_ci = {"headSha": head, "status": "completed", "conclusion": "success", "workflowName": "CI", "event": "push"}
        def git(argv, **kwargs):
            if argv[1] == "status":
                return SimpleNamespace(stdout=b"")
            if argv[1] == "show":
                return SimpleNamespace(stdout=(M.ROOT / argv[2].removeprefix("HEAD:")).read_bytes())
            return SimpleNamespace(stdout=head.encode())
        # Mock file read for the new authorization, never create authority on disk.
        real_read = Path.read_bytes
        with patch.object(M.old, "load_json", return_value=auth), patch.object(M.sys, "flags", SimpleNamespace(isolated=1)), \
                patch.object(Path, "read_bytes", autospec=True, side_effect=lambda p: M.old.canonical(auth) if p == M.AUTHORIZATION else real_read(p)), \
                patch.object(M.subprocess, "run", side_effect=git), patch.object(M.old, "command_json", return_value=good_ci) as ci:
            self.assertEqual(head, M.authorize({"proposal_id": M.PROPOSAL_ID}, "123"))
            for field, value in (("headSha", "b" * 40), ("event", "pull_request"), ("conclusion", "failure"), ("status", "in_progress")):
                ci.return_value = {**good_ci, field: value}
                with self.assertRaises(ValueError):
                    M.authorize({"proposal_id": M.PROPOSAL_ID}, "123")
            ci.return_value = good_ci
            with patch.object(M.subprocess, "run", return_value=SimpleNamespace(stdout=b"dirty")):
                with self.assertRaises(ValueError):
                    M.authorize({"proposal_id": M.PROPOSAL_ID}, "123")
            with patch.object(M.sys, "flags", SimpleNamespace(isolated=0)):
                with self.assertRaises(ValueError):
                    M.authorize({"proposal_id": M.PROPOSAL_ID}, "123")

    def test_native_closure_mismatch_stops_before_compiler(self):
        with patch.object(M.old.binding, "bind_tools", return_value={}), patch.object(M.native, "sha") as sha:
            with self.assertRaisesRegex(ValueError, "runtime closure"):
                M.native_preflight(M.load_plan(), self.tools)
        sha.assert_not_called()

    def test_compiler_mismatch_rejected_even_when_codec_closure_matches(self):
        plan = M.load_plan()
        predecessor = M.old.load_plan()
        closure = M.old.load_json(M.ROOT / predecessor["bindings"]["native_tools"]["path"])
        with patch.object(M.old.binding, "bind_tools", return_value=closure), \
                patch.object(M.shutil, "which", return_value=str(Path(M.__file__))), \
                patch.object(M.native, "sha", return_value="0" * 64), \
                patch.object(M.subprocess, "check_output", return_value=b"mock compiler"):
            with self.assertRaisesRegex(ValueError, "compiler or environment"):
                M.native_preflight(plan, self.tools)

    def test_codec_wrapping_uses_new_identity_and_no_retained_scratch(self):
        replay = self.replay()
        self.assertEqual(6, len(replay["cases"]))
        for item, recipe in zip(replay["cases"], M.conditions(), strict=True):
            self.assertEqual("observed", item["state"])
            self.assertEqual(M.empty_case(self.source, recipe)["case_id"], item["case_id"])
            self.assertNotEqual(M.old.empty_case(self.source, recipe)["case_id"], item["case_id"])
            M.validate_case(item)
        self.assertEqual([], list(self.parent.iterdir()))
        self.assertIsNone(M.alignment.NATIVE_BACKEND)

    def test_timings_alone_do_not_break_deterministic_repeatability(self):
        first, second = self.replay(), self.replay()
        for item in second["cases"]:
            item["timing_seconds"]["case"] += 9.5
        report = M.summarize([first, second])
        self.assertTrue(report["all_cases_observed"])
        self.assertTrue(report["deterministic_evidence_byte_identical"])
        self.assertFalse(report["both_controls_technically_supported_both_rounds"])
        self.assertEqual(0, report["codec_comparisons_technically_supported"])
        self.assertEqual("bounded_canary_computationally_complete", report["state"])

    def test_hash_alignment_packet_and_native_changes_break_repeatability(self):
        first = self.replay()
        mutations = [lambda r: r["cases"][2].update(encoded_sha256="b" * 64),
                     lambda r: r["cases"][2].update(decoded_sha256="c" * 64),
                     lambda r: r["cases"][2]["packet_geometry"]["packets"][0].update(pts=-1023),
                     lambda r: r["cases"][0]["native_audit"].update(native_candidates=13),
                     lambda r: r["cases"][0]["comparison"]["alignment"].update(extra_diagnostic=1),
                     lambda r: r["cases"][0]["native_global_audit"].update(geometry_sha256="e" * 64)]
        for mutate in mutations:
            second = copy.deepcopy(first)
            mutate(second)
            self.assertFalse(M.summarize([first, second])["deterministic_evidence_byte_identical"])

    def test_every_slot_order_and_identity_remains_visible(self):
        first = self.replay()
        for mutate in (lambda r: r["cases"].pop(), lambda r: r["cases"].reverse(),
                       lambda r: r["cases"][0].update(case_id=r["cases"][1]["case_id"])):
            bad = copy.deepcopy(first)
            mutate(bad)
            with self.assertRaises(ValueError):
                M.summarize([first, bad])

    def test_technical_evidence_cannot_populate_quality(self):
        first = self.replay()
        for mutate in (lambda x: x.update(severity=0), lambda x: x.update(perceptual_support=True),
                       lambda x: x.update(subtle_technical_support=True),
                       lambda x: x["alignment"].update(public_verdict_enabled=True)):
            bad = copy.deepcopy(first)
            mutate(bad["cases"][0]["comparison"])
            with self.assertRaises(ValueError):
                M.summarize([first, bad])

    def test_invalid_timing_unknown_reasons_and_native_counts_fail(self):
        first = self.replay()
        for mutate in (lambda x: x["timing_seconds"].update(case=float("nan")),
                       lambda x: x["timing_seconds"].update(extra=1),
                       lambda x: x["native_audit"].update(native_candidates=-1),
                       lambda x: x["comparison"]["alignment"]["support"].update(reasons=["unreviewed"])):
            bad = copy.deepcopy(first)
            mutate(bad["cases"][0])
            with self.assertRaises(ValueError):
                M.summarize([first, bad])

    def test_resource_stop_does_not_restart_later_cases(self):
        process = Mock(side_effect=ValueError("reserve"))
        replay = M.run_replay(self.source, self.root, self.parent, self.tools, None, None, process_fn=process)
        self.assertEqual(1, process.call_count)
        self.assertEqual(["not_run"] * 6, [item["state"] for item in replay["cases"]])
        report = M.summarize([replay, copy.deepcopy(replay)])
        self.assertFalse(report["all_cases_observed"])
        self.assertTrue(report["deterministic_evidence_byte_identical"])

    def test_replay_cutoff_and_prior_stop_preserve_six_unrun_slots(self):
        process = Mock(side_effect=AssertionError("must not start"))
        with patch.object(M.time, "monotonic", side_effect=[0] + [1200] * 6):
            replay = M.run_replay(self.source, self.root, self.parent, self.tools, None, None, process_fn=process)
        self.assertEqual(["replay_time_budget"] * 6, [item["reason"] for item in replay["cases"]])
        M.run_replay(self.source, self.root, self.parent, self.tools, None, None,
                     process_fn=process, stopped="resource_or_preflight_stop")
        process.assert_not_called()

    def test_alignment_timeout_restores_backend_and_preserves_audit(self):
        with patch.object(M.old, "reserve"), patch.object(M.native, "Kernel", return_value=backend()), \
                patch.object(M.alignment, "align_channels", side_effect=M.old.CaseFailure("alignment_timeout")):
            item = M.process_case(self.source, "identity", self.root, self.parent, self.tools, None, None)
        self.assertEqual(("failed", "alignment_timeout"), (item["state"], item["reason"]))
        self.assertIsNone(item["comparison"])
        self.assertEqual(12, item["native_audit"]["native_candidates"])
        self.assertIsNone(M.alignment.NATIVE_BACKEND)
        self.assertEqual((0.0, 0.0), M.signal.getitimer(M.signal.ITIMER_REAL))

    def test_existing_backend_or_alarm_is_not_overwritten(self):
        for target, attribute, value in ((M.alignment, "NATIVE_BACKEND", backend()),
                                          (M.signal, "getitimer", Mock(return_value=(1.0, 0.0)))):
            with patch.object(target, attribute, value):
                with self.assertRaises(ValueError):
                    M.process_case(self.source, "identity", self.root, self.parent, self.tools, None, None)

    def test_public_projection_omits_private_ids_hashes_and_paths(self):
        first = self.replay()
        report = M.old.canonical(M.summarize([first, copy.deepcopy(first)]))
        for forbidden in (self.source["opaque_delivery_id"], self.source["output_sha256"], str(self.root),
                          first["cases"][0]["case_id"], first["cases"][2]["encoded_sha256"]):
            self.assertNotIn(forbidden.encode(), report)

    def test_edge_failure_keeps_observations_but_not_complete_state(self):
        first = self.replay()
        second = copy.deepcopy(first)
        second["edge_check_after"] = "preflight_failed"
        report = M.summarize([first, second])
        self.assertTrue(report["all_cases_observed"])
        self.assertFalse(report["all_edge_checks_passed"])
        self.assertEqual("bounded_canary_negative_or_incomplete", report["state"])

    def execute_fixture(self, *, changed_after_first=False, bad_build=False):
        plan = {**self.plan, "native_build": {"mock_compiler": True}}
        for path in self.tools.values():
            M.old.write_new(path, b"non-executable mock tool")
        args = SimpleNamespace(ci_run_id="123", source_root=self.root, output_parent=self.parent, **self.tools)
        real_load, real_replay = M.load_plan, M.run_replay
        def build(directory):
            file = directory / "correlation.mock"
            M.old.write_new(file, b"NOT A SHARED LIBRARY")
            return file, {"mock_compiler": not bad_build, "binary_sha256": "d" * 64}
        def replay(*args, **kwargs):
            return real_replay(*args, **kwargs, process_fn=self.process)
        checks = [None, None, ValueError("post-run drift")] if changed_after_first else [None] * 5
        with patch.object(M, "load_plan", return_value=plan), patch.object(M, "authorize", return_value="a" * 40), \
                patch.object(M, "native_preflight", side_effect=checks) as edges, \
                patch.object(M.old, "reserve"), patch.object(M.native, "build", side_effect=build), \
                patch.object(M.native, "Kernel", return_value=backend()), patch.object(M.native, "sha", return_value="d" * 64), \
                patch.object(M, "run_replay", side_effect=replay), patch.object(M, "verify_selected", wraps=M.verify_selected) as selected:
            if bad_build:
                with self.assertRaisesRegex(ValueError, "built kernel provenance"):
                    M.execute(args)
                selected.assert_not_called()
                return None
            report = M.execute(args)
        self.assertIs(real_load, M.load_plan)
        self.assertEqual(1 if changed_after_first else 4, selected.call_count)
        self.assertEqual(3 if changed_after_first else 5, edges.call_count)
        root = next(path for path in self.parent.iterdir() if path.is_dir())
        self.assertTrue((self.parent / (M.PROPOSAL_ID + ".launch.json")).is_file())
        self.assertEqual({"execution.json", "attribution.json", "replay-1.json", "replay-2.json",
                          "public-projection.json", "kernel"}, {path.name for path in root.iterdir()})
        self.assertEqual(report, json.loads((root / "public-projection.json").read_bytes()))
        self.assertEqual(6, len(json.loads((root / "replay-2.json").read_bytes())["cases"]))
        with self.assertRaises(FileExistsError):
            M.old.write_new(root / "execution.json", b"overwrite forbidden")
        return report

    def test_mocked_end_to_end_retains_only_declared_evidence(self):
        report = self.execute_fixture()
        self.assertTrue(report["all_cases_observed"])
        self.assertTrue(report["all_edge_checks_passed"])
        self.assertTrue(report["deterministic_evidence_byte_identical"])

    def test_post_run_drift_preserves_first_round_and_halts_second(self):
        report = self.execute_fixture(changed_after_first=True)
        self.assertEqual({"observed": 6}, report["replays"][0]["dispositions"])
        self.assertEqual({"not_run": 6}, report["replays"][1]["dispositions"])
        self.assertFalse(report["all_edge_checks_passed"])

    def test_build_provenance_failure_precedes_waveform_verification(self):
        self.execute_fixture(bad_build=True)

    def test_disk_reserve_not_lowered(self):
        minimum = 15 * 1024**3 + 384 * 1024**2
        with patch.object(M.old.shutil, "disk_usage", return_value=SimpleNamespace(free=minimum - 1)):
            with self.assertRaises(ValueError):
                M.old.reserve(self.parent)


    def test_global_audit_corruption_cannot_be_hidden(self):
        first = self.replay()
        for change in (lambda x: x.update(native_global_audit=None),
                       lambda x: x["native_global_audit"].update(native_candidates=-1),
                       lambda x: x["native_global_audit"].update(native_candidates=True),
                       lambda x: x["native_global_audit"].update(native_candidates=11),
                       lambda x: x["native_global_audit"].update(geometry_sha256="invalid"),
                       lambda x: x["native_global_audit"].update(geometry_rows=13),
                       lambda x: x["native_global_audit"]["searches"].append(x["native_global_audit"]["searches"][0]),
                       lambda x: x["native_global_audit"].update(extra=0)):
            bad = copy.deepcopy(first)
            change(bad["cases"][0])
            with self.assertRaises(ValueError):
                M.summarize([first, bad])

    def test_global_fallback_remains_visible_and_fails_primary_gate(self):
        first = self.replay()
        first["cases"][0]["native_global_audit"]["fallback_candidates"] = 1
        result = M.summarize([first, copy.deepcopy(first)])
        self.assertTrue(result["all_cases_observed"])
        self.assertFalse(result["no_native_fallback_all_cases"])
        self.assertFalse(result["primary_technical_gate_passed"])
        self.assertEqual(1, result["replays"][0]["global_fallback_candidates"])

    def test_timeout_retains_partial_global_work_without_fabricating_completion(self):
        first = self.replay()
        item = first["cases"][0]
        item.update(state="failed", reason="alignment_timeout", comparison=None)
        item["native_global_audit"]["native_candidates"] = 3
        M.validate_case(item)
        report = M.summarize([first, copy.deepcopy(first)])
        self.assertFalse(report["primary_technical_gate_passed"])
        self.assertFalse(report["no_native_fallback_all_cases"])

    def test_qualification_negative_or_missing_audit_closes_real_batch(self):
        real_load = M.old.load_json
        path = M.ROOT / M.BINDINGS["qualification_result"]
        result = real_load(path)
        for change in (lambda r: r.update(state="negative"),
                       lambda r: r["integrity"].update(independent_saved_artifact_audit_passed=False),
                       lambda r: r["observations"].update(all_full_alignments_within_120_seconds=False),
                       lambda r: r["observations"]["rounds"][0][1].update(wall_seconds=121),
                       lambda r: r["bindings"]["protocol"].update(sha256="0"*64)):
            changed = copy.deepcopy(result)
            change(changed)
            with patch.object(M.old, "load_json", side_effect=lambda p, *a: changed if p == path else real_load(p, *a)):
                with self.assertRaises(ValueError):
                    M.load_plan()

    def test_standing_authority_does_not_accept_consumed_predecessor_batch(self):
        with patch.object(M.sys, "flags", SimpleNamespace(isolated=1)), patch.object(M, "AUTHORIZATION", M.base.AUTHORIZATION):
            with self.assertRaisesRegex(ValueError, "new exact canary authorization"):
                M.authorize({"proposal_id": M.PROPOSAL_ID}, "123")

    def test_exclusive_launch_marker_is_not_overwritten(self):
        M.claim_launch(self.parent, "a"*40, "123")
        marker = self.parent / (M.PROPOSAL_ID + ".launch.json")
        before = marker.read_bytes()
        with self.assertRaises(FileExistsError):
            M.claim_launch(self.parent, "a"*40, "123")
        self.assertEqual(before, marker.read_bytes())

    def test_real_execution_uses_v5_without_modifying_frozen_module_globals(self):
        with patch.object(M.base.alignment, "align_channels", side_effect=AssertionError("v4 must not execute")):
            self.replay()
        self.assertIsNone(M.base.alignment.NATIVE_BACKEND)
        self.assertEqual("perceptual_degradation_alignment_v5", M.alignment.__name__)

    def test_maximum_time_and_search_semantics_do_not_expand(self):
        plan = M.load_plan()
        self.assertEqual(M.base.RESOURCES["maximum_case_seconds"], plan["resources"]["maximum_case_seconds"])
        self.assertEqual(M.base.RESOURCES["stop_starting_cases_after_replay_seconds"],
                         plan["resources"]["stop_starting_cases_after_replay_seconds"])
        self.assertEqual(M.base.SELECTION, plan["selection"])
        self.assertEqual(M.base.ACCOUNTING, plan["accounting"])


if __name__ == "__main__":
    unittest.main()
