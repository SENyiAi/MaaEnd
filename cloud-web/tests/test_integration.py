import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import prepare


class PreparationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.kit = self.root / "kit"
        self.kit.mkdir()
        self.work = self.root / "work"
        self.enterContext(patch.object(prepare, "ROOT", self.kit))
        self.git("init", "--quiet")
        self.git("config", "user.name", "integration-test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        self.file = self.source / "input.txt"
        self.file.write_text("before\n" + "unchanged\n" * 12 + "tail\n", encoding="utf-8", newline="\n")
        self.git("add", ".")
        self.git("commit", "--quiet", "-m", "upstream base")
        self.base = self.git("rev-parse", "HEAD")
        self.file.write_text(self.file.read_text().replace("before", "cloud"), encoding="utf-8", newline="\n")
        data = subprocess.check_output(["git", "-C", str(self.source), "diff", "--full-index"])
        (self.kit / "cloud.patch").write_bytes(data)
        self.manifest = {
            "patches": [{"path": "cloud.patch", "sha256": hashlib.sha256(data).hexdigest()}],
            "fixtures": [],
        }
        prepare.write_json(self.kit / "adaptation.json", self.manifest)
        prepare.write_json(
            self.kit / "upstream.json",
            {
                "repository": "example/upstream",
                "ref": "HEAD",
                "patch_base": self.base,
            },
        )
        self.git("restore", "input.txt")

    def git(self, *args):
        return prepare.git(self.source, *args)

    def run_prepare(self):
        return prepare.prepare(self.work, source=str(self.source))

    def test_updated_upstream_keeps_independent_changes(self):
        self.file.write_text(self.file.read_text().replace("tail", "new upstream tail"), encoding="utf-8", newline="\n")
        self.git("commit", "--quiet", "-am", "upstream update")
        expected_commit = self.git("rev-parse", "HEAD")
        # A dirty source checkout must stay dirty and must not leak into the build.
        (self.source / "private-state.txt").write_text("do not export", encoding="utf-8")
        report = self.run_prepare()
        result = (self.work / "upstream" / "input.txt").read_text()
        self.assertTrue(result.startswith("cloud\n"))
        self.assertTrue(result.endswith("new upstream tail\n"))
        self.assertEqual(report["commit"], expected_commit)
        self.assertEqual(report["status"], "prepared")
        self.assertFalse((self.work / "upstream" / "private-state.txt").exists())
        self.assertEqual(self.git("status", "--porcelain"), "?? private-state.txt")

    def test_conflict_stops_with_diagnostics_and_preserves_source(self):
        self.file.write_text(
            self.file.read_text().replace("before", "upstream changed"), encoding="utf-8", newline="\n"
        )
        self.git("commit", "--quiet", "-am", "conflicting upstream update")
        with self.assertRaises(RuntimeError):
            self.run_prepare()
        report = json.loads((self.work / "prepare.json").read_text())
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["applying"], "cloud.patch")
        self.assertTrue(self.file.read_text().startswith("upstream changed\n"))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_changed_patch_is_rejected(self):
        with (self.kit / "cloud.patch").open("ab") as stream:
            stream.write(b"unexpected content\n")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            self.run_prepare()
        self.assertEqual((self.work / "upstream" / "input.txt").read_text(), self.file.read_text())

    def test_existing_work_directory_is_not_reset(self):
        self.run_prepare()
        marker = self.work / "keep.txt"
        marker.write_text("keep", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.run_prepare()
        self.assertEqual(marker.read_text(), "keep")

    def test_fixtures_require_initialization_and_do_not_replace_changed_upstream(self):
        with self.assertRaisesRegex(ValueError, "Initialize"):
            prepare.install_fixtures(self.work)
        fixture = self.kit / "fixtures" / "Win32" / "image.png"
        fixture.parent.mkdir(parents=True)
        fixture.write_bytes(b"test image")
        self.manifest["fixtures"] = [
            {"path": "Win32/image.png", "sha256": hashlib.sha256(fixture.read_bytes()).hexdigest()}
        ]
        prepare.write_json(self.kit / "adaptation.json", self.manifest)
        testset = self.work / "upstream" / "tests" / "MaaEndTestset"
        testset.mkdir(parents=True)
        (testset / ".git").write_text("gitdir: test", encoding="utf-8")
        self.assertEqual(prepare.install_fixtures(self.work), 1)
        target = testset / "Win32" / "image.png"
        target.write_bytes(b"changed upstream image")
        with self.assertRaisesRegex(ValueError, "Upstream changed fixture"):
            prepare.install_fixtures(self.work)
        self.assertEqual(target.read_bytes(), b"changed upstream image")

    def test_fixture_path_cannot_escape_testset(self):
        testset = self.work / "upstream" / "tests" / "MaaEndTestset"
        testset.mkdir(parents=True)
        (testset / ".git").write_text("gitdir: test", encoding="utf-8")
        self.manifest["fixtures"] = [{"path": "../../escape.png", "sha256": "unused"}]
        prepare.write_json(self.kit / "adaptation.json", self.manifest)
        with self.assertRaisesRegex(ValueError, "Unsafe"):
            prepare.install_fixtures(self.work)


if __name__ == "__main__":
    unittest.main()
