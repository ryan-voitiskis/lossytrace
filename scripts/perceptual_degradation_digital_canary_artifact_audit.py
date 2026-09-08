"""Independent accounting/readback audit; no codec, native build or playback.

The frozen validator is an additional check, not the aggregate implementation.
Real audit reads only saved reports, delivery metadata and the selected WAV bytes.
"""
import argparse
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def regular(file, maximum=16 * 1024 ** 2):
    assert file.is_file() and not file.is_symlink()
    assert 0 < file.stat().st_size <= maximum
    data = file.read_bytes()
    assert len(data) <= maximum
    return data


def deterministic(replay):
    result = copy.deepcopy(replay)
    for case in result["cases"]:
        del case["timing_seconds"]
    return result


def derive(module, replays, selected):
    plan = module.load_plan()
    order = ["identity", "float32_adapter"] + [r["id"] for r in plan["recipes"]]
    assert len(replays) == 2
    summaries = []
    for replay in replays:
        assert set(replay) == {"proposal_id", "cases", "edge_check_before", "edge_check_after"}
        assert replay["proposal_id"] == plan["proposal_id"]
        assert [case["recipe_id"] for case in replay["cases"]] == order
        for case in replay["cases"]:
            expected = sha((plan["proposal_id"] + ":" + selected["opaque_delivery_id"] + ":" + case["recipe_id"]).encode())[:24]
            assert case["case_id"] == expected
            module.validate_case(case)
            if "source_sha256" in case:
                assert case["source_sha256"] == selected["output_sha256"]
                assert case["input_geometry"] == selected["output_pcm_geometry"]
            if case["recipe_id"] in order[:2]:
                assert all(case[key] is None for key in ("encoded_sha256", "decoded_sha256", "packet_geometry"))
            comparison, native = case["comparison"], case["native_audit"]
            if comparison is not None:
                raw = comparison["alignment"]
                active, frames = raw["alignment"]["summary"]["active_seconds"], raw["alignment"]["summary"]["aligned_frames"]
                cap = min(active, frames / 48000) if active is not None and frames is not None else None
                supported = raw["status"] == "supported"
                assert comparison["active_seconds_bounded_by_geometry"] == cap
                assert comparison["subtle_technical_support"] is (supported and cap is not None and cap >= 4)
                assert comparison["quality_duration_eligible"] is (supported and cap is not None and cap >= 8)
                assert all(comparison[key] is None for key in ("severity", "audibility", "artifacts", "transparency"))
                assert comparison["perceptual_support"] is False
            if case["state"] == "observed" and native["fallback_candidates"] == 0:
                assert native["native_candidates"] == sum(row["candidate_count"] * row["search_count"] for row in native["searches"])
        comparisons = [case["comparison"] for case in replay["cases"] if case["comparison"] is not None]
        summaries.append({
            "planned": 6,
            "dispositions": dict(sorted(Counter(case["state"] for case in replay["cases"]).items())),
            "failure_or_stop_reasons": dict(sorted(Counter(case["reason"] for case in replay["cases"] if case["reason"]).items())),
            "alignment_unsupported_reasons": dict(sorted(Counter(reason for c in comparisons for reason in c["alignment"]["support"]["reasons"]).items())),
            "subtle_technically_supported": sum(c["subtle_technical_support"] for c in comparisons),
            "quality_duration_eligible": sum(c["quality_duration_eligible"] for c in comparisons),
            "native_candidates": sum(c["native_audit"]["native_candidates"] for c in replay["cases"] if c["native_audit"]),
            "fallback_candidates": sum(c["native_audit"]["fallback_candidates"] for c in replay["cases"] if c["native_audit"]),
            "case_seconds": sum(c["timing_seconds"]["case"] or 0 for c in replay["cases"]),
        })
    cases = [c for r in replays for c in r["cases"]]
    observed = all(c["state"] == "observed" for c in cases)
    repeated = canonical(deterministic(replays[0])) == canonical(deterministic(replays[1]))
    edges = all(r[k] == "passed" for r in replays for k in ("edge_check_before", "edge_check_after"))
    result = {
        "schema_version": 1, "proposal_id": plan["proposal_id"],
        "state": "bounded_canary_computationally_complete" if observed and repeated and edges else "bounded_canary_negative_or_incomplete",
        "all_cases_observed": observed, "deterministic_evidence_byte_identical": repeated,
        "timings_excluded_from_repeatability": True, "all_edge_checks_passed": edges,
        "both_controls_technically_supported_both_rounds": all(c["comparison"] is not None and c["comparison"]["subtle_technical_support"] for c in cases if c["recipe_id"] in order[:2]),
        "no_native_fallback_all_cases": observed and all(c["native_audit"]["fallback_candidates"] == 0 for c in cases),
        "codec_comparisons_technically_supported": sum(bool(c["comparison"] and c["comparison"]["subtle_technical_support"]) for c in cases if c["recipe_id"] not in order[:2]),
        "replays": summaries, **plan["claim_boundary"],
        "severity": None, "audibility": None, "artifacts": None, "transparency": None,
    }
    assert canonical(module.summarize(replays)) == canonical(result)
    encoded = canonical(result)
    assert not re.search(rb"/Users/|/Volumes/|odaq-delivery-[0-9a-f]{24}|[0-9a-f]{64}", encoded)
    for case in cases:
        assert case["case_id"].encode() not in encoded
    return result


def audit(module, run, source_root, ci, head):
    assert set(p.name for p in run.iterdir()) == {"execution.json", "attribution.json", "replay-1.json", "replay-2.json", "public-projection.json", "kernel"}
    assert not run.is_symlink() and not (run / "kernel").is_symlink()
    assert {p.name for p in (run / "kernel").iterdir()} == {"correlation.dylib"}
    saved = {name: regular(run / name) for name in ("execution.json", "attribution.json", "replay-1.json", "replay-2.json", "public-projection.json")}
    execution = json.loads(saved["execution.json"])
    assert set(execution) == {"head", "ci_run_id", "proposal_sha256", "selected_source", "kernel"}
    assert execution["head"] == head and str(execution["ci_run_id"]) == str(ci)
    assert execution["proposal_sha256"] == sha(module.PLAN.read_bytes())
    plan = module.load_plan()
    assert {k: v for k, v in execution["kernel"].items() if k != "binary_sha256"} == plan["native_build"]
    assert sha(regular(run / "kernel/correlation.dylib")) == execution["kernel"]["binary_sha256"]
    metadata_bytes = regular(source_root / "delivery.json")
    metadata = json.loads(metadata_bytes)
    records = metadata["completed"]
    assert len(records) == 16
    assert sha(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()) == plan["cohort"]["delivery_inventory_sha256"]
    selected = min(records, key=lambda r: (-r["output_pcm_geometry"]["frame_count"], r["opaque_delivery_id"]))
    assert execution["selected_source"] == selected
    assert re.fullmatch(r"odaq-delivery-[0-9a-f]{24}", selected["opaque_delivery_id"])
    assert selected["relative_path"] == "sources/" + selected["opaque_delivery_id"] + ".wav"
    assert saved["attribution.json"] == regular(source_root / "attribution.json")
    assert sha(saved["attribution.json"]) == plan["cohort"]["attribution_sha256"]
    waveform = regular(source_root / selected["relative_path"], 32 * 1024 ** 2)
    assert len(waveform) == selected["output_byte_length"] and sha(waveform) == selected["output_sha256"]
    replays = [json.loads(saved[f"replay-{i}.json"]) for i in (1, 2)]
    for i, replay in enumerate(replays, 1):
        assert canonical(replay) == saved[f"replay-{i}.json"]
    result = derive(module, replays, selected)
    assert saved["public-projection.json"] == canonical(result)
    assert regular(source_root / "delivery.json") == metadata_bytes
    return {"schema_version": 1, "independent_artifact_audit_passed": True,
            "execution_head": head, "ci_run_id": str(ci), "public_projection": result,
            "private_report_sha256": {name: sha(data) for name, data in saved.items()},
            "deterministic_replay_sha256": [sha(canonical(deterministic(r))) for r in replays],
            "selected_source_preserved": True, "other_15_waveforms_read_by_auditor": False,
            "exact_retention_boundary_passed": True, "derived_audio_retained": False,
            "audit_helper_sha256": sha(Path(__file__).read_bytes())}


def self_test(module):
    sys.path.insert(0, str(module.ROOT / "scripts/tests"))
    from test_perceptual_degradation_digital_canary import CanaryTest
    test = CanaryTest()
    test.setUp()
    try:
        replays = [test.replay(), test.replay()]
        assert derive(module, replays, test.source)["deterministic_evidence_byte_identical"]
        changed = copy.deepcopy(replays)
        changed[1]["cases"][0]["timing_seconds"]["case"] += 1
        assert derive(module, changed, test.source)["deterministic_evidence_byte_identical"]
        changed[1]["cases"][2]["decoded_sha256"] = "d" * 64
        assert not derive(module, changed, test.source)["deterministic_evidence_byte_identical"]
        failed = copy.deepcopy(replays)
        for replay in failed:
            replay["cases"][0].update(state="failed", reason="alignment_timeout", comparison=None)
            replay["cases"][0]["native_audit"]["native_candidates"] = 7
        negative = derive(module, failed, test.source)
        assert negative["state"] == "bounded_canary_negative_or_incomplete"
        assert negative["deterministic_evidence_byte_identical"] and not negative["all_cases_observed"]
        for mutation in (lambda r: r[0]["cases"].pop(),
                         lambda r: r[0]["cases"][0].update(case_id="f" * 24),
                         lambda r: r[0]["cases"][0].update(source_sha256="f" * 64),
                         lambda r: r[0]["cases"][0]["comparison"].update(severity=0),
                         lambda r: r[0]["cases"][0]["native_audit"].update(native_candidates=13)):
            changed = copy.deepcopy(replays)
            mutation(changed)
            try:
                derive(module, changed, test.source)
            except (AssertionError, ValueError):
                pass
            else:
                raise AssertionError("mutated audit fixture accepted")
        print(json.dumps({"constructed_audit_checks_passed": 9, "real_audio_or_codec_accessed": False}))
    finally:
        test.tearDown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--run", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--ci-run-id")
    parser.add_argument("--head")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo / "scripts"))
    import perceptual_degradation_digital_canary as module
    if args.self_test:
        self_test(module)
    else:
        assert sys.flags.isolated == 1
        assert module.authorize(module.load_plan(), args.ci_run_id) == args.head
        result = audit(module, args.run, args.source_root, args.ci_run_id, args.head)
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(result))
        print(json.dumps({k: result[k] for k in ("independent_artifact_audit_passed", "exact_retention_boundary_passed", "selected_source_preserved", "other_15_waveforms_read_by_auditor", "derived_audio_retained")}))
