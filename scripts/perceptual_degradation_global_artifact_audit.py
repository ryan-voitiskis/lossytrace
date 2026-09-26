"""Independent saved-artifact accounting and construction-hash audit.

No real waveform access, codec, alignment or native execution. Synthetic input
hashes are reconstructed from the frozen integer/float recipe after the timed
batch ends; arrays are never written. The runner validator is an extra check.
"""
import argparse
from array import array
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys

HEAD = "93c5607005801a4cce34d8454b2d20b2d26a8c4a"
PLAN_SHA = "12def738f8b9b697f14a3c54690080daaf90baf9fada2fe718f54b5a6ecfd6bf"
TIMING = {"wall_seconds", "cpu_seconds", "stage_wall_seconds", "stage_cpu_seconds", "other_wall_seconds", "other_cpu_seconds"}
CASES = [f"{family}:{mode}" for family in ("quantized", "dense_float", "mixed_scale", "sparse_bursts") for mode in ("global_pair", "full_native")]


def canonical(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+"\n").encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def construction_hash(family, frames=576008):
    left, right = array("d"), array("d")
    if family == "quantized":
        state = 0x35A719C3
        for pair_index in range((frames+1)//2):
            pair = []
            for _ in range(2):
                state = (1664525*state+1013904223) & 0xffffffff
                pair.append((((state>>16) & 1023)-512)*32*(1+(pair_index//137)%5)/1048576)
            left.extend(pair)
            right.extend((-pair[1], pair[0]))
        del left[frames:]
        del right[frames:]
    else:
        state = 0x56842139D30A0F71
        for frame in range(frames):
            for channel, destination in enumerate((left, right)):
                state = (6364136223846793005*state+1442695040888963407) & 0xffffffffffffffff
                value = ((state>>11)/9007199254740992-.5)*.25
                factor = (1+(frame//137+channel)%5)/5
                value = value*factor
                if family == "mixed_scale":
                    value = math.ldexp(value, -((frame+channel*7)%41))
                elif family == "sparse_bursts" and (frame//2400)%5 != 0:
                    value = 0.0
                destination.append(value)
    if sys.byteorder != "little":
        left.byteswap()
        right.byteswap()
    digest = hashlib.sha256(left.tobytes())
    digest.update(right.tobytes())
    return digest.hexdigest()


def reconstruct(rounds, edges):
    assert len(rounds) == 2 and all([r["case"] for r in rows] == CASES for rows in rounds)
    rows = [r for group in rounds for r in group]
    complete = all(r["outcome"] == "completed" for r in rows)
    by_case = {}
    repeated = []
    for case in CASES:
        a, b = (next(r for r in group if r["case"] == case) for group in rounds)
        pair_complete = a["outcome"] == b["outcome"] == "completed"
        same = canonical({k:v for k,v in a.items() if k not in TIMING}) == canonical({k:v for k,v in b.items() if k not in TIMING}) if pair_complete else None
        repeated.append({"case": case, "outcome_equal": a["outcome"] == b["outcome"], "completed_evidence_byte_identical": same})
        by_case[case] = [a, b]
    global_rows = [r for r in rows if r["case"].split(":")[1] == "global_pair"]
    full_rows = [r for r in rows if r["case"].split(":")[1] == "full_native"]
    equality = all(r["outcome"] == "completed" and r["component"]["all_candidate_records_byte_identical"]
                   and r["component"]["predecessor_sha256"] == r["component"]["successor_sha256"]
                   and r["component"]["global_candidates"] == 3848 for r in global_rows)
    margin = all(r["outcome"] == "completed" and r["wall_seconds"] <= 120 for r in full_rows)
    replay_ok = all(r["completed_evidence_byte_identical"] is True for r in repeated)
    fallback_ok = complete and not sum(r[name]["fallback_candidates"] for r in rows for name in ("global_native", "local_native"))
    input_ok = complete and all(r["inputs_unchanged"] for r in rows)
    passed = complete and equality and margin and replay_ok and fallback_ok and input_ok and edges == ["passed"]*4
    return {"schema_version":1, "plan_id":"alignment-global-workload-20260908-001", "planned_slots":16,
            "state":"synthetic_workload_margin_passed" if passed else "synthetic_workload_negative_or_incomplete",
            "all_slots_completed":complete, "global_candidate_equivalence_passed":equality,
            "all_full_alignments_within_120_seconds":margin, "completed_evidence_repeated":replay_ok,
            "no_native_fallback":fallback_ok, "all_inputs_preserved":input_ok,
            "replay_edges":edges, "repeatability":repeated, "rounds":rounds,
            "real_audio_accessed":False, "codec_executed":False, "perceptual_support":False,
            "full_rate_pipeline_qualified":False, "public_verdict_enabled":False, "objective_complete":False}


def regular(path, mode, maximum=4*1024**2):
    assert path.is_file() and not path.is_symlink() and path.stat().st_mode & 0o777 == mode
    assert 0 < path.stat().st_size <= maximum
    return path.read_bytes()


def audit(repo, run, first_sha=None):
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo).decode().strip() == HEAD
    assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=repo)
    sys.path.insert(0, str(repo/"scripts"))
    import perceptual_degradation_global_qualification as module
    plan = module.load_plan()
    assert sha(module.PLAN.read_bytes()) == PLAN_SHA
    assert not run.is_symlink() and run.stat().st_mode & 0o777 == 0o700
    assert {p.name for p in run.iterdir()} == {"execution.json", "round-1.json", "round-2.json", "result.json", "kernel"}
    assert (run/"kernel").is_dir() and not (run/"kernel").is_symlink()
    assert (run/"kernel").stat().st_mode & 0o777 == 0o700
    assert {p.name for p in (run/"kernel").iterdir()} == {"correlation.dylib"}
    names = ("execution.json", "round-1.json", "round-2.json", "result.json")
    saved = {name: regular(run/name, 0o600) for name in names}
    parsed = {name: json.loads(value) for name, value in saved.items()}
    assert all(canonical(parsed[name]) == saved[name] for name in names)
    execution = parsed["execution.json"]
    assert execution["head"] == HEAD and execution["plan_sha256"] == PLAN_SHA
    assert execution["synthetic_only"] is True and execution["locally_preregistered"] is True and execution["externally_preregistered"] is False
    assert {k:v for k,v in execution["kernel"].items() if k != "binary_sha256"} == plan["native_build"]
    assert sha(regular(run/"kernel/correlation.dylib", 0o500)) == execution["kernel"]["binary_sha256"]
    if first_sha is not None:
        assert sha(saved["round-1.json"]) == first_sha
    rounds = [parsed[f"round-{i}.json"] for i in (1, 2)]
    result = parsed["result.json"]
    derived = reconstruct(rounds, result["replay_edges"])
    assert canonical(derived) == saved["result.json"]
    assert canonical(module.aggregate(rounds, result["replay_edges"])) == saved["result.json"]
    hashes = {family: construction_hash(family) for family in ("quantized", "dense_float", "mixed_scale", "sparse_bursts")}
    observed = [row for group in rounds for row in group if "input_sha256" in row]
    for row in observed:
        assert row["input_sha256"] == hashes[row["case"].split(":")[0]] and row["inputs_unchanged"] is True
        for dimension in ("wall", "cpu"):
            assert all(math.isfinite(v) and v >= 0 for v in row[f"stage_{dimension}_seconds"].values())
            assert sum(row[f"stage_{dimension}_seconds"].values()) <= row[f"{dimension}_seconds"]+.01
    return {"schema_version":1, "independent_saved_artifact_audit_passed":True,
            "execution_head":HEAD, "plan_sha256":PLAN_SHA,
            "first_round_snapshot_matched":first_sha is not None,
            "exact_private_retention_boundary_passed":True, "waveform_or_array_files_retained":False,
            "native_executed_by_auditor":False, "alignment_executed_by_auditor":False,
            "synthetic_construction_hashes_independently_reconstructed":4,
            "recorded_input_hashes_verified":len(observed),
            "report_sha256":{name:sha(value) for name,value in saved.items()},
            "public_result":derived, "audit_helper_sha256":sha(Path(__file__).read_bytes())}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--first-sha")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.repo, args.run, args.first_sha)
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(canonical(result))
    print(json.dumps({k:result[k] for k in ("independent_saved_artifact_audit_passed", "recorded_input_hashes_verified", "exact_private_retention_boundary_passed", "first_round_snapshot_matched")}))
