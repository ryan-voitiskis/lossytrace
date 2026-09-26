#!/usr/bin/env python3
"""Build a deterministic native RC bundle with notices and covered source."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import tarfile
import tomllib

TARGETS = {"aarch64-apple-darwin", "x86_64-unknown-linux-gnu"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def runtime_packages(metadata: dict) -> list[dict]:
    nodes = {n["id"]: n for n in metadata["resolve"]["nodes"]}
    root = metadata["resolve"]["root"]
    seen = set()
    pending = [root]
    while pending:
        identity = pending.pop()
        if identity in seen:
            continue
        seen.add(identity)
        for dep in nodes[identity]["deps"]:
            if any(kind["kind"] in (None, "build") for kind in dep["dep_kinds"]):
                pending.append(dep["pkg"])
    return sorted((p for p in metadata["packages"] if p["id"] in seen and p["id"] != root),
                  key=lambda p: (p["name"], p["version"]))


def archive_bytes(files: dict[str, tuple[bytes, int]]) -> bytes:
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0, compresslevel=9) as gz:
        with tarfile.open(fileobj=gz, mode="w", format=tarfile.GNU_FORMAT) as tar:
            for name, (data, mode) in sorted(files.items()):
                path = PurePosixPath(name)
                if not name or str(path) == "." or path.is_absolute() or ".." in path.parts or "\0" in name:
                    raise ValueError("unsafe archive member")
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = mode
                info.mtime = info.uid = info.gid = 0
                info.uname = info.gname = ""
                tar.addfile(info, io.BytesIO(data))
    return stream.getvalue()


def dependency_material(root: Path, target: str) -> tuple[dict, list[dict]]:
    metadata = json.loads(subprocess.check_output(
        ["cargo", "metadata", "--locked", "--offline", "--format-version", "1", "--filter-platform", target],
        cwd=root, timeout=60))
    lock = tomllib.loads((root / "Cargo.lock").read_text())
    checksums = {(p["name"], p["version"]): p.get("checksum") for p in lock["package"]}
    files = {}
    entries = []
    for package in runtime_packages(metadata):
        name, version = package["name"], package["version"]
        if package.get("source") != "registry+https://github.com/rust-lang/crates.io-index":
            raise ValueError("unreviewed non-registry dependency")
        directory = Path(package["manifest_path"]).parent
        crate = directory.parents[1].parent / "cache" / directory.parent.name / f"{name}-{version}.crate"
        data = crate.read_bytes()
        if sha(data) != checksums[(name, version)]:
            raise ValueError("dependency source checksum mismatch")
        texts = {}
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                relative = PurePosixPath(member.name)
                if relative.is_absolute() or ".." in relative.parts:
                    raise ValueError("unsafe dependency archive")
                if any(relative.name.upper().startswith(prefix) for prefix in ("LICENSE", "COPYING", "NOTICE", "UNLICENSE")):
                    texts[str(relative)] = archive.extractfile(member).read()
        license_expression = package.get("license")
        if not license_expression:
            raise ValueError("dependency license absent")
        if not texts and license_expression != "MPL-2.0":
            raise ValueError(f"license text requires review: {name}")
        for path, content in texts.items():
            files["licenses/dependencies/" + path] = (content, 0o644)
        source_member = None
        if license_expression == "MPL-2.0":
            source_member = f"covered-source/{name}-{version}.crate"
            files[source_member] = (data, 0o644)
        entries.append({"name": name, "version": version, "license": license_expression,
                        "crate_sha256": sha(data), "source_url": f"https://crates.io/api/v1/crates/{name}/{version}/download",
                        "bundled_covered_source": source_member,
                        "notice_files": ["licenses/dependencies/" + p for p in sorted(texts)]})
    files["licenses/MPL-2.0.txt"] = ((root / "licenses/MPL-2.0.txt").read_bytes(), 0o644)
    sysroot = Path(subprocess.check_output(["rustc", "--print", "sysroot"], text=True).strip())
    rust_notices = sysroot / "share/doc/rust"
    files["licenses/rust/COPYRIGHT-library.html"] = ((rust_notices / "COPYRIGHT-library.html").read_bytes(), 0o644)
    rust_texts = sorted((rust_notices / "licenses").glob("*.txt"))
    if not rust_texts:
        raise ValueError("Rust standard-library license texts absent")
    for text in rust_texts:
        files["licenses/rust/licenses/" + text.name] = (text.read_bytes(), 0o644)
    files["dependency-inventory.json"] = ((json.dumps(entries, indent=2, sort_keys=True) + "\n").encode(), 0o644)
    notice = ["# Third-party notices", "", "This bundle includes the normal/build dependency closure for its target; dev-only dependencies are excluded.",
              "Each dependency retains its upstream license and notices listed below.",
              "", "Symphonia components are unmodified MPL-2.0 Covered Software. Their exact published source archives are included under covered-source/; the license is licenses/MPL-2.0.txt. These source files remain available under MPL-2.0, without restrictions on recipients' rights. LossyTrace's own MIT/Apache terms do not replace those terms.",
              "", "Rust standard-library copyright and licensing information from the build toolchain is included at licenses/rust/COPYRIGHT-library.html with the toolchain's license texts. This material covers multiple targets; it is not a claim that every listed component is linked here.",
              "", "Lossprint code and weights are not included.", ""]
    for entry in entries:
        notice.extend([f"## {entry['name']} {entry['version']}", f"License: {entry['license']}",
                       f"Source: {entry['source_url']}", f"Source SHA-256: {entry['crate_sha256']}",
                       *[f"Notice: {p}" for p in entry["notice_files"]],
                       f"Bundled source: {entry['bundled_covered_source']}" if entry["bundled_covered_source"] else "", ""])
    files["THIRD_PARTY_NOTICES.md"] = (("\n".join(notice) + "\n").encode(), 0o644)
    return files, entries


def package(root: Path, binary: Path, target: str, tag: str) -> tuple[bytes, dict]:
    if target not in TARGETS or not re.fullmatch(r"v\d+\.\d+\.\d+-rc\.\d+", tag):
        raise ValueError("only reviewed targets and explicit RC tags are supported")
    if subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=root, text=True).strip():
        raise ValueError("commit tracked source changes before packaging an identified RC")
    version = tomllib.loads((root / "Cargo.toml").read_text())["package"]["version"]
    if tag != "v" + version:
        raise ValueError("tag and Cargo version differ")
    result = subprocess.check_output([str(binary.resolve()), "--version"], timeout=15, text=True).strip()
    if result != f"lossytrace {version}":
        raise ValueError("binary version differs")
    files, dependencies = dependency_material(root, target)
    for name, source in {
        "README.md": "docs/binary-readme.md", "inspection-guide.md": "docs/inspection-guide.md",
        "release-notes.md": "docs/release-notes.md", "LICENSE-APACHE": "LICENSE-APACHE", "LICENSE-MIT": "LICENSE-MIT",
        "Cargo.lock": "Cargo.lock",
    }.items():
        files[name] = ((root / source).read_bytes(), 0o644)
    files["lossytrace"] = (binary.read_bytes(), 0o755)
    info = {"schema_version": 1, "version": version, "tag": tag, "target": target,
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
            "rustc": subprocess.check_output(["rustc", "--version"], text=True).strip(),
            "cargo_lock_sha256": sha((root / "Cargo.lock").read_bytes()),
            "binary_sha256": sha(files["lossytrace"][0]), "dependency_count": len(dependencies),
            "covered_source_count": sum(e["bundled_covered_source"] is not None for e in dependencies),
            "archive_metadata": "sorted members; zero timestamps and ownership; fixed modes"}
    files["build-info.json"] = ((json.dumps(info, indent=2, sort_keys=True) + "\n").encode(), 0o644)
    return archive_bytes(files), info


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("root", "binary", "output"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--tag", required=True)
    args = parser.parse_args()
    data, info = package(args.root.resolve(), args.binary, args.target, args.tag)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as out:
        out.write(data)
    print(json.dumps({**info, "archive_sha256": sha(data)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
