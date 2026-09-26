#!/usr/bin/env python3
"""Test current software and replay byte-bound historical audits at their checkpoint.

Nothing is skipped: the explicit historical modules run in a detached worktree;
all other discovered modules run against the current tree. Historical research
files are checked for preservation in the current tree before either suite.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT = "48f0f63f5f87b0afa816ef0ee869c157e7f232b3"
HISTORICAL = frozenset(
    ["test_audio_integrity_v2_public_decoder_probe", "test_perceptual_degradation_objective_completion_audit"]
    + [f"test_perceptual_degradation_objective_completion_audit_v{n}" for n in range(2, 23)]
)


def split_modules(names: set[str]) -> tuple[list[str], list[str]]:
    if not HISTORICAL <= names:
        raise ValueError("historical test inventory is incomplete")
    return sorted(names - HISTORICAL), sorted(HISTORICAL)


def preserved(path: str, original: bytes, current: bytes) -> bool:
    if path == "docs/research/status.md":
        return current.startswith(original)
    return current == original


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], timeout=60)


def verify_historical_preservation() -> int:
    paths = git("ls-tree", "-r", "--name-only", CHECKPOINT, "benchmarks", "research", "scripts", "docs/research").decode().splitlines()
    for path in paths:
        original = git("show", f"{CHECKPOINT}:{path}")
        current = ROOT / path
        if not current.is_file() or not preserved(path, original, current.read_bytes()):
            raise ValueError(f"historical research file changed: {path}; use a separately named successor")
    # Confirm this is the checkpoint required by the frozen audit, not a convenient snapshot.
    for path, expected in {
        "src/main.rs": "c1da3719f1897ce47e4a0c28b8585060a43268575d75e1fa6c6d9418e910cf54",
        "tests/cli.rs": "9cf8cb01b942886ff0e268fb83ed86f6b0331c71594eedaa361cf40d5cdd5645",
    }.items():
        if hashlib.sha256(git("show", f"{CHECKPOINT}:{path}")).hexdigest() != expected:
            raise ValueError("historical CLI checkpoint identity differs")
    return len(paths)


def run_current(names: list[str]) -> bool:
    sys.path.insert(0, str(ROOT / "scripts/tests"))
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    return unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful()


def run_historical(names: list[str]) -> bool:
    # Dedicated generated directory; preserve it if cleanup detects unexpected changes.
    parent = Path(tempfile.mkdtemp(prefix="lossytrace-historical-tests-"))
    checkout = parent / "checkpoint"
    added = False
    try:
        git("worktree", "add", "--detach", str(checkout), CHECKPOINT)
        added = True
        result = subprocess.run([sys.executable, "-m", "unittest", *names],
                                cwd=checkout / "scripts/tests", check=False, timeout=1200)
        return result.returncode == 0
    finally:
        if added:
            # No force: an unexpected modification must not be discarded.
            git("worktree", "remove", str(checkout))
        parent.rmdir()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-only", action="store_true", help="diagnostic subset, not full CI")
    args = parser.parse_args()
    names = {p.stem for p in (ROOT / "scripts/tests").glob("test_*.py")}
    current, historical = split_modules(names)
    count = verify_historical_preservation()
    print(f"Preserved {count} historical research files; replay {len(historical)} test modules at {CHECKPOINT}.", flush=True)
    archived_ok = run_historical(historical)
    if args.historical_only:
        return 0 if archived_ok else 1
    print(f"Run {len(current)} current test modules against the current source tree.", flush=True)
    current_ok = run_current(current)
    return 0 if archived_ok and current_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
