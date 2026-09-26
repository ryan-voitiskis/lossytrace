"""Metadata-only binding of the native digital-study tool/runtime closure.

No codec invocation, waveform access, downloads, installation or private data.
System-cache dependencies are bound to the exact macOS build, not claimed to
have individually readable file hashes. The closure excludes optional plugins.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import sysconfig
from pathlib import Path


def canonical(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()


def sha_file(file):
    digest = hashlib.sha256()
    with Path(file).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metadata(command):
    result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                            timeout=30, check=True, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    return result.stdout.decode().strip()


def dependency_paths(binary):
    lines = metadata(["/usr/bin/otool", "-L", str(binary)]).splitlines()[1:]
    return [line.strip().split(" (compatibility", 1)[0] for line in lines if line.strip()]


def resolve_dependency(token, owner, executable):
    if token.startswith(("/usr/lib/", "/System/Library/")):
        return "system:" + token.removeprefix("/System/Library/").removeprefix("/usr/lib/")
    replacements = {"@loader_path": owner.parent, "@executable_path": executable.parent}
    for prefix, parent in replacements.items():
        if token.startswith(prefix + "/"):
            candidate = parent / token[len(prefix) + 1:]
            if candidate.is_file():
                return candidate.resolve()
    if token.startswith("@rpath/"):
        commands = metadata(["/usr/bin/otool", "-l", str(owner)])
        paths = re.findall(r"cmd LC_RPATH\s+cmdsize \d+\s+path (.*?) \(offset", commands)
        for prefix in paths:
            for marker, parent in replacements.items():
                prefix = prefix.replace(marker, str(parent))
            candidate = Path(prefix) / token[len("@rpath/"):]
            if candidate.is_file():
                return candidate.resolve()
    candidate = Path(token)
    if candidate.is_absolute() and candidate.is_file():
        return candidate.resolve()
    raise ValueError("unresolved non-system dependency; binding is incomplete")


def runtime_files():
    root = Path(sysconfig.get_path("stdlib")).resolve()
    rows, extensions = [], []
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(item for item in dirs if item not in {"site-packages", "__pycache__", "test", "tests"})
        for name in sorted(files):
            file = Path(directory) / name
            if file.suffix not in {".py", ".so"}:
                continue
            if file.is_symlink():
                raise ValueError("unexpected symlink in bound Python runtime")
            rows.append({"relative": str(file.relative_to(root)), "sha256": sha_file(file)})
            if file.suffix == ".so":
                extensions.append(file)
    return sorted(rows, key=lambda row: row["relative"]), extensions


def licence_declaration(text):
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("  license "):
            selected, balance = [], 0
            for item in [line[len("  license "):], *lines[index + 1:]]:
                selected.append(item.rstrip())
                code = item.split("#", 1)[0]
                balance += code.count("[") + code.count("{") - code.count("]") - code.count("}")
                if balance == 0:
                    return "\n".join(selected).strip()
                if balance < 0:
                    break
            break
    raise ValueError("complete package licence declaration is absent")


def bind_tools(tools):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        raise ValueError("this exact native execution binding requires macOS arm64")
    if set(tools) != {"ffmpeg", "ffprobe", "oggenc"}:
        raise ValueError("exactly three codec/probe executables required")
    roots = {name: Path(file).resolve(strict=True) for name, file in tools.items()}
    roots["python"] = Path(sys.executable).resolve(strict=True)
    rows, extensions = runtime_files()
    nodes, seen, packages = {}, {}, {}

    def package_record(file):
        parts = file.parts
        if "Cellar" not in parts:
            raise ValueError("non-system binary is outside the declared package store")
        index = parts.index("Cellar")
        name, version = parts[index + 1:index + 3]
        package_id = name + "@" + version
        if package_id not in packages:
            root = Path(*parts[:index + 3])
            formula = root / ".brew" / (name + ".rb")
            declaration = licence_declaration(formula.read_text())
            notices = [item for item in root.iterdir() if item.is_file()
                       and item.name.upper().startswith(("LICENSE", "LICENCE", "COPYING", "COPYRIGHT"))]
            packages[package_id] = {
                "id": package_id, "name": name, "version": version,
                "formula_sha256": sha_file(formula),
                "licence_declaration": declaration,
                "notice_files": [{"name": item.name, "sha256": sha_file(item)}
                                 for item in sorted(notices)],
            }
        return package_id

    def visit(file, executable):
        file = file.resolve(strict=True)
        if file in seen:
            return seen[file]
        digest = sha_file(file)
        seen[file] = digest
        node = {"name": file.name, "sha256": digest, "bytes": file.stat().st_size,
                "package": package_record(file), "dependencies": []}
        nodes[digest] = node
        dependencies = []
        for token in dependency_paths(file):
            target = resolve_dependency(token, file, executable)
            if isinstance(target, str):
                dependencies.append(target)
            elif target != file:
                dependencies.append(visit(target, executable))
        node["dependencies"] = sorted(set(dependencies))
        return digest

    root_ids = {name: visit(file, file) for name, file in roots.items()}
    for file in extensions:
        visit(file, roots["python"])
    versions = {
        "ffmpeg": metadata([str(roots["ffmpeg"]), "-version"]).splitlines()[0],
        "ffprobe": metadata([str(roots["ffprobe"]), "-version"]).splitlines()[0],
        "oggenc": metadata([str(roots["oggenc"]), "--version"]).splitlines()[0],
        "python": platform.python_version(),
    }
    return {
        "schema_version": 1, "record_kind": "digital_development_native_tool_binding_v1",
        "operating_system": {"name": "macOS", "version": metadata(["/usr/bin/sw_vers", "-productVersion"]),
                             "build": metadata(["/usr/bin/sw_vers", "-buildVersion"]), "architecture": "arm64"},
        "versions": versions, "roots": root_ids,
        "python_stdlib": {"file_count": len(rows), "tree_sha256": hashlib.sha256(canonical(rows)).hexdigest(),
                          "scope": "all_py_and_so_excluding_site_packages_tests_and_caches"},
        "nodes": sorted(nodes.values(), key=lambda node: (node["name"], node["sha256"])),
        "packages": sorted(packages.values(), key=lambda item: item["id"]),
        "system_library_policy": "Exact macOS build binds dyld shared-cache libraries; they are not individually file-hashed.",
        "dynamic_plugin_loading_authorized": False, "audio_or_private_manifest_accessed": False,
        "codec_execution_performed": False, "tool_redistribution_authorized": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for tool in ("ffmpeg", "ffprobe", "oggenc"):
        parser.add_argument("--" + tool, type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.buffer.write(canonical(bind_tools(vars(args))))


if __name__ == "__main__":
    main()
