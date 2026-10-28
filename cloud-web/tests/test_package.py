import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import package as distribution
from prepare import write_json


class PackagingTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.install = self.work / "upstream" / "install"
        self.output = self.work / "output"
        write_json(self.work / "prepare.json", {"status": "prepared", "commit": "a" * 40})
        for name in distribution.REQUIRED:
            if name == "MaaEnd.exe" or name.startswith("maafw/"):
                continue
            path = self.install / name
            if name == "resource_cloud_web/pipeline":
                path.mkdir(parents=True)
            elif name == "interface.json":
                write_json(
                    path,
                    {
                        "github": "https://github.com/MaaEnd/MaaEnd",
                        "mirrorchyan_rid": "MaaEnd",
                        "telemetry": {"sentry": {}},
                        "welcome": "upstream announcement",
                        "controller": [],
                    },
                )
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"test binary")
        deps = self.work / "upstream" / "deps"
        (deps / "bin").mkdir(parents=True)
        (deps / "bin" / "MaaFramework.dll").write_bytes(b"framework")
        (deps / "bin" / "MaaWin32ControlUnit.dll").write_bytes(b"control-unit")
        (deps / "share" / "MaaAgentBinary").mkdir(parents=True)
        (self.install / "mxu.exe").write_bytes(b"unmodified gui")
        write_json(self.install / "version.json", {"versions": {"mxu": "upstream-gui-test"}})
        self.enterContext(patch.object(distribution.subprocess, "run"))
        self.enterContext(patch.object(distribution, "git", return_value="b" * 40))

    def build(self):
        return distribution.package(self.work, "example/cloud-fork", "fw-test", self.output)

    def test_package_uses_own_update_source_and_records_versions(self):
        archive = self.build()
        with zipfile.ZipFile(archive) as bundle:
            interface = json.loads(bundle.read("interface.json"))
            self.assertEqual(interface["github"], "https://github.com/example/cloud-fork")
            self.assertNotIn("mirrorchyan_rid", interface)
            self.assertNotIn("telemetry", interface)
            self.assertNotIn("welcome", interface)
            self.assertEqual(bundle.read("MaaEnd.exe"), b"unmodified gui")
            self.assertNotIn("mxu.exe", bundle.namelist())
            provenance = json.loads(bundle.read("cloud-build.json"))
            self.assertEqual(provenance["framework"], "fw-test")
            self.assertEqual(provenance["gui"], "upstream-gui-test")
            self.assertEqual(json.loads(bundle.read("version.json"))["versions"]["mxu"], "upstream-gui-test")
            checksums = json.loads(bundle.read("cloud-files.sha256.json"))
            self.assertIn("agent/cloud-webview.exe", checksums)
        self.assertTrue(archive.with_suffix(".zip.sha256").exists())

    def test_missing_host_does_not_produce_package(self):
        (self.install / "agent" / "cloud-webview.exe").unlink()
        with self.assertRaisesRegex(ValueError, "Incomplete GUI"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_browser_state_does_not_enter_package(self):
        (self.install / "agent" / "cloud-webview.exe.WebView2").mkdir()
        with self.assertRaisesRegex(ValueError, "Unexpected runtime state"):
            self.build()
        self.assertFalse(self.output.exists())

    def test_official_update_repository_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "own repository"):
            distribution.package(self.work, "MaaEnd/MaaEnd", "fw", self.output)

    def test_missing_upstream_gui_does_not_download_a_replacement(self):
        (self.install / "mxu.exe").unlink()
        with self.assertRaisesRegex(ValueError, "Missing upstream-installed MXU"):
            self.build()
        distribution.subprocess.run.assert_not_called()
        self.assertFalse(self.output.exists())

    def test_missing_upstream_gui_version_is_rejected(self):
        write_json(self.install / "version.json", {"versions": {}})
        with self.assertRaisesRegex(ValueError, "Missing upstream-installed MXU version"):
            self.build()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
