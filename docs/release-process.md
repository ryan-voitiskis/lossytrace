# RC build and verification

The RC workflow builds on `codex/codec-history-rc` pushes without publishing.
Only an explicit matching `vX.Y.Z-rc.N` tag can enter its publication job.
The existing general release workflow excludes those RC tags to prevent a
second, less strictly verified publication. No stable tag or registry publish
is part of this process.

1. Commit reviewed source and notices; preserve frozen research artifacts.
2. Require green CI on the exact commit. Python tests include current software
   plus historical byte-bound audit replay; Rust tests check the current CLI.
3. Use Rust 1.94.0, locked dependencies, the declared native target and fixed
   source path remapping. On macOS, use the linker's `-reproducible` option and
   `-oso_prefix` with each absolute target-directory prefix to normalize debug
   map paths before UUID generation. Build into two fresh target directories
   and require identical executable bytes. Package each and require identical
   archives. UUIDs and ad-hoc signatures are retained, not stripped for comparison.
4. Extract and test the actual native package on macOS 15 arm64 or Ubuntu 24.04
   x86-64. Keep smoke and same-runner reproducibility reports as artifacts.
5. Review the expected native packages, dependency notices/source, SBOMs and
   exact-commit checks before creating an RC tag. Publishing generates a
   checksum list for every release asset and uses GitHub's prerelease flag.
6. Download published assets and verify their checksums, source commit and
   native smoke/rebuild records. Keep the PR unmerged unless separately
   authorized. The release candidate is not automatically a stable release.

## Local native package

After committing the intended RC source, build with the same pinned compiler:

```sh
rustup run 1.94.0 cargo build --locked --release --target aarch64-apple-darwin
rustup run 1.94.0 python3 scripts/package_rc.py --root . \
  --binary target/aarch64-apple-darwin/release/lossytrace \
  --target aarch64-apple-darwin --tag v0.1.0-rc.1 \
  --output dist/lossytrace-v0.1.0-rc.1-aarch64-apple-darwin.tar.gz
python3 scripts/smoke_rc.py \
  --bundle dist/lossytrace-v0.1.0-rc.1-aarch64-apple-darwin.tar.gz \
  --target aarch64-apple-darwin --tag v0.1.0-rc.1 --output dist/smoke.json
```

Use the Linux target only on the corresponding native environment. Package
creation refuses uncommitted tracked changes, wrong versions, unreviewed
targets, absent notices and registry-source checksum mismatches. It does not
compile or validate a binary's build history; provenance also depends on the
workflow's controlled build and the published attestations. A local successful
smoke test alone is not permission to publish or proof of independent detector
validation. Build outputs and temporary fixtures should use the designated
external workspace when running this research project locally.

Archives have sorted members, fixed modes and zero timestamps/ownership. The
repeat-build claim is deliberately limited to two clean build directories in
one pinned-compiler hosted environment. Toolchain, OS linker, standard-library
and platform differences can affect bytes across hosts. GitHub provenance
attestations identify an originating workflow; they are not a performance or
scientific endorsement. See [license provenance](../licenses/README.md) and
[release notes](release-notes.md) for redistribution and capability scope.

## macOS repeat-build correction

The [initial RC artifact run](https://github.com/ryan-voitiskis/lossytrace/actions/runs/36258832618)
passed Linux but failed the macOS byte comparison before publication. A local
reproduction isolated the differences to the UUID and its signature hash.
Unstripped diagnostics exposed target-directory paths in the debug map.
`-reproducible` alone did not resolve the mismatch; additionally normalizing
the object-path prefix with `-oso_prefix` produced identical clean builds.
The equality requirement was not relaxed and no binary bytes were patched.
The options are documented in Apple's linker manual (`man ld`); see also
[Apple's build UUID guidance](https://developer.apple.com/documentation/technotes/tn3178-checking-for-and-resolving-build-uuid-problems).
