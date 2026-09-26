"""One bounded v5 digital plumbing canary under standing technical authority.

Default plan validation reads public records only. Real access requires this
separate committed batch and successful exact-head push CI. No native fallback,
technical correlation or codec history can populate perceptual outputs.
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
import perceptual_degradation_alignment_v5 as alignment
import perceptual_degradation_correlation_global as native
import perceptual_degradation_digital_canary as base
import perceptual_degradation_global_qualification as qualification
import perceptual_degradation_digital_development as old

ROOT = old.ROOT
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/digital-v5-canary-proposal-20260908.json"
AUTHORIZATION = ROOT / "benchmarks/perceptual-degradation-v1/digital-v5-canary-authorization-20260908.json"
PROPOSAL_ID = "digital-v5-canary-20260908-001"
REPLAY_SECONDS = 1200
BINDINGS = {
    "predecessor_plan": str(base.PLAN.relative_to(ROOT)),
    "predecessor_runner": "scripts/perceptual_degradation_digital_canary.py",
    "predecessor_result": "research/toolchains/evidence/perceptual-degradation-digital-canary-20260908-001.json",
    "standing_authorization": "benchmarks/perceptual-degradation-v1/digital-development-standing-authorization-20260908.json",
    "qualification_plan": "benchmarks/perceptual-degradation-v1/alignment-global-workload-plan-20260908.json",
    "qualification_result": "research/toolchains/evidence/perceptual-degradation-alignment-global-synthetic-20260908-001.json",
    "qualification_runner": "scripts/perceptual_degradation_global_qualification.py",
    "alignment_v5": "scripts/perceptual_degradation_alignment_v5.py",
    "native_bridge": "scripts/perceptual_degradation_correlation_global.py",
    "native_source": "scripts/perceptual_degradation_correlation_global.c",
    "included_native_source": "scripts/perceptual_degradation_correlation_native.c",
    "runner": "scripts/perceptual_degradation_digital_canary_v5.py",
    "tests": "scripts/tests/test_perceptual_degradation_digital_canary_v5.py",
    "artifact_auditor": "scripts/perceptual_degradation_digital_canary_v5_artifact_audit.py",
    "artifact_auditor_tests": "scripts/tests/test_perceptual_degradation_digital_canary_v5_artifact_audit.py",
}
GLOBAL_KEYS = {"native_candidates", "fallback_candidates", "short_overlap_candidates",
               "searches", "geometry_sha256", "geometry_rows", "sampled_pair_evaluations"}
SUCCESS = {"all_twelve_cases_observed": True, "completed_evidence_repeated": True,
           "all_four_replay_edges_passed": True, "both_controls_supported_in_both_rounds": True,
           "zero_local_and_global_fallback": True, "all_codec_cases_supported_required": False}

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
             "persistent_derived_pcm_allowed": False, "automatic_retry_allowed": False,
             "exclusive_parent_launch_marker": True, "minimum_workspace_free_gib": 15}
CLAIMS = {key: False for key in ("perceptual_support", "human_calibrated", "source_trait_assignment",
                               "independent_validation", "full_cohort_validation", "training_authorized",
                               "metric_authorized", "playback_authorized", "public_verdict_enabled")}
TIMING_KEYS = {"case", "alignment", "encode", "probe", "decode"}
EDGE_STATES = {"passed", "preflight_failed", "not_attempted_after_stop"}


recipes = base.recipes
conditions = base.conditions
select_record = base.select_record
selected_inventory = base.selected_inventory
verify_selected = base.verify_selected


def qualified_result():
    qualification.load_plan()
    result = old.load_json(ROOT / BINDINGS["qualification_result"])
    for entry in result["bindings"].values():
        if old.binding.sha_file(ROOT / entry["path"]) != entry["sha256"]:
            raise ValueError("audited qualification binding changed")
    observed = result["observations"]
    gates = ("all_slots_completed", "global_candidate_equivalence_passed",
             "all_full_alignments_within_120_seconds", "completed_evidence_repeated",
             "no_native_fallback", "all_inputs_preserved")
    if (result["state"] != "audited_synthetic_workload_margin_passed"
            or observed["state"] != "synthetic_workload_margin_passed"
            or any(observed[key] is not True for key in gates)
            or observed["replay_edges"] != ["passed"] * 4
            or result["integrity"]["independent_saved_artifact_audit_passed"] is not True
            or old.canonical(qualification.aggregate(observed["rounds"], observed["replay_edges"])) != old.canonical(observed)):
        raise ValueError("successful audited synthetic workload required")
    return result


def load_plan():
    predecessor = base.load_plan()  # Immutable transitive source/tool/contract bindings.
    result = qualified_result()
    authority = old.load_json(ROOT / BINDINGS["standing_authorization"])
    if (authority["additional_retained_reference_codec_canaries_authorized"] is not True
            or authority["each_real_audio_batch_requires_committed_hash_bound_protocol_and_exact_head_ci"] is not True):
        raise ValueError("standing bounded technical authority required")
    plan = old.load_json(PLAN)
    expected = {
        "schema_version": 1, "proposal_id": PROPOSAL_ID, "execution_authorized": False,
        "bindings": {key: {"path": path, "sha256": old.binding.sha_file(ROOT / path)}
                     for key, path in BINDINGS.items()},
        "cohort": predecessor["cohort"], "accounting": ACCOUNTING, "selection": SELECTION,
        "recipes": recipes(), "probe_argv": old.PROBE_ARGV, "decode_argv": old.DECODE_ARGV,
        "resources": RESOURCES, "claim_boundary": CLAIMS, "success_criteria": SUCCESS,
        "native_build": {key: value for key, value in result["execution"]["kernel"].items()
                         if key != "binary_sha256"},
        "repeatability": "canonical_private_replay_bytes_excluding_only_each_case_timing_seconds",
        "global_native_audit": "separate_search_inventory_counts_and_canonical_geometry_digest_no_numeric_evidence_exclusions",
        "development_evidence": "same_previously_consumed_largest_reference_not_fresh_independent_validation",
        "runtime_expectation": "synthetic_margin_is_not_a_real_source_or_codec_throughput_guarantee",
    }
    if old.canonical(plan) != old.canonical(expected):
        raise ValueError("exact canary proposal or binding differs")
    for module in (base, old, old.binding, alignment, alignment.legacy, alignment.topology,
                   native, native.local, native.reference, qualification):
        if Path(module.__file__).resolve() != ROOT / "scripts" / (module.__name__ + ".py"):
            raise ValueError("loaded implementation differs")
    return plan


def authorize(plan, ci_run_id):
    if plan["proposal_id"] != PROPOSAL_ID or sys.flags.isolated != 1:
        raise ValueError("exact proposal and isolated Python required")
    expected = {"schema_version": 1, "proposal_id": PROPOSAL_ID,
                "proposal_sha256": old.binding.sha_file(PLAN),
                "runner_sha256": old.binding.sha_file(Path(__file__)),
                "standing_authorization_sha256": old.binding.sha_file(ROOT / BINDINGS["standing_authorization"]),
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


def native_preflight(plan, tools):
    predecessor = old.load_plan()
    expected = old.load_json(ROOT / predecessor["bindings"]["native_tools"]["path"])
    if old.binding.bind_tools(tools) != expected:
        raise ValueError("native runtime closure changed")
    compiler = Path(shutil.which("cc") or "missing-compiler").resolve(strict=True)
    observed = {"compiler_sha256": native.sha(compiler),
                "compiler_version": subprocess.check_output([str(compiler), "--version"], timeout=10).decode().splitlines()[:3],
                "source_sha256": native.sha(native.SOURCE), "included_source_sha256": native.sha(native.local.SOURCE),
                "flags": list(native.FLAGS), "link_libraries": ["m"],
                "platform": platform.system(), "machine": platform.machine(), "os_release": platform.release(),
                "compiler_dependency_closure_claimed": False}
    if observed != plan["native_build"]:
        raise ValueError("qualified native compiler or environment changed")


def empty_case(source, recipe):
    item = old.empty_case(source, recipe)
    item["case_id"] = old.digest((PROPOSAL_ID + ":" + source["opaque_delivery_id"] + ":" + item["recipe_id"]).encode())[:24]
    item.update(native_audit=None, native_global_audit=None, timing_seconds={key: None for key in sorted(TIMING_KEYS)})
    return item


def process_case(source, recipe, root, parent, tools, kernel_path, kernel_sha, *, invoke_fn=old.invoke):
    empty = empty_case(source, recipe)
    timings, audit, global_record = empty["timing_seconds"], None, None
    if alignment.NATIVE_BACKEND is not None or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0):
        raise ValueError("exclusive native backend and alarm required")

    def invoke(argv, files, stage, scratch, deadline):
        began = time.monotonic()
        try:
            return invoke_fn(argv, files, stage, scratch, deadline)
        finally:
            timings[stage] = time.monotonic() - began

    def compare(reference, test, predecessor_case_id, deadline):
        nonlocal audit, global_record
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
            global_record = qualification.global_audit(backend)
            timings["alignment"] = time.monotonic() - began

    began = time.monotonic()
    # Adapt the predecessor's case identity at both the alignment call and result
    # boundary. Its IO, codec argv, PCM conversion and deadlines are unchanged.
    result = old.process_case(source, recipe, root, parent, tools, compare_fn=compare, invoke_fn=invoke)
    timings["case"] = time.monotonic() - began
    result.update(case_id=empty["case_id"], native_audit=audit, native_global_audit=global_record, timing_seconds=timings)
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


def validate_global(audit, *, completed):
    if audit is None:
        if completed:
            raise ValueError("completed global audit missing")
        return
    if not isinstance(audit, dict) or set(audit) != GLOBAL_KEYS:
        raise ValueError("global audit fields differ")
    for key in GLOBAL_KEYS - {"searches", "geometry_sha256"}:
        if type(audit[key]) is not int or audit[key] < 0:
            raise ValueError("invalid global count")
    if (not isinstance(audit["geometry_sha256"], str)
            or not re.fullmatch(r"[0-9a-f]{64}", audit["geometry_sha256"])
            or not isinstance(audit["searches"], list)):
        raise ValueError("global geometry evidence invalid")
    total, seen = 0, set()
    for search in audit["searches"]:
        if (not isinstance(search, dict)
                or set(search) != {"reference_frames", "test_frames", "candidate_count", "search_count"}
                or any(type(v) is not int or v <= 0 for v in search.values())
                or max(search["reference_frames"], search["test_frames"]) > native.MAX_FRAMES):
            raise ValueError("global search inventory invalid")
        key = tuple(search[k] for k in ("reference_frames", "test_frames", "candidate_count"))
        if key in seen:
            raise ValueError("duplicate global search inventory")
        seen.add(key)
        total += search["candidate_count"] * search["search_count"]
    counted = audit["native_candidates"] + audit["short_overlap_candidates"]
    if counted > total or audit["fallback_candidates"] > total:
        raise ValueError("global candidate counts exceed started searches")
    # Fallback may overlap native attempts, or replace an ineligible whole search.
    if completed and not counted <= total <= counted + audit["fallback_candidates"]:
        raise ValueError("completed global candidate accounting incomplete")
    if completed and audit["geometry_rows"] > audit["native_candidates"]:
        raise ValueError("completed global geometry inventory exceeds native candidates")


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
    validate_global(item["native_global_audit"], completed=item["state"] == "observed")
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
            "global_native_candidates": sum(item["native_global_audit"]["native_candidates"] for item in cases if item["native_global_audit"]),
            "global_fallback_candidates": sum(item["native_global_audit"]["fallback_candidates"] for item in cases if item["native_global_audit"]),
            "global_short_overlap_candidates": sum(item["native_global_audit"]["short_overlap_candidates"] for item in cases if item["native_global_audit"]),
            "case_seconds": sum(item["timing_seconds"]["case"] or 0 for item in cases)})
    cases = [item for replay in replays for item in replay["cases"]]
    observed = all(item["state"] == "observed" for item in cases)
    repeat = old.canonical(deterministic(replays[0])) == old.canonical(deterministic(replays[1]))
    edges = all(replay[key] == "passed" for replay in replays for key in ("edge_check_before", "edge_check_after"))
    controls = all(item["comparison"] is not None and item["comparison"]["subtle_technical_support"]
                   for item in cases if item["recipe_id"] in old.CONTROLS)
    no_fallback = observed and all(item[name]["fallback_candidates"] == 0
                                   for item in cases for name in ("native_audit", "native_global_audit"))
    return {"schema_version": 1, "proposal_id": PROPOSAL_ID,
            "state": "bounded_canary_computationally_complete" if observed and repeat and edges else "bounded_canary_negative_or_incomplete",
            "all_cases_observed": observed, "deterministic_evidence_byte_identical": repeat,
            "primary_technical_gate_passed": observed and repeat and edges and controls and no_fallback,
            "timings_excluded_from_repeatability": True, "all_edge_checks_passed": edges,
            "both_controls_technically_supported_both_rounds": controls, "no_native_fallback_all_cases": no_fallback,
            "codec_comparisons_technically_supported": sum(bool(item["comparison"] and item["comparison"]["subtle_technical_support"])
                                                          for item in cases if item["recipe_id"] not in old.CONTROLS),
            "replays": summaries, **CLAIMS, "severity": None, "audibility": None, "artifacts": None, "transparency": None}


def claim_launch(parent, head, ci_run_id):
    old.write_new(parent / (PROPOSAL_ID + ".launch.json"), old.canonical({
        "proposal_id": PROPOSAL_ID, "head": head, "ci_run_id": ci_run_id,
        "proposal_sha256": old.binding.sha_file(PLAN), "automatic_retry_authorized": False}))


def execute(args):
    plan = load_plan()
    head = authorize(plan, args.ci_run_id)  # Before private path/metadata/media access.
    tools = {name: getattr(args, name).resolve(strict=True) for name in ("ffmpeg", "ffprobe", "oggenc")}
    native_preflight(plan, tools)
    root, parent = old.outside_repository(args.source_root), old.outside_repository(args.output_parent)
    if root == parent or root in parent.parents or parent in root.parents:
        raise ValueError("separate private source and output trees required")
    old.reserve(parent)
    old.reserve(ROOT)
    # The marker is consumed even if later preflight/build fails: no automatic retry.
    claim_launch(parent, head, args.ci_run_id)
    source = selected_inventory(root, plan)
    run_root = Path(tempfile.mkdtemp(prefix="lossytrace-digital-v5-canary-", dir=parent))
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
        old.reserve(ROOT)
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
