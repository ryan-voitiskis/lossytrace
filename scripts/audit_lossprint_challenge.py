#!/usr/bin/env python3
"""Independently audit a completed fixed challenge without re-running inference."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path


def digest(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit(selection_path: Path, run: Path) -> dict:
    require(digest(selection_path) == "27ffb173d2add8e302753f1f5bf2d730c60a46c414d89ad1c6de97817ef1d7df", "selection differs")
    selection = json.loads(selection_path.read_text())
    rows = json.loads((run / "records-private.json").read_text())
    aggregate = json.loads((run / "aggregate.json").read_text())
    preflight = json.loads((run / "preflight.json").read_text())
    completion = json.loads((run / "completion-private.json").read_text())
    require(completion == {"failure": None, "integrity": True}, "execution not technically complete")
    require(aggregate["private_records_sha256"] == digest(run / "records-private.json"), "records binding differs")
    require(all(aggregate[k] == v for k, v in preflight.items()), "preflight binding differs")
    cases = {c["case_id"]: c for c in selection["cases"]}
    ids = selection["representative_ids"]
    require(len(cases) == 717 and len(ids) == 693 and len(set(ids)) == 693, "population differs")
    require([(r["round"], r["case_id"]) for r in rows] == [(n, i) for n in (1, 2) for i in ids], "record order differs")
    results = {}
    audio_root = Path(selection["audio_root"]).resolve()
    for row in rows:
        require(row["status"] == "supported" and row["returncode"] == 0 and not row["timeout"] and not row["stderr"], "unsupported or failed slot")
        case = cases[row["case_id"]]
        path = (audio_root / case["relative_path"]).resolve()
        path.relative_to(audio_root)
        require(0 <= row["elapsed_seconds"] <= 10, "slot deadline exceeded")
        output = json.loads(row["stdout"])
        require(output.pop("path") == str(path), "output identity differs")
        require(set(output) == {"transcode_probability", "verdict", "encoder", "bitrate_kbps"}, "output schema differs")
        score = output["transcode_probability"]
        require(type(score) in (int, float) and 0 <= score <= 1, "score invalid")
        flag = score >= .5
        require(output["verdict"] == ("transcode" if flag else "clean"), "threshold interpretation differs")
        if not flag:
            require(output["encoder"] is None and output["bitrate_kbps"] is None, "conditional fields differ")
        else:
            require(output["encoder"] in {"mp3", "ffmpeg_aac", "vorbis", "opus", "wma", "mp2", "musepack"}, "unknown family")
            require(type(output["bitrate_kbps"]) in (int, float) and 0 < output["bitrate_kbps"] < float("inf"), "bitrate invalid")
        require(output == row["output"], "saved normalized output differs")
        results[(row["round"], row["case_id"])] = output
        if row["round"] == 1:
            require(path.stat().st_size == case["audio_bytes"] and digest(path) == case["audio_sha256"], "retained input differs")
    require(all(results[(1, i)] == results[(2, i)] for i in ids), "replay mismatch")
    pcm = {}
    outputs = {}
    for c in cases.values():
        output = results[(1, c["representative_case_id"])]
        outputs[c["case_id"]] = output
        previous = pcm.setdefault(c["_analysis_pcm_sha256"], output)
        require(previous == output, "equal PCM wrappers disagree")
    domains = {}
    total_false = total_detected = total_correct = 0
    for domain in sorted({c["source_domain"] for c in cases.values()}):
        groups = defaultdict(list)
        negatives = []
        positives = []
        for c in cases.values():
            if c["source_domain"] == domain:
                groups[c["source_group"]].append(c)
                (negatives if c["expectation"] == "negative" else positives).append(c)
        flagged = lambda c: outputs[c["case_id"]]["transcode_probability"] >= .5
        false = sum(flagged(c) for c in negatives)
        detected = sum(flagged(c) for c in positives)
        family = lambda value: {"ffmpeg_aac": "aac", "aac_lc": "aac", "musepack": "mpc"}.get(value, value)
        correct = sum(flagged(c) and family(outputs[c["case_id"]]["encoder"]) == family(c.get("codec_family")) for c in positives)
        negative_groups = sum(any(c["expectation"] == "negative" and flagged(c) for c in cs) for cs in groups.values())
        positive_groups = sum(any(c["expectation"] == "controlled_positive" and flagged(c) for c in cs) for cs in groups.values())
        negative_total = sum(any(c["expectation"] == "negative" for c in cs) for cs in groups.values())
        positive_total = sum(any(c["expectation"] == "controlled_positive" for c in cs) for cs in groups.values())
        require(len(groups) == 5, "domain group count differs")
        actual = aggregate["domains"][domain]
        expected = {"negative_cases": len(negatives), "positive_cases": len(positives),
                    "false_alert_cases": false, "detected_positive_cases": detected,
                    "family_correct_detected_cases": correct, "negative_alert_groups": negative_groups,
                    "detected_supported_positive_groups": positive_groups,
                    "supported_positive_groups": positive_total, "supported_negative_groups": negative_total,
                    "continuation_passed": bool(negative_total and positive_total and negative_groups == 0 and positive_groups / positive_total >= .8)}
        require(all(actual[k] == v for k, v in expected.items()), "domain aggregate differs")
        domains[domain] = expected
        total_false += false; total_detected += detected; total_correct += correct
    require(aggregate["case_metrics"]["negative_cases"] == 336 and aggregate["case_metrics"]["positive_cases"] == 381, "label counts differ")
    require(aggregate["case_metrics"]["false_alert_cases"] == total_false and aggregate["case_metrics"]["detected_positive_cases"] == total_detected, "total counts differ")
    require(aggregate["case_metrics"]["family_correct_detected_cases"] == total_correct, "family count differs")
    require(aggregate["continuation_passed"] == all(d["continuation_passed"] for d in domains.values()), "continuation decision differs")
    require(aggregate["technical_passed"] and aggregate["exact_replay_match"] and aggregate["wrapper_consistency"], "technical summary differs")
    return {"schema_version": 1, "purpose": "independent_saved_output_audit_no_new_inference",
            "passed": True, "execution_head": aggregate["execution_head"], "ci_run_id": aggregate["ci_run_id"],
            "aggregate_sha256": digest(run / "aggregate.json"), "private_records_sha256": digest(run / "records-private.json"),
            "selection_sha256": digest(selection_path), "auditor_sha256": digest(__file__),
            "verified_slots": len(rows), "verified_artifacts": len(ids), "verified_pcm_identities": len(pcm),
            "false_alert_cases": total_false, "detected_positive_cases": total_detected,
            "family_correct_detected_cases": total_correct, "domains": domains,
            "continuation_passed": aggregate["continuation_passed"], "public_verdict_enabled": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.selection, args.run)
    with args.output.open("x") as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write("\n")
    print(json.dumps(result, indent=2, sort_keys=True))
