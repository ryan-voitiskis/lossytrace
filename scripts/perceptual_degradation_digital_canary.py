"""One-reference digital plumbing canary; default plan validation opens no media.

Frozen predecessor helpers are reused without modifying their globals or files.
Execution needs a new committed authorization and exact-head successful push CI.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
from pathlib import Path
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import perceptual_degradation_alignment_v4 as alignment
import perceptual_degradation_correlation_native as native
import perceptual_degradation_digital_development as old

ROOT = old.ROOT
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/digital-canary-proposal-20260908.json"
AUTHORIZATION = ROOT / "benchmarks/perceptual-degradation-v1/digital-canary-authorization.json"
PROPOSAL_ID = "digital-native-canary-20260908-001"
REPLAY_SECONDS = 1200
BINDINGS = {
    "predecessor_plan": str(old.PLAN.relative_to(ROOT)),
    "predecessor_runner": "scripts/perceptual_degradation_digital_development.py",
    "qualification_plan": "benchmarks/perceptual-degradation-v1/alignment-native-qualification-plan-20260908.json",
    "qualification_result": "research/toolchains/evidence/perceptual-degradation-alignment-native-synthetic-20260908-001.json",
    "alignment_v4": "scripts/perceptual_degradation_alignment_v4.py",
    "native_bridge": "scripts/perceptual_degradation_correlation_native.py",
    "native_source": "scripts/perceptual_degradation_correlation_native.c",
    "runner": "scripts/perceptual_degradation_digital_canary.py",
    "tests": "scripts/tests/test_perceptual_degradation_digital_canary.py",
}
ACCOUNTING = {"inventory_metadata_members": 16, "waveform_references": 1,
              "codec_conditions": 4, "controls": 2, "cases_per_replay": 6,
              "replays": 2, "total_comparisons": 12, "maximum_encode_decode_pairs": 8}
SELECTION = {"primary": "largest_declared_output_pcm_geometry_frame_count",
             "tie_break": "ascending_opaque_delivery_id", "full_length": True,
             "waveform_selection_permitted": False, "substitution_permitted": False}
RESOURCES = {"workers": 1, "minimum_free_gib": 15, "scratch_allowance_bytes": 12 * old.MAX_FILE,
             "maximum_file_bytes": old.MAX_FILE, "maximum_command_seconds": 60,
             "maximum_case_seconds": 180, "stop_starting_cases_after_replay_seconds": REPLAY_SECONDS,
             "preflight_and_filesystem_overhead_inside_hard_global_timeout": False,
             "persistent_derived_pcm_allowed": False, "automatic_retry_allowed": False}
CLAIMS = {key: False for key in ("perceptual_support", "human_calibrated", "source_trait_assignment",
                               "independent_validation", "full_cohort_validation", "training_authorized",
                               "metric_authorized", "playback_authorized", "public_verdict_enabled")}
TIMING_KEYS = {"case", "alignment", "encode", "probe", "decode"}
EDGE_STATES = {"passed", "preflight_failed", "not_attempted_after_stop"}


def recipes():
    return [old.recipes()[index] for index in (1, 3, 5, 7)]


def conditions():
    return (*old.CONTROLS, *recipes())


def load_plan():
    predecessor = old.load_plan()  # Transitive frozen source/tool/contract bindings.
    plan = old.load_json(PLAN)
    qualification = old.load_json(ROOT / BINDINGS["qualification_plan"])
    for entry in qualification["bindings"].values():
        if old.binding.sha_file(ROOT / entry["path"]) != entry["sha256"]:
            raise ValueError("qualified implementation changed")
    result = old.load_json(ROOT / BINDINGS["qualification_result"])
    expected = {
        "schema_version": 1, "proposal_id": PROPOSAL_ID, "execution_authorized": False,
        "bindings": {key: {"path": path, "sha256": old.binding.sha_file(ROOT / path)}
                     for key, path in BINDINGS.items()},
        "cohort": predecessor["cohort"], "accounting": ACCOUNTING, "selection": SELECTION,
        "recipes": recipes(), "probe_argv": old.PROBE_ARGV, "decode_argv": old.DECODE_ARGV,
        "resources": RESOURCES, "claim_boundary": CLAIMS,
        "native_build": {key: value for key, value in result["observations"]["kernel"].items()
                         if key != "binary_sha256"},
        "repeatability": "canonical_private_replay_bytes_excluding_only_each_case_timing_seconds",
        "conditional_runtime_estimate": {"seconds_per_comparison": 118, "total_seconds": 1416,
                                         "measured_codec_throughput": False},
    }
    if old.canonical(plan) != old.canonical(expected):
        raise ValueError("exact canary proposal or binding differs")
    for module in (old, old.binding, alignment, alignment.legacy, alignment.topology, native, native.reference):
        if Path(module.__file__).resolve() != ROOT / "scripts" / (module.__name__ + ".py"):
            raise ValueError("loaded implementation differs")
    return plan


def authorize(plan, ci_run_id):
    if plan["proposal_id"] != PROPOSAL_ID or sys.flags.isolated != 1:
        raise ValueError("exact proposal and isolated Python required")
    expected = {"schema_version": 1, "proposal_id": PROPOSAL_ID,
                "proposal_sha256": old.binding.sha_file(PLAN),
                "runner_sha256": old.binding.sha_file(Path(__file__)),
                "responsible_user_execution_approved": True,
                "one_selected_reference_two_six_case_replays_authorized": True,
                "metric_playback_listener_training_authorized": False}
    if old.canonical(old.load_json(AUTHORIZATION)) != old.canonical(expected):
        raise ValueError("new exact canary authorization required")
    if not re.fullmatch(r"[1-9][0-9]*", str(ci_run_id)):
        raise ValueError("exact CI run ID required")
    if subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True,
                      check=True, timeout=30).stdout:
        raise ValueError("clean committed checkout required")
    for file in (PLAN, AUTHORIZATION, Path(__file__)):
        committed = subprocess.run(["git", "show", "HEAD:" + str(file.relative_to(ROOT))],
                                   cwd=ROOT, capture_output=True, check=True, timeout=30).stdout
        if committed != file.read_bytes():
            raise ValueError("execution artifact differs from commit")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          check=True, timeout=30).stdout.decode().strip()
    ci = old.command_json(["gh", "run", "view", str(ci_run_id), "--json", "headSha,status,conclusion,workflowName,event"])
    if ci != {"headSha": head, "status": "completed", "conclusion": "success", "workflowName": "CI", "event": "push"}:
        raise ValueError("successful exact execution HEAD push CI required")
    return head


def select_record(records):
    return min(records, key=lambda item: (-item["output_pcm_geometry"]["frame_count"], item["opaque_delivery_id"]))


def selected_inventory(root, plan):
    """Hash-bound metadata selection. Never read any waveform in this function."""
    if {item.name for item in root.iterdir()} != {"delivery.json", "attribution.json", "sources", ".partial"}:
        raise ValueError("exact retained delivery layout required")
    for name in ("sources", ".partial"):
        if (root / name).is_symlink() or not (root / name).is_dir():
            raise ValueError("regular retained directories required")
    if any((root / ".partial").iterdir()):
        raise ValueError("partial delivery is not eligible")
    state, expected = old.load_json(root / "delivery.json"), plan["cohort"]
    records = state.get("completed")
    if not isinstance(records, list) or len(records) != 16:
        raise ValueError("exact 16-member metadata inventory required")
    inventory_sha = old.digest(json.dumps(records, sort_keys=True, separators=(",", ":")).encode())
    for key, value in {"schema_version": 1, "state": "private_delivery_projection_complete",
                       "completed_count": 16, "reference_count": 16, "output_inventory_sha256": inventory_sha,
                       "input_inventory_sha256": expected["original_inventory_sha256"],
                       "authorization_sha256": expected["delivery_authorization_sha256"],
                       "attribution_sha256": expected["attribution_sha256"]}.items():
        if type(state.get(key)) is not type(value) or state[key] != value:
            raise ValueError("retained delivery metadata differs")
    if inventory_sha != expected["delivery_inventory_sha256"]:
        raise ValueError("frozen metadata inventory hash differs")
    for key in ("processed_condition_opened", "listening_score_opened", "perceptual_metric_executed",
                "listener_response_collected", "sealed_evidence_opened", "public_verdict_emitted"):
        if state.get(key) is not False:
            raise ValueError("retained access boundary differs")
    if old.digest(old.bounded_bytes(root / "attribution.json", old.MAX_JSON)) != expected["attribution_sha256"]:
        raise ValueError("attached attribution differs")
    names, sizes, bits, frames = set(), 0, Counter(), []
    for item in records:
        identity = item.get("opaque_delivery_id", "")
        relative = "sources/" + identity + ".wav"
        if (not re.fullmatch(r"odaq-delivery-[0-9a-f]{24}", identity)
                or item.get("relative_path") != relative or identity + ".wav" in names
                or not re.fullmatch(r"[0-9a-f]{64}", item.get("output_sha256", ""))):
            raise ValueError("invalid or duplicate member identity")
        geometry = item["output_pcm_geometry"]
        count, depth = geometry["frame_count"], geometry["bit_depth"]
        if (type(count) is not int or not 0 < count <= old.MAX_FRAMES
                or type(depth) is not int or depth not in (24, 32)
                or old.canonical(geometry) != old.canonical({"sample_rate_hz": old.RATE, "channel_count": 2,
                    "bit_depth": depth, "frame_count": count, "sample_encoding": "signed_integer_pcm",
                    "container_encoding": "riff_wave"})
                or type(item["output_byte_length"]) is not int
                or item["output_byte_length"] != 44 + count * depth // 8 * 2):
            raise ValueError("declared PCM geometry differs")
        file = root / relative
        if file.is_symlink() or not file.is_file():
            raise ValueError("regular source entry required")
        names.add(file.name)
        sizes += item["output_byte_length"]
        bits[str(depth)] += 1
        frames.append(count)
    if ({item.name for item in (root / "sources").iterdir()} != names or sizes != expected["total_bytes"]
            or dict(bits) != expected["bit_depth_counts"] or min(frames) != expected["minimum_frames"]
            or max(frames) != expected["maximum_frames"]):
        raise ValueError("metadata distribution or file inventory differs")
    return select_record(records)


def verify_selected(root, source):
    data = old.bounded_bytes(root / source["relative_path"])
    if len(data) != source["output_byte_length"] or old.digest(data) != source["output_sha256"]:
        raise ValueError("selected reference integrity differs")
    if old.pcm_channels(data)[1] != source["output_pcm_geometry"]:
        raise ValueError("selected reference geometry differs")


def native_preflight(plan, tools):
    predecessor = old.load_plan()
    expected = old.load_json(ROOT / predecessor["bindings"]["native_tools"]["path"])
    if old.binding.bind_tools(tools) != expected:
        raise ValueError("native runtime closure changed")
    compiler = Path(shutil.which("cc") or "missing-compiler").resolve(strict=True)
    observed = {"compiler_sha256": native.sha(compiler),
                "compiler_version": subprocess.check_output([str(compiler), "--version"], timeout=10).decode().splitlines()[:3],
                "source_sha256": native.sha(native.SOURCE), "flags": list(native.FLAGS), "link_libraries": ["m"],
                "platform": platform.system(), "machine": platform.machine(), "os_release": platform.release(),
                "compiler_dependency_closure_claimed": False}
    if observed != plan["native_build"]:
        raise ValueError("qualified native compiler or environment changed")


def empty_case(source, recipe):
    item = old.empty_case(source, recipe)
    item["case_id"] = old.digest((PROPOSAL_ID + ":" + source["opaque_delivery_id"] + ":" + item["recipe_id"]).encode())[:24]
    item.update(native_audit=None, timing_seconds={key: None for key in sorted(TIMING_KEYS)})
    return item


def process_case(source, recipe, root, parent, tools, kernel_path, kernel_sha, *, invoke_fn=old.invoke):
    empty = empty_case(source, recipe)
    timings, audit = empty["timing_seconds"], None
    if alignment.NATIVE_BACKEND is not None or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("exclusive native backend and alarm required")

    def invoke(argv, files, stage, scratch, deadline):
        began = time.monotonic()
        try:
            return invoke_fn(argv, files, stage, scratch, deadline)
        finally:
            timings[stage] = time.monotonic() - began

    def compare(reference, test, predecessor_case_id, deadline):
        nonlocal audit
        backend = native.Kernel(kernel_path, kernel_sha)
        began = time.monotonic()
        try:
            alignment.NATIVE_BACKEND = backend
            with old.analysis_deadline(deadline):
                raw = alignment.align_channels(reference_channels=reference, test_channels=test,
                    reference_channel_map=["L", "R"], test_channel_map=["L", "R"], sample_rate_hz=old.RATE,
                    recipe_identity=empty["case_id"], minimum_active_seconds=4.0, maximum_delay_seconds=2.0)
            return {"alignment": raw, **old.duration_eligibility(raw),
                    "quality_policy": "unchanged_alignment_and_four_eight_second_limits_with_aligned_frame_geometry_cap",
                    "perceptual_support": False, "severity": None, "audibility": None, "artifacts": None, "transparency": None}
        finally:
            alignment.NATIVE_BACKEND = None
            audit = backend.record()
            timings["alignment"] = time.monotonic() - began

    began = time.monotonic()
    # Adapt the predecessor's case identity at both the alignment call and result
    # boundary. Its IO, codec argv, PCM conversion and deadlines are unchanged.
    result = old.process_case(source, recipe, root, parent, tools, compare_fn=compare, invoke_fn=invoke)
    timings["case"] = time.monotonic() - began
    result.update(case_id=empty["case_id"], native_audit=audit, timing_seconds=timings)
    return result


def run_replay(source, root, parent, tools, kernel_path, kernel_sha, *, process_fn=process_case, stopped=None):
    began, cases = time.monotonic(), []
    for recipe in conditions():
        if time.monotonic() - began >= REPLAY_SECONDS:
            stopped = stopped or "replay_time_budget"
        item = empty_case(source, recipe)
        if not stopped:
            try:
                item = process_fn(source, recipe, root, parent, tools, kernel_path, kernel_sha)
            except (ValueError, OSError):
                stopped = "resource_or_preflight_stop"
        if stopped:
            item["reason"] = stopped
        cases.append(item)
    return {"proposal_id": PROPOSAL_ID, "cases": cases,
            "edge_check_before": "passed", "edge_check_after": "passed"}


def validate_case(item):
    if not re.fullmatch(r"[0-9a-f]{24}", item["case_id"]):
        raise ValueError("opaque case identity required")
    timing = item["timing_seconds"]
    if set(timing) != TIMING_KEYS or any(value is not None and
            (type(value) not in (int, float) or not math.isfinite(value) or value < 0) for value in timing.values()):
        raise ValueError("bounded timing fields required")
    if item["state"] not in {"observed", "failed", "not_run"}:
        raise ValueError("unknown case disposition")
    audit = item["native_audit"]
    if audit is not None:
        if set(audit) != {"native_candidates", "fallback_candidates", "searches"}:
            raise ValueError("native audit fields differ")
        if any(type(audit[key]) is not int or audit[key] < 0 for key in ("native_candidates", "fallback_candidates")):
            raise ValueError("invalid native candidate counts")
        for search in audit["searches"]:
            if set(search) != {"window_frames", "stride", "candidate_count", "search_count"} or any(
                    type(value) is not int or value < 0 for value in search.values()):
                raise ValueError("invalid native search inventory")
    comparison = item["comparison"]
    if item["state"] != "observed":
        if item["reason"] not in old.FAILURE_REASONS or comparison is not None:
            raise ValueError("unknown failure or fabricated comparison")
        return
    if item["reason"] is not None or audit is None or timing["case"] is None or timing["alignment"] is None:
        raise ValueError("completed case evidence missing")
    if comparison["perceptual_support"] is not False or any(comparison[key] is not None
            for key in ("severity", "audibility", "artifacts", "transparency")):
        raise ValueError("perceptual outputs must remain null")
    raw = comparison["alignment"]
    if (raw["record_kind"] != alignment.RECORD_KIND or raw["case_id"] != alignment.legacy.case_id(item["case_id"])
            or raw["public_verdict_enabled"] is not False):
        raise ValueError("alignment identity or boundary differs")
    reasons, supported = raw["support"]["reasons"], raw["status"] == "supported"
    if (not isinstance(reasons, list) or any(reason not in old.ALIGNMENT_REASONS for reason in reasons)
            or raw["status"] not in {"supported", "unsupported"} or supported == bool(reasons)):
        raise ValueError("alignment reasons contradict status")
    active, frames = (raw["alignment"]["summary"][key] for key in ("active_seconds", "aligned_frames"))
    if (active is not None and (type(active) not in (int, float) or not math.isfinite(active) or active < 0)
            or frames is not None and (type(frames) is not int or not 0 <= frames <= old.MAX_FRAMES)
            or supported and (active is None or active < 4.0 or frames is None)):
        raise ValueError("alignment duration evidence invalid")
    for key, value in old.duration_eligibility(raw).items():
        if type(comparison[key]) is not type(value) or comparison[key] != value:
            raise ValueError("duration eligibility contradicts alignment")
    for key in ("source_sha256", "adapter_sha256"):
        if not re.fullmatch(r"[0-9a-f]{64}", item[key]):
            raise ValueError("private input integrity missing")
    if item["recipe_id"] in old.CONTROLS:
        if any(item[key] is not None for key in ("encoded_sha256", "decoded_sha256", "packet_geometry")):
            raise ValueError("control must not encode")
    else:
        recipe = next(recipe for recipe in recipes() if recipe["id"] == item["recipe_id"])
        if any(not re.fullmatch(r"[0-9a-f]{64}", item[key]) for key in ("encoded_sha256", "decoded_sha256")):
            raise ValueError("private codec integrity missing")
        old.packet_geometry(item["packet_geometry"], recipe)


def deterministic(replay):
    # Exclude exactly this named per-case performance field, nothing recursively.
    return {**replay, "cases": [{key: value for key, value in item.items() if key != "timing_seconds"}
                                for item in replay["cases"]]}


def summarize(replays):
    order = [item if isinstance(item, str) else item["id"] for item in conditions()]
    if len(replays) != 2:
        raise ValueError("exactly two replays required")
    summaries = []
    for replay in replays:
        cases = replay["cases"]
        if (set(replay) != {"proposal_id", "cases", "edge_check_before", "edge_check_after"}
                or replay["proposal_id"] != PROPOSAL_ID or [item["recipe_id"] for item in cases] != order
                or len({item["case_id"] for item in cases}) != 6
                or any(replay[key] not in EDGE_STATES for key in ("edge_check_before", "edge_check_after"))):
            raise ValueError("every ordered canary case and edge check must remain visible")
        for item in cases:
            validate_case(item)
        comparisons = [item["comparison"] for item in cases if item["comparison"] is not None]
        summaries.append({"planned": 6, "dispositions": dict(sorted(Counter(item["state"] for item in cases).items())),
            "failure_or_stop_reasons": dict(sorted(Counter(item["reason"] for item in cases if item["reason"]).items())),
            "alignment_unsupported_reasons": dict(sorted(Counter(reason for item in comparisons
                                                   for reason in item["alignment"]["support"]["reasons"]).items())),
            "subtle_technically_supported": sum(item["subtle_technical_support"] for item in comparisons),
            "quality_duration_eligible": sum(item["quality_duration_eligible"] for item in comparisons),
            "native_candidates": sum(item["native_audit"]["native_candidates"] for item in cases if item["native_audit"]),
            "fallback_candidates": sum(item["native_audit"]["fallback_candidates"] for item in cases if item["native_audit"]),
            "case_seconds": sum(item["timing_seconds"]["case"] or 0 for item in cases)})
    cases = [item for replay in replays for item in replay["cases"]]
    observed = all(item["state"] == "observed" for item in cases)
    repeat = old.canonical(deterministic(replays[0])) == old.canonical(deterministic(replays[1]))
    edges = all(replay[key] == "passed" for replay in replays for key in ("edge_check_before", "edge_check_after"))
    controls = all(item["comparison"] is not None and item["comparison"]["subtle_technical_support"]
                   for item in cases if item["recipe_id"] in old.CONTROLS)
    no_fallback = observed and all(item["native_audit"]["fallback_candidates"] == 0 for item in cases)
    return {"schema_version": 1, "proposal_id": PROPOSAL_ID,
            "state": "bounded_canary_computationally_complete" if observed and repeat and edges else "bounded_canary_negative_or_incomplete",
            "all_cases_observed": observed, "deterministic_evidence_byte_identical": repeat,
            "timings_excluded_from_repeatability": True, "all_edge_checks_passed": edges,
            "both_controls_technically_supported_both_rounds": controls, "no_native_fallback_all_cases": no_fallback,
            "codec_comparisons_technically_supported": sum(bool(item["comparison"] and item["comparison"]["subtle_technical_support"])
                                                          for item in cases if item["recipe_id"] not in old.CONTROLS),
            "replays": summaries, **CLAIMS, "severity": None, "audibility": None, "artifacts": None, "transparency": None}


def execute(args):
    plan = load_plan()
    head = authorize(plan, args.ci_run_id)  # Before private path/metadata/media access.
    tools = {name: getattr(args, name).resolve(strict=True) for name in ("ffmpeg", "ffprobe", "oggenc")}
    native_preflight(plan, tools)
    root, parent = old.outside_repository(args.source_root), old.outside_repository(args.output_parent)
    if root == parent or root in parent.parents or parent in root.parents:
        raise ValueError("separate private source and output trees required")
    old.reserve(parent)
    source = selected_inventory(root, plan)
    run_root = Path(tempfile.mkdtemp(prefix="lossytrace-digital-canary-", dir=parent))
    kernel_root = run_root / "kernel"
    kernel_root.mkdir(mode=0o700)
    kernel_path, provenance = native.build(kernel_root)
    if {key: value for key, value in provenance.items() if key != "binary_sha256"} != plan["native_build"]:
        raise ValueError("built kernel provenance changed")
    native.Kernel(kernel_path, provenance["binary_sha256"])
    old.write_new(run_root / "execution.json", old.canonical({"head": head, "ci_run_id": args.ci_run_id,
        "proposal_sha256": old.binding.sha_file(PLAN), "selected_source": source, "kernel": provenance}))
    old.write_new(run_root / "attribution.json", old.bounded_bytes(root / "attribution.json", old.MAX_JSON))

    def edge_check():
        load_plan()
        native_preflight(plan, tools)
        old.reserve(run_root)
        if selected_inventory(root, plan) != source:
            raise ValueError("selected metadata changed; no substitution")
        verify_selected(root, source)
        if native.sha(kernel_path) != provenance["binary_sha256"]:
            raise ValueError("native binary changed")

    replays, halted = [], False
    for index in range(2):
        before = "not_attempted_after_stop" if halted else "passed"
        if not halted:
            try:
                edge_check()
            except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
                before, halted = "preflight_failed", True
        replay = run_replay(source, root, run_root, tools, kernel_path, provenance["binary_sha256"],
                            stopped="resource_or_preflight_stop" if halted else None)
        replay["edge_check_before"] = before
        replay["edge_check_after"] = "not_attempted_after_stop" if halted else "passed"
        if not halted:
            try:
                edge_check()
            except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError):
                replay["edge_check_after"], halted = "preflight_failed", True
        # A replay resource/time stop is terminal, not an invitation to start over.
        halted = halted or any(item["state"] == "not_run" for item in replay["cases"])
        old.write_new(run_root / f"replay-{index + 1}.json", old.canonical(replay))
        replays.append(replay)
    report = summarize(replays)
    old.write_new(run_root / "public-projection.json", old.canonical(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan")
    live = commands.add_parser("run")
    for name in ("source-root", "output-parent", "ffmpeg", "ffprobe", "oggenc"):
        live.add_argument("--" + name, type=Path, required=True)
    live.add_argument("--ci-run-id", required=True)
    args = parser.parse_args()
    if args.command == "plan":
        result = {"proposal_id": PROPOSAL_ID, "execution_authorized": False, "accounting": load_plan()["accounting"]}
    else:
        result = execute(args)
    sys.stdout.buffer.write(old.canonical(result))


if __name__ == "__main__":
    main()
