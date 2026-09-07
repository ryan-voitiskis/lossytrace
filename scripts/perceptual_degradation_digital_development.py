"""Exact ODAQ16 digital technical study; real execution is separately gated.

The default command only validates public plans. Tests use constructed arrays
and mocked codec boundaries. No metric, playback, network media or training API.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))
import perceptual_degradation_alignment_v3 as alignment
import perceptual_degradation_digital_tools as binding


ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "benchmarks/perceptual-degradation-v1/digital-development-execution-proposal-20260908.json"
AUTHORIZATION = ROOT / "benchmarks/perceptual-degradation-v1/digital-development-execution-authorization.json"
PROPOSAL_ID = "odaq16-digital-technical-20260908-001"
RATE = 48000
MIN_FREE = 15 * 1024**3
MAX_FILE = 32 * 1024**2
MAX_JSON = 2 * 1024**2
MAX_FRAMES = 576008
COMMAND_SECONDS = 60
CASE_SECONDS = 180
REPLAY_SECONDS = 3600
CONTROLS = ("identity", "float32_adapter")
BINDING_FILES = {
    "amendment": "benchmarks/perceptual-degradation-v1/digital-development-sequence-amendment-20260907.json",
    "reference_delivery": "benchmarks/perceptual-degradation-v1/odaq-reference-delivery-result-20260814.json",
    "candidate_inventory": "benchmarks/perceptual-degradation-v1/source-condition-qualification-plan.json",
    "oracle_contract": "benchmarks/perceptual-degradation-v1/oracle-validity-integration-plan.json",
    "alignment_v1": "scripts/perceptual_degradation_alignment.py",
    "alignment_v2": "scripts/perceptual_degradation_alignment_v2.py",
    "alignment_v3": "scripts/perceptual_degradation_alignment_v3.py",
    "runner": "scripts/perceptual_degradation_digital_development.py",
    "tool_binding_implementation": "scripts/perceptual_degradation_digital_tools.py",
    "attribution_audit": "research/toolchains/evidence/perceptual-degradation-odaq-attribution-audit-20260804-001.json",
    "native_tools": "research/toolchains/evidence/perceptual-degradation-digital-native-tools-20260908-001.json",
    "runner_tests": "scripts/tests/test_perceptual_degradation_digital_development.py",
}
FAILURE_REASONS = {"case_time_budget", "case_integrity_or_structure", "decoder_frame_geometry", "decoder_nonfinite",
                   "encoded_stream_inventory", "encoded_channel_or_rate_geometry", "encoded_timebase",
                   "encoded_packet_structure", "encoded_packet_timestamps", "encoded_packet_side_data",
                   "alignment_timeout", "replay_time_budget", "resource_or_preflight_stop", "inventory_changed_between_replays"}
FAILURE_REASONS.update(stage + suffix for stage in ("encode", "probe", "decode") for suffix in ("_timeout", "_failed", "_metadata_bound"))
ALIGNMENT_REASONS = {"invalid_numeric_input", "no_valid_coarse_correlation", "no_valid_sample_correlation",
                     "fractional_peak_unavailable", "ambiguity_margin_unavailable", "ambiguous_alignment_peak",
                     "insufficient_active_audio", "low_alignment_correlation", "drift_windows_unavailable",
                     "structural_windows_unavailable", "low_structural_window_correlation", "clock_drift_exceeds_limit",
                     "nonlinear_drift", "structural_edit_suspected", "gain_or_polarity_unavailable", "gain_exceeds_limit",
                     "excessive_trim", "invalid_channel_shape", "unsupported_channel_map", "channel_topology_mismatch",
                     "channel_map_mismatch", "channel_alignment_disagreement"}
ENV = {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C", "TZ": "UTC",
       "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1"}


class CaseFailure(ValueError):
    """A stable reason code, never a command, source identity or private path."""


def canonical(value):
    return binding.canonical(value)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def recipes():
    result = []
    settings = [("mp3", "libmp3lame", "96k"), ("mp3", "libmp3lame", "128k"),
                ("aac_lc", "aac", "96k"), ("aac_lc", "aac", "128k"),
                ("opus", "libopus", "64k"), ("opus", "libopus", "128k"),
                ("vorbis", "oggenc", "2"), ("vorbis", "oggenc", "6")]
    for family, encoder, setting in settings:
        recipe_id = f"digital48-{family}-{encoder}-{setting}-v1"
        extension = {"mp3": "mp3", "aac_lc": "m4a", "opus": "opus", "vorbis": "ogg"}[family]
        if family == "vorbis":
            argv = ["<oggenc>", "--quiet", "--discard-comments", "--serial", "1",
                    "--quality", setting, "--output", "<encoded>", "<adapter>"]
        else:
            argv = ["<ffmpeg>", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                    "-protocol_whitelist", "file,pipe", "-threads", "1", "-i", "<adapter>",
                    "-map", "0:a:0", "-map_metadata", "-1", "-vn", "-sn", "-dn",
                    "-filter_threads", "1", "-c:a", encoder, "-threads:a", "1",
                    "-sample_fmt", "flt" if family == "opus" else "fltp",
                    "-ar", str(RATE), "-ac", "2", "-b:a", setting,
                    "-fflags", "+bitexact", "-flags:a", "+bitexact"]
            if family == "mp3":
                argv += ["-abr", "0", "-joint_stereo", "1", "-reservoir", "1", "-write_xing", "1", "-id3v2_version", "0"]
            elif family == "aac_lc":
                argv += ["-profile:a", "aac_low", "-aac_coder", "twoloop"]
            else:
                argv += ["-application", "audio", "-frame_duration", "20", "-vbr", "off",
                         "-compression_level", "10", "-mapping_family", "0", "-serial_offset", "1"]
            argv += ["<encoded>"]
        result.append({"id": recipe_id, "codec_family": family, "encoder": encoder,
                       "setting": setting, "extension": extension,
                       "decoder": "mp3float" if family == "mp3" else "aac" if family == "aac_lc" else family,
                       "expected_profile": "LC" if family == "aac_lc" else None,
                       "expected_codec_name": "aac" if family == "aac_lc" else family,
                       "encode_argv": argv})
    return result


PROBE_ARGV = ["<ffprobe>", "-v", "error", "-protocol_whitelist", "file,pipe", "-threads", "1",
              "-show_streams", "-show_packets", "-show_entries",
              "stream=codec_name,profile,sample_rate,channels,channel_layout,time_base,start_pts,duration_ts:packet=pts,dts,duration:packet_side_data=side_data_type,skip_samples,discard_padding",
              "-of", "json", "<encoded>"]
DECODE_ARGV = ["<ffmpeg>", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
               "-protocol_whitelist", "file,pipe", "-threads", "1", "-c:a", "<decoder>", "-i", "<encoded>",
               "-map", "0:a:0", "-map_metadata", "-1", "-vn", "-sn", "-dn", "-filter_threads", "1",
               "-c:a", "pcm_f64le", "-threads:a", "1", "-f", "f64le", "<decoded>"]


def load_json(file, limit=MAX_JSON):
    value = json.loads(bounded_bytes(file, limit))
    if not isinstance(value, dict):
        raise ValueError("JSON object required")
    return value


def load_plan():
    plan = load_json(PLAN)
    if plan.get("proposal_id") != PROPOSAL_ID or plan.get("execution_authorized") is not False:
        raise ValueError("proposal identity or planning boundary differs")
    if plan.get("recipes") != recipes() or plan.get("probe_argv") != PROBE_ARGV or plan.get("decode_argv") != DECODE_ARGV:
        raise ValueError("exact recipe inventory differs")
    if set(plan["bindings"]) != set(BINDING_FILES):
        raise ValueError("complete implementation binding inventory required")
    for key, relative in BINDING_FILES.items():
        if plan["bindings"][key] != {"path": relative, "sha256": binding.sha_file(ROOT / relative)}:
            raise ValueError("public predecessor or implementation binding differs")
    delivery = load_json(ROOT / plan["bindings"]["reference_delivery"]["path"])
    inventory = delivery["delivery_inventory"]
    expected_cohort = {
        "delivery_inventory_sha256": inventory["output_inventory_sha256"],
        "original_inventory_sha256": delivery["input_inventory"]["inventory_sha256"],
        "delivery_authorization_sha256": delivery["bindings"]["authorization"]["sha256"],
        "attribution_sha256": delivery["attribution"]["attachment_sha256"],
        "total_bytes": inventory["output_audio_bytes_per_replay"],
        "minimum_frames": inventory["minimum_frame_count"], "maximum_frames": inventory["maximum_frame_count"],
        "bit_depth_counts": {"24": 9, "32": 7},
    }
    if plan["cohort"] != expected_cohort:
        raise ValueError("cohort differs from the bound historical delivery")
    if plan["accounting"] != {"references": 16, "codec_conditions": 8, "controls": 2,
                               "cases_per_replay": 160, "replays": 2, "total_cases": 320}:
        raise ValueError("fixed study denominator differs")
    if plan["resources"] != {"workers": 1, "minimum_free_gib": 15, "maximum_file_bytes": MAX_FILE,
                             "maximum_command_seconds": COMMAND_SECONDS, "maximum_case_seconds": CASE_SECONDS,
                             "stop_starting_cases_after_replay_seconds": REPLAY_SECONDS,
                             "persistent_derived_pcm_allowed": False}:
        raise ValueError("resource limits differ")
    return plan


def command_json(command):
    result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL, capture_output=True, timeout=30, check=True)
    return json.loads(result.stdout)


def authorize(plan, ci_run_id):
    # This fixed successor does not exist in the preparation checkpoint. A
    # caller-provided arbitrary JSON file cannot replace the committed record.
    if sys.flags.isolated != 1:
        raise ValueError("execution requires Python isolated mode (-I)")
    authorization = load_json(AUTHORIZATION)
    expected = {"schema_version": 1, "proposal_id": PROPOSAL_ID,
                "proposal_sha256": binding.sha_file(PLAN),
                "runner_sha256": binding.sha_file(Path(__file__)),
                "responsible_user_execution_approved": True,
                "retained_delivery_read_and_codec_replays_authorized": True,
                "metric_playback_listener_training_authorized": False}
    if canonical(authorization) != canonical(expected):
        raise ValueError("separate exact user-execution authorization absent or different")
    if not re.fullmatch(r"[1-9][0-9]*", str(ci_run_id)):
        raise ValueError("exact CI run ID required")
    status = subprocess.run(["git", "status", "--porcelain=v1"], cwd=ROOT, capture_output=True, check=True).stdout
    if status:
        raise ValueError("execution requires a clean committed checkout")
    for file in (PLAN, AUTHORIZATION, Path(__file__)):
        committed = subprocess.run(["git", "show", "HEAD:" + str(file.relative_to(ROOT))],
                                   cwd=ROOT, capture_output=True, check=True).stdout
        if committed != file.read_bytes():
            raise ValueError("execution artifact is not the committed version")
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout.decode().strip()
    ci = command_json(["gh", "run", "view", str(ci_run_id), "--json", "headSha,status,conclusion,workflowName,event"])
    if ci != {"headSha": head, "status": "completed", "conclusion": "success", "workflowName": "CI", "event": "push"}:
        raise ValueError("successful push CI for exact execution HEAD required")
    return head


def outside_repository(file):
    resolved = file.resolve(strict=True)
    if resolved == ROOT or ROOT in resolved.parents:
        raise ValueError("private data must remain outside the repository")
    if file.is_symlink():
        raise ValueError("symlink root is not allowed")
    return resolved


def bounded_bytes(file, limit=MAX_FILE):
    if file.is_symlink() or not file.is_file() or not 0 < file.stat().st_size <= limit:
        raise ValueError("regular bounded data file required")
    with file.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("file exceeded its bound during read")
    return data


def source_inventory(root, plan):
    root = outside_repository(root)
    if {file.name for file in root.iterdir()} != {"delivery.json", "attribution.json", "sources", ".partial"}:
        raise ValueError("exact retained delivery layout required")
    for name in ("sources", ".partial"):
        if (root / name).is_symlink() or not (root / name).is_dir():
            raise ValueError("retained directory layout differs")
    if any((root / ".partial").iterdir()):
        raise ValueError("retained partial directory must be empty")
    state = load_json(root / "delivery.json")
    records = state.get("completed")
    expected = plan["cohort"]
    if not isinstance(records, list) or len(records) != 16:
        raise ValueError("exact 16-member delivery inventory required")
    inventory_sha = digest(json.dumps(records, sort_keys=True, separators=(",", ":")).encode())
    if (type(state.get("schema_version")) is not int or state["schema_version"] != 1
            or state.get("state") != "private_delivery_projection_complete"
            or state.get("completed_count") != 16 or state.get("reference_count") != 16
            or inventory_sha != expected["delivery_inventory_sha256"]
            or state.get("output_inventory_sha256") != inventory_sha
            or state.get("input_inventory_sha256") != expected["original_inventory_sha256"]
            or state.get("authorization_sha256") != expected["delivery_authorization_sha256"]):
        raise ValueError("retained inventory differs from the frozen cohort")
    for key in ("processed_condition_opened", "listening_score_opened", "perceptual_metric_executed",
                "listener_response_collected", "sealed_evidence_opened", "public_verdict_emitted"):
        if state.get(key) is not False:
            raise ValueError("retained access boundary differs")
    attribution = bounded_bytes(root / "attribution.json", MAX_JSON)
    if digest(attribution) != expected["attribution_sha256"] or state.get("attribution_sha256") != digest(attribution):
        raise ValueError("attached attribution differs")
    names, sizes, bits, frames = set(), 0, Counter(), []
    for record in records:
        identity = record.get("opaque_delivery_id", "")
        if not re.fullmatch(r"odaq-delivery-[0-9a-f]{24}", identity):
            raise ValueError("retained opaque identity differs")
        relative = "sources/" + identity + ".wav"
        if record.get("relative_path") != relative or relative in names:
            raise ValueError("duplicate identity or unsafe relative path")
        names.add(relative)
        data = bounded_bytes(root / relative)
        if len(data) != record.get("output_byte_length") or digest(data) != record.get("output_sha256"):
            raise ValueError("retained delivery integrity differs")
        channels, geometry = pcm_channels(data)
        del channels
        if geometry != record.get("output_pcm_geometry"):
            raise ValueError("retained PCM geometry differs")
        sizes += len(data)
        bits[geometry["bit_depth"]] += 1
        frames.append(geometry["frame_count"])
    if ({"sources/" + item.name for item in (root / "sources").iterdir()} != names
            or sizes != expected["total_bytes"] or {str(key): value for key, value in bits.items()} != expected["bit_depth_counts"]
            or min(frames) != expected["minimum_frames"] or max(frames) != expected["maximum_frames"]):
        raise ValueError("retained distribution or exact file inventory differs")
    return sorted(records, key=lambda record: record["opaque_delivery_id"])


def pcm_channels(data):
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:16] != b"WAVEfmt ":
        raise ValueError("canonical integer RIFF input required")
    length, fmt_size = struct.unpack_from("<I", data, 4)[0], struct.unpack_from("<I", data, 16)[0]
    encoding, channels, rate, byte_rate, block, bits = struct.unpack_from("<HHIIHH", data, 20)
    if (length + 8 != len(data) or fmt_size != 16 or encoding != 1 or channels != 2
            or rate != RATE or bits not in (24, 32) or block != bits // 8 * 2
            or byte_rate != rate * block or data[36:40] != b"data"
            or struct.unpack_from("<I", data, 40)[0] != len(data) - 44):
        raise ValueError("canonical integer PCM geometry differs")
    frames, remainder = divmod(len(data) - 44, block)
    if remainder or not 0 < frames <= MAX_FRAMES:
        raise ValueError("source duration outside the bounded geometry")
    values = [[], []]
    width, scale = bits // 8, 2 ** (bits - 1)
    for offset in range(44, len(data), block):
        for channel in range(2):
            start = offset + channel * width
            values[channel].append(int.from_bytes(data[start:start + width], "little", signed=True) / scale)
    return values, {"sample_rate_hz": rate, "channel_count": 2, "bit_depth": bits,
                    "frame_count": frames, "sample_encoding": "signed_integer_pcm", "container_encoding": "riff_wave"}


def float32_adapter(channels):
    if len(channels) != 2 or not channels[0] or len(channels[0]) != len(channels[1]):
        raise ValueError("nonempty equal stereo channels required")
    payload = bytearray()
    values = [[], []]
    for pair in zip(*channels, strict=True):
        for channel, value in enumerate(pair):
            if not math.isfinite(value) or not -1 <= value <= 1:
                raise ValueError("invalid adapter input")
            packed = struct.pack("<f", value)
            payload.extend(packed)
            values[channel].append(struct.unpack("<f", packed)[0])
    fmt = struct.pack("<HHIIHH", 3, 2, RATE, RATE * 8, 8, 32)
    body = (b"WAVEfmt " + struct.pack("<I", 16) + fmt + b"fact" + struct.pack("<II", 4, len(channels[0]))
            + b"data" + struct.pack("<I", len(payload)) + payload)
    return b"RIFF" + struct.pack("<I", len(body)) + body, values


def decoded_channels(data, reference_frames):
    frames, remainder = divmod(len(data), 16)
    if remainder or not 0 < frames <= reference_frames + 2 * RATE:
        raise CaseFailure("decoder_frame_geometry")
    channels = [[], []]
    for left, right in struct.iter_unpack("<dd", data):
        if not math.isfinite(left) or not math.isfinite(right):
            raise CaseFailure("decoder_nonfinite")
        channels[0].append(left)
        channels[1].append(right)
    return channels


def expand(argv, files):
    return [str(files[value[1:-1]]) if value.startswith("<") and value.endswith(">") else value for value in argv]


def reserve(parent):
    if shutil.disk_usage(parent).free < MIN_FREE + 12 * MAX_FILE:
        raise ValueError("15 GiB reserve plus bounded scratch allowance required")


def write_new(file, data):
    descriptor = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output:
        output.write(data)


def child_limits():
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_FILE, MAX_FILE))


def invoke(argv, files, stage, scratch, deadline):
    remaining = min(COMMAND_SECONDS, deadline - time.monotonic())
    if remaining <= 0:
        raise CaseFailure("case_time_budget")
    with (scratch / (stage + ".stdout")).open("xb") as output, (scratch / (stage + ".stderr")).open("xb") as error:
        try:
            result = subprocess.run(expand(argv, files), stdin=subprocess.DEVNULL, stdout=output, stderr=error,
                                    cwd=scratch, env=ENV, timeout=remaining, preexec_fn=child_limits, check=False)
        except subprocess.TimeoutExpired as exc:
            raise CaseFailure(stage + "_timeout") from exc
    if result.returncode:
        raise CaseFailure(stage + "_failed")
    stdout = scratch / (stage + ".stdout")
    if stdout.stat().st_size > MAX_JSON:
        raise CaseFailure(stage + "_metadata_bound")
    return stdout.read_bytes()


def packet_geometry(probe, recipe):
    streams, packets = probe.get("streams"), probe.get("packets")
    if not isinstance(streams, list) or len(streams) != 1 or not isinstance(packets, list) or not 0 < len(packets) <= 4096:
        raise CaseFailure("encoded_stream_inventory")
    stream = streams[0]
    if (not isinstance(stream, dict) or stream.get("codec_name") != recipe["expected_codec_name"] or stream.get("sample_rate") != str(RATE)
            or stream.get("channels") != 2 or stream.get("channel_layout") != "stereo"
            or (recipe["expected_profile"] is not None and stream.get("profile") != recipe["expected_profile"])):
        raise CaseFailure("encoded_channel_or_rate_geometry")
    if not isinstance(stream.get("time_base"), str) or not re.fullmatch(r"[1-9][0-9]*/[1-9][0-9]*", stream["time_base"]):
        raise CaseFailure("encoded_timebase")
    for key in ("start_pts", "duration_ts"):
        value = stream.get(key)
        if value is not None and (type(value) is not int or abs(value) >= 2**63):
            raise CaseFailure("encoded_packet_timestamps")
    selected_packets = []
    for packet in packets:
        if not isinstance(packet, dict):
            raise CaseFailure("encoded_packet_structure")
        for key in ("pts", "dts", "duration"):
            value = packet.get(key)
            if value is not None and (type(value) is not int or abs(value) >= 2**63):
                raise CaseFailure("encoded_packet_timestamps")
        side = packet.get("side_data_list", [])
        if not isinstance(side, list) or len(side) > 16 or any(not isinstance(item, dict) for item in side):
            raise CaseFailure("encoded_packet_side_data")
        selected_side = []
        for item in side:
            if not isinstance(item.get("side_data_type"), str) or len(item["side_data_type"]) > 80:
                raise CaseFailure("encoded_packet_side_data")
            for key in ("skip_samples", "discard_padding"):
                value = item.get(key)
                if value is not None and (type(value) is not int or not 0 <= value < 2**32):
                    raise CaseFailure("encoded_packet_side_data")
            selected_side.append({key: item[key] for key in ("side_data_type", "skip_samples", "discard_padding") if key in item})
        selected = {key: packet[key] for key in ("pts", "dts", "duration") if key in packet}
        if side:
            selected["side_data_list"] = selected_side
        selected_packets.append(selected)
    # Retain the bound demuxer's timestamps, skip/discard metadata and duration.
    # They are observations, not a waveform-offset correction instruction.
    selected_stream = {key: stream[key] for key in ("codec_name", "profile", "sample_rate", "channels", "channel_layout", "time_base", "start_pts", "duration_ts") if key in stream}
    return {"streams": [selected_stream], "packets": selected_packets}


@contextmanager
def analysis_deadline(deadline):
    def expired(signum, frame):
        raise CaseFailure("alignment_timeout")
    previous = signal.signal(signal.SIGALRM, expired)
    remaining = deadline - time.monotonic()
    try:
        if remaining <= 0:
            raise CaseFailure("case_time_budget")
        signal.setitimer(signal.ITIMER_REAL, remaining)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def duration_eligibility(record):
    summary = record["alignment"]["summary"]
    active, frames = summary["active_seconds"], summary["aligned_frames"]
    capped = min(active, frames / RATE) if active is not None and frames is not None else None
    supported = record["status"] == "supported"
    return {"active_seconds_bounded_by_geometry": capped,
            "duration_geometry_cap_applied": capped is not None and capped < active,
            "subtle_technical_support": supported and capped is not None and capped >= 4.0,
            "quality_duration_eligible": supported and capped is not None and capped >= 8.0}


def compare(reference, test, case_id, deadline):
    with analysis_deadline(deadline):
        record = alignment.align_channels(reference_channels=reference, test_channels=test,
                                          reference_channel_map=["L", "R"], test_channel_map=["L", "R"],
                                          sample_rate_hz=RATE, recipe_identity=case_id,
                                          minimum_active_seconds=4.0, maximum_delay_seconds=2.0)
    return {"alignment": record, **duration_eligibility(record),
            "quality_policy": "unchanged_alignment_and_four_eight_second_limits_with_aligned_frame_geometry_cap",
            "perceptual_support": False, "severity": None, "audibility": None, "artifacts": None, "transparency": None}


def empty_case(source, recipe):
    recipe_id = recipe["id"] if isinstance(recipe, dict) else recipe
    case_id = digest((PROPOSAL_ID + ":" + source["opaque_delivery_id"] + ":" + recipe_id).encode())[:24]
    return {"case_id": case_id, "recipe_id": recipe_id, "state": "not_run", "reason": None,
            "comparison": None, "encoded_sha256": None, "decoded_sha256": None, "packet_geometry": None}


def process_case(source, recipe, root, scratch_parent, tools, compare_fn=compare, invoke_fn=invoke):
    record = empty_case(source, recipe)
    recipe_id, case_id = record["recipe_id"], record["case_id"]
    reserve(scratch_parent)
    deadline = time.monotonic() + CASE_SECONDS
    try:
        data = bounded_bytes(root / source["relative_path"])
        if digest(data) != source["output_sha256"]:
            raise ValueError("retained delivery changed after verification")
        original, geometry = pcm_channels(data)
        adapter, adapted = float32_adapter(original)
        record.update({"source_sha256": digest(data), "adapter_sha256": digest(adapter), "input_geometry": geometry})
        if recipe_id == "identity":
            reference, test = original, original
        elif recipe_id == "float32_adapter":
            reference, test = original, adapted
        else:
            with tempfile.TemporaryDirectory(prefix="digital-case-", dir=scratch_parent) as directory:
                scratch = Path(directory)
                files = {**tools, "decoder": recipe["decoder"], "adapter": scratch / "input.wav", "encoded": scratch / ("condition." + recipe["extension"]),
                         "decoded": scratch / "decoded.f64"}
                write_new(files["adapter"], adapter)
                invoke_fn(recipe["encode_argv"], files, "encode", scratch, deadline)
                encoded = bounded_bytes(files["encoded"])
                record["encoded_sha256"] = digest(encoded)
                probe = json.loads(invoke_fn(PROBE_ARGV, files, "probe", scratch, deadline))
                record["packet_geometry"] = packet_geometry(probe, recipe)
                invoke_fn(DECODE_ARGV, files, "decode", scratch, deadline)
                decoded = bounded_bytes(files["decoded"])
                record["decoded_sha256"] = digest(decoded)
                test = decoded_channels(decoded, geometry["frame_count"])
                reference = adapted
            # The comparison is in memory; scratch encoded/decoded PCM is gone.
        record["comparison"] = compare_fn(reference, test, case_id, deadline)
        record["state"] = "observed"
    except CaseFailure as exc:
        record["state"], record["reason"] = "failed", str(exc)
    except (ValueError, OSError, KeyError, TypeError, struct.error):
        record["state"], record["reason"] = "failed", "case_integrity_or_structure"
    return record


def run_replay(records, root, parent, tools, process_fn=process_case):
    began = time.monotonic()
    cases = []
    stopped = None
    for source in records:
        for recipe in (*CONTROLS, *recipes()):
            if time.monotonic() - began >= REPLAY_SECONDS:
                stopped = stopped or "replay_time_budget"
            not_run = empty_case(source, recipe)
            if stopped:
                not_run["reason"] = stopped
                cases.append(not_run)
                continue
            try:
                cases.append(process_fn(source, recipe, root, parent, tools))
            except (ValueError, OSError):
                stopped = "resource_or_preflight_stop"
                not_run["reason"] = stopped
                cases.append(not_run)
    return {"proposal_id": PROPOSAL_ID, "cases": cases}


def summarize(replays):
    expected = Counter({recipe: 16 for recipe in (*CONTROLS, *(item["id"] for item in recipes()))})
    if len(replays) != 2 or any(Counter(item["recipe_id"] for item in replay["cases"]) != expected
                              or len({item["case_id"] for item in replay["cases"]}) != 160 for replay in replays):
        raise ValueError("every planned case in both replays must remain visible")
    summaries = []
    for replay in replays:
        cases = replay["cases"]
        for item in cases:
            if not re.fullmatch(r"[0-9a-f]{24}", item["case_id"]):
                raise ValueError("opaque fixed case identity required")
            if item["state"] not in {"observed", "failed", "not_run"}:
                raise ValueError("unknown case disposition")
            comparison = item["comparison"]
            if item["state"] != "observed":
                if item["reason"] not in FAILURE_REASONS or comparison is not None:
                    raise ValueError("unknown failure reason or fabricated comparison")
                continue
            if item["reason"] is not None or not isinstance(comparison, dict):
                raise ValueError("observed comparison is missing")
            if comparison["perceptual_support"] is not False or any(comparison[key] is not None for key in ("severity", "audibility", "artifacts", "transparency")):
                raise ValueError("technical evidence cannot populate perceptual outcomes")
            raw = comparison["alignment"]
            raw_reasons = raw["support"]["reasons"]
            if not isinstance(raw_reasons, list) or any(reason not in ALIGNMENT_REASONS for reason in raw_reasons):
                raise ValueError("unknown alignment reason in public projection")
            supported = raw["status"] == "supported"
            active = raw["alignment"]["summary"]["active_seconds"]
            frames = raw["alignment"]["summary"]["aligned_frames"]
            if raw["status"] not in {"supported", "unsupported"} or supported == bool(raw_reasons):
                raise ValueError("alignment state and reasons contradict")
            if active is not None and (type(active) not in (int, float) or not math.isfinite(active) or active < 0):
                raise ValueError("invalid active duration")
            if frames is not None and (type(frames) is not int or frames < 0):
                raise ValueError("invalid aligned frame count")
            if supported and (active is None or active < 4.0):
                raise ValueError("supported alignment lacks four active seconds")
            for key, value in duration_eligibility(raw).items():
                if type(comparison[key]) is not type(value) or comparison[key] != value:
                    raise ValueError("technical support projection contradicts alignment or geometry")
        reasons = Counter(item["reason"] for item in cases if item["reason"])
        alignment_reasons = Counter(reason for item in cases if item["comparison"]
                                    for reason in item["comparison"]["alignment"]["support"]["reasons"])
        summaries.append({"planned": 160, "dispositions": dict(sorted(Counter(item["state"] for item in cases).items())),
                          "failure_or_stop_reasons": dict(sorted(reasons.items())),
                          "alignment_unsupported_reasons": dict(sorted(alignment_reasons.items())),
                          "active_duration_geometry_cap_applied_count": sum(bool(item["comparison"] and item["comparison"]["duration_geometry_cap_applied"]) for item in cases),
                          "subtle_technically_supported": sum(bool(item["comparison"] and item["comparison"]["subtle_technical_support"]) for item in cases),
                          "quality_duration_eligible": sum(bool(item["comparison"] and item["comparison"]["quality_duration_eligible"]) for item in cases)})
    identical = canonical(replays[0]) == canonical(replays[1])
    all_observed = all(item["state"] == "observed" for replay in replays for item in replay["cases"])
    return {"schema_version": 1, "proposal_id": PROPOSAL_ID,
            "state": "technical_replay_complete" if identical and all_observed else "technical_negative_or_incomplete",
            "replays": summaries, "private_replays_byte_identical": identical,
            "all_cases_observed": all_observed, "perceptual_support": False,
            "severity": None, "audibility": None, "artifacts": None, "transparency": None,
            "human_calibrated": False, "independent_validation": False, "public_verdict_enabled": False}


def execute(args):
    plan = load_plan()
    head = authorize(plan, args.ci_run_id)  # Before any private path or inventory access.
    tools = {name: getattr(args, name).resolve(strict=True) for name in ("ffmpeg", "ffprobe", "oggenc")}
    expected_tools = load_json(ROOT / plan["bindings"]["native_tools"]["path"])
    if binding.bind_tools(tools) != expected_tools:
        raise ValueError("native tool, dependency, runtime or operating-system binding changed")
    root, parent = outside_repository(args.source_root), outside_repository(args.output_parent)
    if root == parent or root in parent.parents or parent in root.parents:
        raise ValueError("separate private source and output trees required")
    reserve(parent)
    records = source_inventory(root, plan)
    # Only our newly created temporary case directories are auto-removed.
    # Private reports are retained in a unique new directory, never overwritten.
    run_root = Path(tempfile.mkdtemp(prefix="lossytrace-digital-", dir=parent))
    write_new(run_root / "execution.json", canonical({"head": head, "ci_run_id": args.ci_run_id,
                                                     "proposal_sha256": binding.sha_file(PLAN)}))
    write_new(run_root / "attribution.json", bounded_bytes(root / "attribution.json", MAX_JSON))
    replays = []
    for index in range(2):
        # Reverify the entire fixed inventory and attribution before each replay.
        try:
            verified = source_inventory(root, plan)
            if verified != records:
                raise ValueError("retained inventory changed between replays")
        except (ValueError, OSError):
            cases = [empty_case(source, recipe) for source in records for recipe in (*CONTROLS, *recipes())]
            for case in cases:
                case["reason"] = "inventory_changed_between_replays"
            replay = {"proposal_id": PROPOSAL_ID, "cases": cases}
        else:
            replay = run_replay(records, root, run_root, tools)
        write_new(run_root / f"replay-{index + 1}.json", canonical(replay))
        replays.append(replay)
    report = summarize(replays)
    write_new(run_root / "public-projection.json", canonical(report))
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
        plan = load_plan()
        result = {"proposal_id": PROPOSAL_ID, "execution_authorized": False, "accounting": plan["accounting"]}
    else:
        result = execute(args)
    sys.stdout.buffer.write(canonical(result))


if __name__ == "__main__":
    main()
