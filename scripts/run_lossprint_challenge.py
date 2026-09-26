#!/usr/bin/env python3
"""Bounded fixed-baseline challenge and aggregate-only analysis."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time

from audio_integrity_v2_baseline_common import assert_public_path_free, resolve_beneath
from lossprint_challenge import unsupported_reason, write_new
from lossprint_qualification import digest, normalize, invoke, save, SOURCE_HASHES

ROOT = Path(__file__).resolve().parents[1]
BINARY_SHA = "86b45007913a97d0edf252f0f49107dc1e23fbd60e0f3f3d9a8d49c7bbc9b07c"
SELECTION_SHA = "27ffb173d2add8e302753f1f5bf2d730c60a46c414d89ad1c6de97817ef1d7df"


def family(value: str | None) -> str | None:
    return {"aac_lc": "aac", "ffmpeg_aac": "aac", "musepack": "mpc"}.get(value, value)


def command(binary: Path, path: Path) -> list[str]:
    return [str(binary), "--jobs", "1", "--threshold", "0.5", "-o", "jsonl", str(path)]


def analyze(selection: dict, records: list[dict], integrity: bool) -> dict:
    cases = selection["cases"]
    reps = selection["representative_ids"]
    expected = [(r, identity) for r in (1, 2) for identity in reps]
    inventory = [(r["round"], r["case_id"]) for r in records] == expected
    by_slot = {(r["round"], r["case_id"]): r for r in records}
    replay = inventory and all(
        by_slot[(1, identity)]["status"] == by_slot[(2, identity)]["status"]
        and by_slot[(1, identity)].get("output") == by_slot[(2, identity)].get("output")
        for identity in reps)
    outputs = {c["case_id"]: by_slot.get((1, c["representative_case_id"]), {}).get("output")
               for c in cases}
    pcm_outputs = defaultdict(list)
    for r in (1, 2):
        for c in cases:
            row = by_slot.get((r, c["representative_case_id"]), {})
            if row.get("output") is not None:
                pcm_outputs[(r, c["_analysis_pcm_sha256"])].append(row["output"])
    wrappers = all(all(o == values[0] for o in values) for values in pcm_outputs.values())
    by_id = {c["case_id"]: c for c in cases}
    technical = inventory and integrity and replay and wrappers and all(
        (r["status"] == "supported" and r.get("output") is not None)
        or (r["status"] == "unsupported" and unsupported_reason(by_id[r["case_id"]]) is not None)
        for r in records)

    def metrics(rows: list[dict]) -> dict:
        negatives = [c for c in rows if c["expectation"] == "negative"]
        positives = [c for c in rows if c["expectation"] == "controlled_positive"]
        supported_neg = [c for c in negatives if outputs[c["case_id"]] is not None]
        supported_pos = [c for c in positives if outputs[c["case_id"]] is not None]
        flagged = lambda c: outputs[c["case_id"]] is not None and outputs[c["case_id"]]["verdict"] == "transcode"
        detected = [c for c in supported_pos if flagged(c)]
        correct = sum(family(outputs[c["case_id"]]["encoder"]) == family(c.get("codec_family")) for c in detected)
        return {"negative_cases": len(negatives), "positive_cases": len(positives),
                "supported_negative_cases": len(supported_neg), "supported_positive_cases": len(supported_pos),
                "false_alert_cases": sum(flagged(c) for c in negatives), "detected_positive_cases": len(detected),
                "unconditional_positive_coverage": len(detected) / len(positives) if positives else None,
                "supported_recall": len(detected) / len(supported_pos) if supported_pos else None,
                "supported_false_alert_rate": sum(flagged(c) for c in negatives) / len(supported_neg) if supported_neg else None,
                "family_correct_detected_cases": correct,
                "family_accuracy_given_detection": correct / len(detected) if detected else None,
                "joint_family_detection_coverage": correct / len(supported_pos) if supported_pos else None}

    domains = {}
    for domain in sorted({c["source_domain"] for c in cases}):
        rows = [c for c in cases if c["source_domain"] == domain]
        counts = metrics(rows)
        groups = defaultdict(list)
        for c in rows:
            groups[c["source_group"]].append(c)
        pg = ng = spg = sng = detected_groups = alert_groups = partial_pos = partial_neg = 0
        for group in groups.values():
            pos = [c for c in group if c["expectation"] == "controlled_positive"]
            neg = [c for c in group if c["expectation"] == "negative"]
            p_ok = bool(pos) and all(outputs[c["case_id"]] is not None and outputs[c["reference_case_id"]] is not None for c in pos)
            n_ok = bool(neg) and all(outputs[c["case_id"]] is not None for c in neg)
            pg += bool(pos); ng += bool(neg); spg += p_ok; sng += n_ok
            partial_pos += bool(pos) and not p_ok and any(outputs[c["case_id"]] is not None for c in pos)
            partial_neg += bool(neg) and not n_ok and any(outputs[c["case_id"]] is not None for c in neg)
            detected_groups += p_ok and any(outputs[c["case_id"]]["verdict"] == "transcode" for c in pos)
            alert_groups += any(outputs[c["case_id"]] is not None and outputs[c["case_id"]]["verdict"] == "transcode" for c in neg)
        counts.update(positive_groups=pg, negative_groups=ng, supported_positive_groups=spg,
                      supported_negative_groups=sng, partially_supported_positive_groups=partial_pos,
                      partially_supported_negative_groups=partial_neg, detected_supported_positive_groups=detected_groups,
                      negative_alert_groups=alert_groups,
                      continuation_passed=bool(pg and ng and alert_groups == 0 and spg / pg >= .75
                                               and spg and detected_groups / spg >= .8))
        processing = defaultdict(list)
        for c in rows:
            processing["+".join(c.get("post_transform_ids", [])) or "identity"].append(c)
        counts["processing_classes"] = {k: metrics(v) for k, v in sorted(processing.items())}
        domains[domain] = counts
    slices = {}
    for field in ("history_class", "codec_family", "encoder_lineage_id", "encoder_setting_id", "post_transform_ids"):
        buckets = defaultdict(list)
        for c in cases:
            val = c.get(field)
            label = "+".join(val) or "identity" if isinstance(val, list) else (val or "none")
            buckets[label].append(c)
        slices[field] = {k: metrics(v) for k, v in sorted(buckets.items())}
    paired = defaultdict(dict)
    for c in sorted(cases, key=lambda c: (bool(c.get("post_transform_ids")), c["case_id"])):
        if c["expectation"] != "controlled_positive":
            continue
        ref = by_id[c["reference_case_id"]]
        a, b = outputs[c["case_id"]], outputs[ref["case_id"]]
        if a is not None and b is not None:
            key = (c["_analysis_pcm_sha256"], ref["_analysis_pcm_sha256"])
            paired[(c["source_domain"], c["source_group"])].setdefault(key, a["transcode_probability"] - b["transcode_probability"])
    paired_domains = {}
    for domain in domains:
        groups = [values for (d, _), values in paired.items() if d == domain]
        medians = [statistics.median(v.values()) for v in groups]
        paired_domains[domain] = {"supported_groups": len(groups), "unique_within_group_pcm_pairs": sum(map(len, groups)),
                                  "positive_group_median_directions": sum(v > 0 for v in medians),
                                  "median_group_delta": statistics.median(medians) if medians else None}
    result = {"schema_version": 1, "purpose": "consumed_development_external_baseline_falsification_screen",
              "public_verdict_enabled": False, "independent_validation": False,
              "planned_slots": len(expected), "accounted_slots": len(records), "inventory_matches": inventory,
              "status_counts": dict(Counter(r["status"] for r in records)), "integrity_verified": integrity,
              "exact_replay_match": replay, "wrapper_consistency": wrappers, "technical_passed": technical,
              "continuation_passed": technical and all(d["continuation_passed"] for d in domains.values()),
              "case_metrics": metrics(cases), "domains": domains, "slices": slices, "paired": paired_domains,
              "bitrate": {"eligible_cases": 0, "accuracy": None,
                          "reason": "selected manifests have settings but no measured comparable source bitrates"}}
    assert_public_path_free(result)
    return result


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True, timeout=30).strip()


def ci_matches(ci: dict, head: str) -> bool:
    return (ci.get("head_sha") == head and ci.get("status") == "completed"
            and ci.get("conclusion") == "success" and ci.get("path") == ".github/workflows/ci.yml"
            and ci.get("repository", {}).get("full_name") == "ryan-voitiskis/lossytrace")


def run(args) -> None:
    plan = json.loads(args.plan.read_text())
    for relative, expected in plan["repository_bindings"].items():
        if digest(resolve_beneath(ROOT, relative)) != expected:
            raise ValueError("repository binding differs")
    if digest(args.selection) != SELECTION_SHA or digest(args.binary) != BINARY_SHA:
        raise ValueError("selection or binary identity differs")
    if digest(Path(sys.executable).resolve()) != plan["python_executable_sha256"] or platform.platform() != plan["platform"]:
        raise ValueError("runtime closure differs")
    for relative, expected in SOURCE_HASHES.items():
        if digest(resolve_beneath(args.source, relative)) != expected:
            raise ValueError("external source or model identity differs")
    if git("status", "--porcelain"):
        raise ValueError("execution checkout is not clean")
    head = git("rev-parse", "HEAD")
    ci = json.loads(subprocess.check_output(["gh", "api", f"repos/ryan-voitiskis/lossytrace/actions/runs/{args.ci_run}"], text=True, timeout=30))
    if not ci_matches(ci, head):
        raise ValueError("successful exact-head CI is required")
    selection = json.loads(args.selection.read_text())
    cases = selection["cases"]
    by_id = {c["case_id"]: c for c in cases}
    reps = selection["representative_ids"]
    if len(cases) != 717 or len(reps) != 693 or len(set(reps)) != len(reps):
        raise ValueError("selection population differs")
    audio_root = Path(selection["audio_root"])
    paths = {identity: resolve_beneath(audio_root, by_id[identity]["relative_path"]) for identity in reps}
    if args.output.exists() or args.output.is_symlink():
        raise ValueError("refusing to overwrite run")
    if shutil.disk_usage(args.output.parent).free < 15 * 1024 ** 3:
        raise ValueError("free reserve below 15 GiB")
    args.output.mkdir(mode=0o700)
    bindings = {"execution_head": head, "ci_run_id": args.ci_run, "plan_sha256": digest(args.plan),
                "private_selection_sha256": digest(args.selection), "binary_sha256": digest(args.binary),
                "python": sys.version, "platform": platform.platform()}
    write_new(args.output / "preflight.json", bindings)
    records = [{"round": r, "case_id": identity, "status": "not_started"} for r in (1, 2) for identity in reps]
    save(args.output / "records-private.json", records)
    start = time.monotonic()
    failure = None
    try:
        # First waveform access: after immutable selection, repository bindings and CI.
        for identity, path in paths.items():
            if time.monotonic() - start >= 2700:
                raise ValueError("overall deadline during identity preflight")
            if path.stat().st_size != by_id[identity]["audio_bytes"] or digest(path) != by_id[identity]["audio_sha256"]:
                raise ValueError("input artifact identity differs")
        for record in records:
            if failure:
                record["reason"] = failure
                continue
            identity = record["case_id"]
            case = by_id[identity]
            remaining = 2700 - (time.monotonic() - start)
            scratch = sum(p.stat().st_size for p in args.output.iterdir() if p.is_file())
            if remaining <= 0 or shutil.disk_usage(args.output).free < 15 * 1024 ** 3 or scratch >= 1024 ** 3:
                failure = "resource_limit"
                record["reason"] = failure
                continue
            if (reason := unsupported_reason(case)) is not None:
                record.update(status="unsupported", reason=reason)
            else:
                result = invoke(command(args.binary, paths[identity]), min(10, remaining))
                record.update(result)
                try:
                    if result["returncode"] != 0 or result["timeout"] or result["stderr"]:
                        raise ValueError("timeout" if result["timeout"] else "process_failure")
                    record.update(output=normalize(result["stdout"], paths[identity]), status="supported")
                except (ValueError, TypeError) as error:
                    record.update(status="failed", reason=str(error))
                    failure = str(error)
            save(args.output / "records-private.json", records)
        integrity = all(digest(paths[i]) == by_id[i]["audio_sha256"] for i in reps)
        integrity = integrity and digest(args.binary) == BINARY_SHA and digest(args.selection) == SELECTION_SHA
        integrity = integrity and all(digest(resolve_beneath(ROOT, p)) == h for p, h in plan["repository_bindings"].items())
        integrity = integrity and all(digest(resolve_beneath(args.source, p)) == h for p, h in SOURCE_HASHES.items())
        integrity = integrity and git("rev-parse", "HEAD") == head and not git("status", "--porcelain")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        failure = str(error)
        integrity = False
    save(args.output / "records-private.json", records)
    result = analyze(selection, records, bool(integrity))
    result.update(bindings)
    result["elapsed_seconds"] = time.monotonic() - start
    result["private_records_sha256"] = digest(args.output / "records-private.json")
    result["execution_error_present"] = failure is not None
    assert_public_path_free(result)
    write_new(args.output / "aggregate.json", result)
    write_new(args.output / "completion-private.json", {"failure": failure, "integrity": integrity})
    print(json.dumps({k: result[k] for k in ("technical_passed", "continuation_passed", "status_counts", "elapsed_seconds")}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--ci-run", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
