# Regression scope after the codec-history successor

The first full regression run after adding `lossytrace explain` completed with
1 failure and 35 errors (1,628 tests attempted, 14 existing opt-in skips).
The failures were exact historical source-binding checks, not a detector or
decoder performance result. The frozen decoder-equivalence plan binds the
original CLI bytes. The perceptual objective-completion audit also binds the
original CLI and its test, and 21 successor audits recursively validate it.

Changing those historical hashes would reinterpret consumed protocols. Leaving
them as requirements on every future CLI would prohibit even a version bump.
The regression entry point therefore separates two explicit scopes:

1. **Historical replay:** 23 named audit test modules execute unchanged at
   `48f0f63f5f87b0afa816ef0ee869c157e7f232b3`, whose CLI and test hashes match
   the consumed audit. All 136 tests passed in the first isolated replay.
   These prove the preserved historical records, not the current executable.
2. **Current software:** every other discovered Python test module and the
   Rust tests execute on the current revision. New modules are included by
   default. Current CLI tests independently assert the verdict-free analysis
   contract and exercise the added explanation command.

Before either Python suite, the runner verifies preservation of all 980 files
under the historical checkpoint's research, benchmark, script and research-doc
trees. New successor files are allowed; existing bytes must match, except that
the status journal permits strictly append-only additions. The old tests and
validators are not edited, skipped, mocked, or rebound to new hashes. Missing
historical test modules fail closed. Existing opt-in tests retain their prior
skip conditions; routing itself adds none.

The replay uses a temporary detached Git worktree and removes it only through
non-forced Git cleanup. Full history and the historical Rust 1.94.0 toolchain
are required. A dirty unexpected checkout is preserved rather than discarded.
CI calls `python scripts/run_regression_tests.py`; focused direct unittest
discovery remains available, but direct discovery of every historical audit
against a newer CLI is intentionally not the full-regression entry point.

This transition does not repair, rerun or overturn a consumed scientific
experiment. The current Lossprint challenge selection, runner and scientific
rules remain unchanged, and a new green exact-commit CI run is still required
before any challenge waveform access.
