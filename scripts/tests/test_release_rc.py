import io
from pathlib import Path
import sys
import tarfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import package_rc
import smoke_rc


class ReleaseBundleTests(unittest.TestCase):
    def test_refuses_dirty_source_and_stable_tags(self):
        with patch.object(package_rc.subprocess, "check_output", return_value=" M Cargo.toml\n"):
            with self.assertRaisesRegex(ValueError, "commit tracked"):
                package_rc.package(Path("."), Path("binary"), "aarch64-apple-darwin", "v0.1.0-rc.1")
        with self.assertRaisesRegex(ValueError, "explicit RC"):
            package_rc.package(Path("."), Path("binary"), "aarch64-apple-darwin", "v0.1.0")

    def test_publication_is_prerelease_only_and_gated(self):
        root = Path(__file__).parents[2]
        workflow = (root / ".github/workflows/release-rc.yml").read_text()
        self.assertIn("--prerelease --verify-tag", workflow)
        self.assertIn("Require successful exact-commit CI", workflow)
        self.assertIn("needs: build", workflow)
        self.assertIn("aarch64-apple-darwin", workflow)
        self.assertIn("x86_64-unknown-linux-gnu", workflow)
        self.assertNotIn("cargo publish", workflow)
        self.assertIn('"!v*-rc.*"', (root / ".github/workflows/release.yml").read_text())

    def test_archive_is_order_and_time_independent(self):
        a = package_rc.archive_bytes({"b": (b"second", 0o644), "lossytrace": (b"binary", 0o755)})
        b = package_rc.archive_bytes({"lossytrace": (b"binary", 0o755), "b": (b"second", 0o644)})
        self.assertEqual(a, b)
        with tarfile.open(fileobj=io.BytesIO(a), mode="r:gz") as archive:
            members = archive.getmembers()
            self.assertEqual([m.name for m in members], ["b", "lossytrace"])
            self.assertTrue(all(m.mtime == m.uid == m.gid == 0 for m in members))
            self.assertEqual(members[1].mode, 0o755)

    def test_macos_reproducibility_preserves_uuid_and_signature(self):
        workflow = (Path(__file__).parents[2] / ".github/workflows/release-rc.yml").read_text()
        self.assertIn("-Wl,-oso_prefix,$GITHUB_WORKSPACE/$build_dir/", workflow)
        self.assertIn("-Wl,-reproducible", workflow)
        self.assertIn('cmp "target-first/', workflow)
        self.assertNotIn("-no_uuid", workflow)
        self.assertNotIn("-no_adhoc_codesign", workflow)

    def test_unsafe_member_rejected(self):
        for name in ("/absolute", "../escape", "a/../../escape", "", "."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                package_rc.archive_bytes({name: (b"data", 0o644)})

    def test_dev_only_dependencies_are_excluded(self):
        packages = [{"id": i, "name": i, "version": "1"} for i in ("root", "normal", "build", "dev")]
        deps = [{"pkg": i, "dep_kinds": [{"kind": k}]} for i, k in (("normal", None), ("build", "build"), ("dev", "dev"))]
        nodes = [{"id": "root", "deps": deps}] + [{"id": i, "deps": []} for i in ("normal", "build", "dev")]
        actual = package_rc.runtime_packages({"packages": packages, "resolve": {"root": "root", "nodes": nodes}})
        self.assertEqual([p["name"] for p in actual], ["build", "normal"])

    def test_smoke_rejects_missing_required_files(self):
        data = package_rc.archive_bytes({"lossytrace": (b"binary", 0o755)})
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            with self.assertRaisesRegex(ValueError, "required"):
                smoke_rc.inspect_members(archive)

    def test_smoke_rejects_duplicate_members(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as archive:
            for _ in range(2):
                info = tarfile.TarInfo("same")
                info.size = 1
                archive.addfile(info, io.BytesIO(b"x"))
        data.seek(0)
        with tarfile.open(fileobj=data, mode="r") as archive:
            with self.assertRaisesRegex(ValueError, "duplicate"):
                smoke_rc.inspect_members(archive)

    def test_smoke_rejects_links(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as archive:
            info = tarfile.TarInfo("link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/outside"
            archive.addfile(info)
        data.seek(0)
        with tarfile.open(fileobj=data, mode="r") as archive:
            with self.assertRaisesRegex(ValueError, "unsafe"):
                smoke_rc.inspect_members(archive)


if __name__ == "__main__":
    unittest.main()
