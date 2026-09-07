"""Constructed fixtures only. Codec/tool/CI execution boundaries are mocked."""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import perceptual_degradation_digital_development as M
import perceptual_degradation_digital_tools as T


def pcm(bits=24, frames=32, seed=1):
    width = bits // 8
    pairs = [(seed * (index + 1), -seed * (index + 2)) for index in range(frames)]
    data = b"".join(value.to_bytes(width, "little", signed=True) for pair in pairs for value in pair)
    fmt = struct.pack("<HHIIHH", 1, 2, 48000, 48000 * width * 2, width * 2, bits)
    body = b"WAVEfmt " + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data
    return b"RIFF" + struct.pack("<I", len(body)) + body


def fixture(root):
    root.mkdir()
    (root / "sources").mkdir()
    (root / ".partial").mkdir()
    records = []
    for index in range(16):
        bits, frames = (24 if index < 9 else 32), 32 + index
        identity = f"odaq-delivery-{index:024x}"
        relative = "sources/" + identity + ".wav"
        data = pcm(bits, frames, (index + 1) * (100001 if bits == 32 else 1))
        M.write_new(root / relative, data)
        geometry = M.pcm_channels(data)[1]
        records.append({"opaque_delivery_id": identity, "relative_path": relative,
                        "output_sha256": M.digest(data), "output_byte_length": len(data), "output_pcm_geometry": geometry})
    attribution = M.canonical({"synthetic_fixture": True, "mappings": []})
    M.write_new(root / "attribution.json", attribution)
    inventory = M.digest(json.dumps(records, sort_keys=True, separators=(",", ":")).encode())
    cohort = {"delivery_inventory_sha256": inventory, "original_inventory_sha256": "b" * 64,
              "delivery_authorization_sha256": "a" * 64, "attribution_sha256": M.digest(attribution),
              "total_bytes": sum(item["output_byte_length"] for item in records),
              "minimum_frames": 32, "maximum_frames": 47, "bit_depth_counts": {"24": 9, "32": 7}}
    state = {"schema_version": 1, "state": "private_delivery_projection_complete", "completed_count": 16,
             "reference_count": 16, "completed": records, "output_inventory_sha256": inventory,
             "input_inventory_sha256": cohort["original_inventory_sha256"],
             "authorization_sha256": cohort["delivery_authorization_sha256"], "attribution_sha256": cohort["attribution_sha256"]}
    state.update({key: False for key in ("processed_condition_opened", "listening_score_opened", "perceptual_metric_executed",
                                       "listener_response_collected", "sealed_evidence_opened", "public_verdict_emitted")})
    M.write_new(root / "delivery.json", M.canonical(state))
    return records, {"cohort": cohort}


def comparison(reference, test, identity, deadline):
    return {"alignment": {"status": "unsupported", "support": {"reasons": ["insufficient_active_audio"]},
                           "alignment": {"summary": {"active_seconds": 0.0, "aligned_frames": 0}}},
            "active_seconds_bounded_by_geometry": 0.0, "duration_geometry_cap_applied": False,
            "subtle_technical_support": False, "quality_duration_eligible": False, "perceptual_support": False,
            "severity": None, "audibility": None, "artifacts": None, "transparency": None}


def fake_probe(recipe):
    return {"streams": [{"codec_name": recipe["expected_codec_name"], "sample_rate": "48000", "channels": 2,
                         "profile": recipe["expected_profile"], "channel_layout": "stereo", "time_base": "1/48000"}],
            "packets": [{"pts": -1024, "dts": -1024, "duration": 1024,
                         "side_data_list": [{"side_data_type": "Skip Samples", "skip_samples": 1024, "discard_padding": 0}]}]}


def fake_codec(recipe, original):
    def invoke(argv, files, stage, scratch, deadline):
        if stage == "encode":
            M.write_new(files["encoded"], b"NOT-AN-AUDIO-CODEC-FIXTURE:" + recipe["id"].encode())
        elif stage == "probe":
            return M.canonical(fake_probe(recipe))
        elif stage == "decode":
            adapted = M.float32_adapter(original)[1]
            M.write_new(files["decoded"], b"".join(struct.pack("<dd", *pair) for pair in zip(*adapted, strict=True)))
        else:
            raise AssertionError(stage)
        return b""
    return invoke


class DigitalDevelopmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="digital-unit-")
        self.base = Path(self.temp.name)
        self.root = self.base / "source"
        self.records, self.fixture_plan = fixture(self.root)
        self.scratch = self.base / "scratch"
        self.scratch.mkdir()
        self.tools = {key: self.base / key for key in ("ffmpeg", "ffprobe", "oggenc")}

    def tearDown(self):
        self.temp.cleanup()

    def test_exact_plan_and_all_bindings(self):
        plan = M.load_plan()
        self.assertEqual(8, len(plan["recipes"]))
        self.assertEqual(320, plan["accounting"]["total_cases"])
        self.assertIs(plan["execution_authorized"], False)

    def test_changed_recipe_or_missing_binding_fails(self):
        raw = M.load_json(M.PLAN)
        for operation in (lambda p: p["recipes"][0]["encode_argv"].append("-y"),
                          lambda p: p["bindings"].pop("alignment_v1"),
                          lambda p: p["cohort"].update(minimum_frames=1)):
            value = copy.deepcopy(raw)
            operation(value)
            original = M.load_json
            with patch.object(M, "load_json", side_effect=lambda file, *args: value if file == M.PLAN else original(file, *args)):
                with self.assertRaises(ValueError):
                    M.load_plan()

    def test_four_development_lineages_two_operating_points_each(self):
        self.assertEqual({"mp3": 2, "aac_lc": 2, "opus": 2, "vorbis": 2}, dict(M.Counter(item["codec_family"] for item in M.recipes())))
        self.assertTrue(all(item["id"].startswith("digital48-") for item in M.recipes()))
        self.assertEqual({"mp3float", "aac", "opus", "vorbis"}, {item["decoder"] for item in M.recipes()})

    def test_integer_pcm_preserves_stereo_and_exact_scale(self):
        for bits in (24, 32):
            channels, geometry = M.pcm_channels(pcm(bits, 32, 7))
            self.assertEqual([7 / 2**(bits - 1), -14 / 2**(bits - 1)], [channel[0] for channel in channels])
            self.assertEqual(32, geometry["frame_count"])

    def test_pcm_rejects_wrong_rate_format_channels_and_length(self):
        for offset, value, encoding in ((24, 44100, "I"), (20, 3, "H"), (22, 1, "H"), (40, 1, "I")):
            bad = bytearray(pcm())
            struct.pack_into("<" + encoding, bad, offset, value)
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                M.pcm_channels(bytes(bad))

    def test_float_adapter_exact_24_bit_and_declared_32_bit_rounding(self):
        original = [[1 / 2**23, (2**31 - 1) / 2**31], [-1.0, -1 / 2**31]]
        encoded, adapted = M.float32_adapter(original)
        self.assertEqual(original[0][0], adapted[0][0])
        self.assertEqual(1.0, adapted[0][1])
        self.assertNotEqual(original[0][1], adapted[0][1])
        self.assertEqual(3, struct.unpack_from("<H", encoded, 20)[0])
        self.assertEqual(2, struct.unpack_from("<I", encoded, 44)[0])

    def test_float_adapter_rejects_nonfinite_and_bad_shape(self):
        for values in ([[float("nan")], [0.0]], [[2.0], [0.0]], [[], []], [[0.0], [0.0, 1.0]]):
            with self.assertRaises(ValueError):
                M.float32_adapter(values)

    def test_decoder_preserves_values_above_full_scale(self):
        decoded = M.decoded_channels(struct.pack("<dd", 1.2, -1.3), 32)
        self.assertEqual([[1.2], [-1.3]], decoded)

    def test_decoder_rejects_nonfinite_empty_and_partial_frames(self):
        for data in (b"", b"short", struct.pack("<dd", float("inf"), 0)):
            with self.assertRaises(M.CaseFailure):
                M.decoded_channels(data, 32)

    def test_full_synthetic_delivery_inventory(self):
        self.assertEqual(self.records, M.source_inventory(self.root, self.fixture_plan))

    def test_tampered_inventory_digest_rejected(self):
        changed = copy.deepcopy(self.fixture_plan)
        changed["cohort"]["delivery_inventory_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "inventory differs"):
            M.source_inventory(self.root, changed)

    def test_unexpected_file_rejected(self):
        M.write_new(self.root / "sources" / "extra.wav", b"synthetic")
        with self.assertRaises(ValueError):
            M.source_inventory(self.root, self.fixture_plan)

    def test_changed_payload_rejected(self):
        file = self.root / self.records[0]["relative_path"]
        file.write_bytes(pcm(seed=99))
        with self.assertRaisesRegex(ValueError, "integrity differs"):
            M.source_inventory(self.root, self.fixture_plan)

    def test_changed_attribution_rejected(self):
        (self.root / "attribution.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "attribution differs"):
            M.source_inventory(self.root, self.fixture_plan)

    def test_symlink_source_or_root_rejected(self):
        link = self.base / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            M.source_inventory(link, self.fixture_plan)
        file = self.root / self.records[0]["relative_path"]
        target = self.base / "saved-synthetic.wav"
        file.rename(target)
        file.symlink_to(target)
        with self.assertRaises(ValueError):
            M.source_inventory(self.root, self.fixture_plan)

    def test_no_clobber_and_private_modes(self):
        file = self.base / "new.json"
        M.write_new(file, b"first")
        self.assertEqual(0o600, file.stat().st_mode & 0o777)
        with self.assertRaises(FileExistsError):
            M.write_new(file, b"second")
        self.assertEqual(b"first", file.read_bytes())

    def test_reserved_space_includes_scratch_headroom(self):
        with patch.object(M.shutil, "disk_usage", return_value=SimpleNamespace(free=M.MIN_FREE + 12 * M.MAX_FILE - 1)):
            with self.assertRaises(ValueError):
                M.reserve(self.scratch)

    def test_private_access_is_after_authorization(self):
        with patch.object(M, "load_plan", return_value={}), patch.object(M, "authorize", side_effect=ValueError("closed")), \
                patch.object(M, "outside_repository") as private, patch.object(T, "bind_tools") as tool_probe:
            with self.assertRaisesRegex(ValueError, "closed"):
                M.execute(argparse.Namespace(ci_run_id="123"))
            private.assert_not_called()
            tool_probe.assert_not_called()

    def test_changed_native_tools_stop_before_private_access(self):
        for file in self.tools.values():
            M.write_new(file, b"synthetic tool placeholder")
        args = argparse.Namespace(ci_run_id="123", **self.tools)
        plan = {"bindings": {"native_tools": {"path": M.BINDING_FILES["native_tools"]}}}
        with patch.object(M, "load_plan", return_value=plan), patch.object(M, "authorize", return_value="a" * 40), \
                patch.object(T, "bind_tools", return_value={}), patch.object(M, "outside_repository") as private:
            with self.assertRaisesRegex(ValueError, "binding changed"):
                M.execute(args)
            private.assert_not_called()

    def test_changed_second_inventory_preserves_unattempted_replay(self):
        for file in self.tools.values():
            M.write_new(file, b"synthetic tool placeholder")
        args = argparse.Namespace(ci_run_id="123", source_root=self.root, output_parent=self.scratch, **self.tools)
        plan = {"bindings": {"native_tools": {"path": M.BINDING_FILES["native_tools"]}}}
        native = M.load_json(M.ROOT / M.BINDING_FILES["native_tools"])
        with patch.object(M, "load_plan", return_value=plan), patch.object(M, "authorize", return_value="a" * 40), \
                patch.object(T, "bind_tools", return_value=native), patch.object(M, "reserve"), \
                patch.object(M, "source_inventory", side_effect=[self.records, self.records, ValueError("changed")]), \
                patch.object(M, "run_replay", return_value=self.mocked_replay()) as replay:
            report = M.execute(args)
        replay.assert_called_once()
        self.assertEqual({"not_run": 160}, report["replays"][1]["dispositions"])
        self.assertEqual("technical_negative_or_incomplete", report["state"])
        directories = list(self.scratch.iterdir())
        self.assertEqual(1, len(directories))
        self.assertEqual({"execution.json", "attribution.json", "replay-1.json", "replay-2.json", "public-projection.json"},
                         {item.name for item in directories[0].iterdir()})

    def test_exact_authorization_and_ci_are_required(self):
        plan_file, runner_file, auth_file = (self.base / name for name in ("plan.json", "runner.py", "authorization.json"))
        M.write_new(plan_file, b"synthetic plan")
        M.write_new(runner_file, b"synthetic runner")
        auth = {"schema_version": 1, "proposal_id": M.PROPOSAL_ID,
                "proposal_sha256": T.sha_file(plan_file), "runner_sha256": T.sha_file(runner_file),
                "responsible_user_execution_approved": True, "retained_delivery_read_and_codec_replays_authorized": True,
                "metric_playback_listener_training_authorized": False}
        M.write_new(auth_file, M.canonical(auth))
        head = "a" * 40
        def git(command, **kwargs):
            if command[1] == "status":
                return SimpleNamespace(stdout=b"")
            if command[1] == "show":
                return SimpleNamespace(stdout=(self.base / command[2].removeprefix("HEAD:")).read_bytes())
            return SimpleNamespace(stdout=(head + "\n").encode())
        ci = {"headSha": head, "status": "completed", "conclusion": "success", "workflowName": "CI", "event": "push"}
        with patch.object(M, "ROOT", self.base), patch.object(M, "PLAN", plan_file), \
                patch.object(M, "AUTHORIZATION", auth_file), patch.object(M, "__file__", str(runner_file)), \
                patch.object(M.sys, "flags", SimpleNamespace(isolated=1)), \
                patch.object(M.subprocess, "run", side_effect=git), patch.object(M, "command_json", return_value=ci):
            self.assertEqual(head, M.authorize({}, "123"))
            auth["responsible_user_execution_approved"] = 1
            auth_file.write_bytes(M.canonical(auth))
            with self.assertRaisesRegex(ValueError, "authorization"):
                M.authorize({}, "123")
            auth["responsible_user_execution_approved"] = True
            auth_file.write_bytes(M.canonical(auth))
            ci["headSha"] = "b" * 40
            with self.assertRaisesRegex(ValueError, "exact execution HEAD"):
                M.authorize({}, "123")
            auth["responsible_user_execution_approved"] = False
            auth_file.write_bytes(M.canonical(auth))
            with self.assertRaisesRegex(ValueError, "authorization"):
                M.authorize({}, "123")

    def test_packet_metadata_records_delay_without_correction(self):
        recipe = M.recipes()[0]
        value = fake_probe(recipe)
        self.assertEqual(value, M.packet_geometry(value, recipe))
        self.assertEqual(-1024, value["packets"][0]["pts"])

    def test_packet_geometry_and_types_fail_closed(self):
        recipe = M.recipes()[0]
        for mutate in (lambda p: p["streams"][0].update(channels=1), lambda p: p["streams"][0].update(sample_rate="44100"),
                       lambda p: p["packets"][0].update(pts=float("nan")), lambda p: p["streams"].append({}),
                       lambda p: p["streams"][0].update(time_base="0/0"),
                       lambda p: p["packets"][0]["side_data_list"][0].update(skip_samples=float("nan"))):
            value = fake_probe(recipe)
            mutate(value)
            with self.assertRaises(M.CaseFailure):
                M.packet_geometry(value, recipe)

    def test_aac_profile_must_be_lc(self):
        recipe = M.recipes()[2]
        value = fake_probe(recipe)
        value["streams"][0]["profile"] = "HE-AAC"
        with self.assertRaises(M.CaseFailure):
            M.packet_geometry(value, recipe)

    def test_one_mocked_codec_case_and_scratch_cleanup(self):
        source, recipe = self.records[0], M.recipes()[0]
        original = M.pcm_channels((self.root / source["relative_path"]).read_bytes())[0]
        with patch.object(M, "reserve"), patch.object(M.subprocess, "run", side_effect=AssertionError("no actual tools in tests")):
            result = M.process_case(source, recipe, self.root, self.scratch, self.tools,
                                    compare_fn=comparison, invoke_fn=fake_codec(recipe, original))
        self.assertEqual("observed", result["state"])
        self.assertIsNotNone(result["encoded_sha256"])
        self.assertIsNotNone(result["decoded_sha256"])
        self.assertEqual([], list(self.scratch.iterdir()))

    def test_control_never_calls_codec_and_uses_correct_reference(self):
        captured = []
        def observe(reference, test, *args):
            captured.append((reference, test))
            return comparison(reference, test, *args)
        forbidden = Mock(side_effect=AssertionError("control called codec"))
        with patch.object(M, "reserve"):
            for control in M.CONTROLS:
                M.process_case(self.records[-1], control, self.root, self.scratch, self.tools, observe, forbidden)
        self.assertIs(captured[0][0], captured[0][1])
        self.assertIsNot(captured[1][0], captured[1][1])
        forbidden.assert_not_called()

    def test_failed_codec_is_kept_and_scratch_removed(self):
        with patch.object(M, "reserve"):
            result = M.process_case(self.records[0], M.recipes()[0], self.root, self.scratch, self.tools,
                                    invoke_fn=Mock(side_effect=M.CaseFailure("encode_failed")))
        self.assertEqual("failed", result["state"])
        self.assertEqual("encode_failed", result["reason"])
        self.assertIsNone(result["comparison"])
        self.assertEqual([], list(self.scratch.iterdir()))

    def test_both_duration_limits_and_no_perceptual_claim(self):
        raw = {"status": "supported", "alignment": {"summary": {"active_seconds": 6.0, "aligned_frames": 288000}}, "support": {"reasons": []}}
        with patch.object(M.alignment, "align_channels", return_value=raw) as align:
            result = M.compare([[1], [2]], [[1], [2]], "synthetic", time.monotonic() + 10)
        self.assertEqual(4.0, align.call_args.kwargs["minimum_active_seconds"])
        self.assertTrue(result["subtle_technical_support"])
        self.assertFalse(result["quality_duration_eligible"])
        self.assertFalse(result["perceptual_support"])
        self.assertIsNone(result["transparency"])

    def test_partial_block_cannot_invent_four_or_eight_seconds(self):
        for seconds, field in ((4, "subtle_technical_support"), (8, "quality_duration_eligible")):
            raw = {"status": "supported", "alignment": {"summary": {"active_seconds": float(seconds), "aligned_frames": seconds * 48000 - 1}}}
            result = M.duration_eligibility(raw)
            self.assertFalse(result[field])
            self.assertTrue(result["duration_geometry_cap_applied"])
            self.assertEqual(float(seconds), raw["alignment"]["summary"]["active_seconds"])
            raw["alignment"]["summary"]["aligned_frames"] += 1
            self.assertTrue(M.duration_eligibility(raw)[field])

    def test_missing_geometry_cannot_support_duration(self):
        raw = {"status": "supported", "alignment": {"summary": {"active_seconds": 8.0, "aligned_frames": None}}}
        result = M.duration_eligibility(raw)
        self.assertIsNone(result["active_seconds_bounded_by_geometry"])
        self.assertFalse(result["quality_duration_eligible"])

    def test_expired_analysis_deadline(self):
        with self.assertRaises(M.CaseFailure):
            with M.analysis_deadline(time.monotonic() - 1):
                self.fail("expired deadline entered body")

    def test_real_alignment_on_tiny_constructed_arrays_abstains(self):
        original = M.pcm_channels(pcm())[0]
        result = M.compare(original, original, "constructed-tiny", time.monotonic() + 10)
        self.assertFalse(result["subtle_technical_support"])
        self.assertFalse(result["quality_duration_eligible"])
        self.assertIsNone(result["audibility"])

    def test_codec_invocation_failure_timeout_and_deadline_are_typed(self):
        for failure, reason in ((SimpleNamespace(returncode=1), "encode_failed"),
                                (M.subprocess.TimeoutExpired("synthetic", 1), "encode_timeout")):
            with tempfile.TemporaryDirectory(dir=self.scratch) as directory:
                side_effect = failure if isinstance(failure, Exception) else None
                with patch.object(M.subprocess, "run", side_effect=side_effect, return_value=failure), \
                        self.assertRaisesRegex(M.CaseFailure, reason):
                    M.invoke(["<ffmpeg>"], self.tools, "encode", Path(directory), time.monotonic() + 10)
        with patch.object(M.subprocess, "run") as run, self.assertRaisesRegex(M.CaseFailure, "case_time_budget"):
            M.invoke(["<ffmpeg>"], self.tools, "encode", self.scratch, time.monotonic() - 1)
        run.assert_not_called()

    def test_command_argv_is_literal_and_environment_is_bounded(self):
        with patch.object(M.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            M.invoke(["<ffmpeg>", "-i", "<adapter>"], {**self.tools, "adapter": "literal file; name"},
                     "encode", self.scratch, time.monotonic() + 10)
        self.assertEqual("literal file; name", run.call_args.args[0][-1])
        self.assertNotIn("shell", run.call_args.kwargs)
        self.assertEqual(M.ENV, run.call_args.kwargs["env"])
        self.assertLessEqual(run.call_args.kwargs["timeout"], 60)

    def test_child_file_bound(self):
        with patch.object(M.resource, "setrlimit") as limit:
            M.child_limits()
        limit.assert_called_once_with(M.resource.RLIMIT_FSIZE, (M.MAX_FILE, M.MAX_FILE))

    def test_two_complete_codec_boundary_replays_without_real_tools(self):
        def process(source, recipe, root, parent, tools):
            original = M.pcm_channels((root / source["relative_path"]).read_bytes())[0]
            codec = fake_codec(recipe, original) if isinstance(recipe, dict) else Mock(side_effect=AssertionError)
            return M.process_case(source, recipe, root, parent, tools, compare_fn=comparison, invoke_fn=codec)
        with patch.object(M, "reserve"), patch.object(M.subprocess, "run", side_effect=AssertionError("actual codec forbidden")):
            first = M.run_replay(self.records, self.root, self.scratch, self.tools, process_fn=process)
            second = M.run_replay(self.records, self.root, self.scratch, self.tools, process_fn=process)
        report = M.summarize([first, second])
        self.assertTrue(report["private_replays_byte_identical"])
        self.assertTrue(report["all_cases_observed"])
        self.assertEqual([], list(self.scratch.iterdir()))
        self.assertEqual(128, sum(item["encoded_sha256"] is not None for item in first["cases"]))

    def mocked_replay(self):
        def process(source, recipe, root, parent, tools):
            item = M.empty_case(source, recipe)
            item.update(state="observed", comparison=comparison(None, None, None, None))
            return item
        return M.run_replay(self.records, self.root, self.scratch, self.tools, process_fn=process)

    def test_two_complete_mocked_replays_are_identical_and_path_free(self):
        first, second = self.mocked_replay(), self.mocked_replay()
        self.assertEqual(160, len(first["cases"]))
        self.assertEqual(M.canonical(first), M.canonical(second))
        report = M.summarize([first, second])
        self.assertTrue(report["private_replays_byte_identical"])
        self.assertTrue(report["all_cases_observed"])
        self.assertEqual(160, report["replays"][0]["alignment_unsupported_reasons"]["insufficient_active_audio"])
        serialized = M.canonical(report)
        for forbidden in (str(self.base).encode(), b"case_id", b"odaq-delivery-", b"encoded_sha256", b"packets"):
            self.assertNotIn(forbidden, serialized)

    def test_different_replay_preserves_negative(self):
        first, second = self.mocked_replay(), self.mocked_replay()
        second["cases"][0]["encoded_sha256"] = "d" * 64
        report = M.summarize([first, second])
        self.assertFalse(report["private_replays_byte_identical"])
        self.assertEqual("technical_negative_or_incomplete", report["state"])

    def test_resource_stop_keeps_all_160_cases(self):
        failing = Mock(side_effect=ValueError("reserved space"))
        replay = M.run_replay(self.records, self.root, self.scratch, self.tools, process_fn=failing)
        self.assertEqual(1, failing.call_count)
        self.assertEqual(160, len(replay["cases"]))
        self.assertTrue(all(item["state"] == "not_run" for item in replay["cases"]))
        self.assertFalse(M.summarize([replay, replay])["all_cases_observed"])

    def test_time_stop_keeps_all_160_cases(self):
        with patch.object(M.time, "monotonic", side_effect=[0, *([4000] * 160)]):
            replay = M.run_replay(self.records, self.root, self.scratch, self.tools, process_fn=Mock(side_effect=AssertionError))
        self.assertTrue(all(item["reason"] == "replay_time_budget" for item in replay["cases"]))

    def test_projection_rejects_missing_duplicate_and_fabricated_cases(self):
        for change in (lambda r: r["cases"].pop(), lambda r: r["cases"].__setitem__(1, r["cases"][0]),
                       lambda r: r["cases"][0]["comparison"].update(transparency=True),
                       lambda r: r["cases"][0]["comparison"]["alignment"]["support"].update(reasons=["private/path"])):
            first, second = self.mocked_replay(), self.mocked_replay()
            change(second)
            with self.assertRaises(ValueError):
                M.summarize([first, second])

    def test_projection_rejects_forged_alignment_support(self):
        first, second = self.mocked_replay(), self.mocked_replay()
        value = second["cases"][0]["comparison"]
        value.update(subtle_technical_support=True)
        value["alignment"].update(status="supported", support={"reasons": []})
        value["alignment"]["alignment"]["summary"]["active_seconds"] = 2.0
        with self.assertRaisesRegex(ValueError, "four active seconds"):
            M.summarize([first, second])


class NativeBindingTest(unittest.TestCase):
    def test_single_and_multiline_licence_declarations_complete(self):
        self.assertEqual('"BSD-3-Clause"', T.licence_declaration('class X\n  license "BSD-3-Clause"\n  head "x"\nend'))
        value = 'all_of: [\n    "GPL-2.0-only", # comment\n    { any_of: ["MIT", "ISC"] },\n  ]'
        self.assertEqual(value, T.licence_declaration('  license ' + value + '\n  head "x"'))

    def test_missing_or_incomplete_licence_fails(self):
        for value in ('  desc "none"', '  license all_of: [\n "MIT"'):
            with self.assertRaises(ValueError):
                T.licence_declaration(value)

    def test_system_cache_is_explicit_not_fake_file_hash(self):
        result = T.resolve_dependency("/usr/lib/libSystem.B.dylib", Path("owner"), Path("executable"))
        self.assertEqual("system:libSystem.B.dylib", result)

    def test_unresolved_dependency_fails(self):
        with self.assertRaises(ValueError):
            T.resolve_dependency("@unknown/unbound.dylib", Path("owner"), Path("executable"))

    def test_no_native_binding_on_wrong_platform(self):
        with patch.object(T.platform, "system", return_value="Linux"), patch.object(T, "metadata") as commands:
            with self.assertRaises(ValueError):
                T.bind_tools({})
            commands.assert_not_called()

    def test_public_native_binding_is_complete_and_metadata_only(self):
        record = M.load_json(M.ROOT / M.BINDING_FILES["native_tools"])
        self.assertEqual({"ffmpeg", "ffprobe", "oggenc", "python"}, set(record["roots"]))
        nodes = {item["sha256"] for item in record["nodes"]}
        packages = {item["id"] for item in record["packages"]}
        self.assertTrue(set(record["roots"].values()) <= nodes)
        for item in record["nodes"]:
            self.assertIn(item["package"], packages)
            self.assertTrue(all(dep in nodes or dep.startswith("system:") for dep in item["dependencies"]))
        self.assertFalse(record["codec_execution_performed"])
        self.assertFalse(record["audio_or_private_manifest_accessed"])
        self.assertGreater(record["python_stdlib"]["file_count"], 0)


if __name__ == "__main__":
    unittest.main()
