"""Assemble a clean Windows GUI distribution from CI build outputs."""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from prepare import ROOT, git, write_json

REQUIRED = (
    "MaaEnd.exe",
    "agent/cloud-webview.exe",
    "agent/cpp-algo.exe",
    "agent/go-service.exe",
    "agent/WebView2Loader.dll",
    "agent/MaaUtils.dll",
    "maafw/MaaFramework.dll",
    "maafw/MaaWin32ControlUnit.dll",
    "resource_cloud_web/pipeline",
    "interface.json",
)


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def package(workdir: Path, repository: str, framework_tag: str, output: Path) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("Repository must be owner/name")
    if repository.lower() == "maaend/maaend":
        raise ValueError("Use your own repository as the distribution update source")
    if output.exists():
        raise ValueError("Output directory already exists; use a new directory")
    report = json.loads((workdir / "prepare.json").read_text(encoding="utf-8"))
    if report["status"] != "prepared":
        raise ValueError("Cannot package an unsuccessful adaptation")
    upstream = workdir / "upstream"
    install = upstream / "install"
    if (install / "MaaEnd.exe").exists():
        raise ValueError("Install directory already contains a GUI; use fresh CI build outputs")
    # Consume MaaEnd's own installer output and its version record, without downloading a second GUI.
    gui = install / "mxu.exe"
    if not gui.is_file():
        raise ValueError("Missing upstream-installed MXU; run MaaEnd's install_mxu first")
    versions = json.loads((install / "version.json").read_text(encoding="utf-8"))["versions"]
    gui_tag = versions.get("mxu")
    if not isinstance(gui_tag, str) or not gui_tag.strip():
        raise ValueError("Missing upstream-installed MXU version")
    shutil.copytree(upstream / "deps" / "bin", install / "maafw", dirs_exist_ok=True)
    shutil.copytree(upstream / "deps" / "share" / "MaaAgentBinary", install / "maafw" / "MaaAgentBinary")
    # MXU remains the released, unmodified binary; only the distribution name changes.
    gui.rename(install / "MaaEnd.exe")
    shutil.copy2(ROOT / "LICENSE", install / "CLOUD-ADAPTATION-LICENSE.txt")
    shutil.copy2(ROOT / "NOTICE.md", install / "CLOUD-ADAPTATION-NOTICE.md")
    (install / "Start-CPU-mode.cmd").write_bytes(
        b'@echo off\r\nset MAAEND_CLOUD_SOFTWARE_RENDERING=1\r\nstart "" "%~dp0MaaEnd.exe"\r\n'
    )
    for license_name in ("LICENSE", "LICENSE.md"):
        source = upstream / "deps" / license_name
        if source.is_file():
            target = install / "third-party" / "MaaFramework"
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target / license_name)
    subprocess.run(["uv", "run", "--frozen", "tools/merge_pipeline.py", "install"], cwd=upstream, check=True)
    version = f"v0.1.0-cloud.{report['commit'][:8]}"
    subprocess.run(
        [
            "uv",
            "run",
            "--frozen",
            "tools/fill_interface.py",
            "--version",
            version,
            "--interface",
            "install/interface.json",
        ],
        cwd=upstream,
        check=True,
    )
    interface_path = install / "interface.json"
    interface = json.loads(interface_path.read_text(encoding="utf-8"))
    interface["github"] = f"https://github.com/{repository}"
    for key in ("mirrorchyan_rid", "mirrorchyan_multiplatform", "telemetry", "welcome"):
        interface.pop(key, None)
    write_json(interface_path, interface)
    missing = [path for path in REQUIRED if not (install / path).exists()]
    if missing:
        raise ValueError(f"Incomplete GUI distribution: {', '.join(missing)}")
    forbidden = {"debug", "logs", "config", ".cache", "maa_pi_config.json", "maa_option.json"}
    for path in install.rglob("*"):
        if path.is_symlink() or path.name in forbidden or path.name.endswith(".WebView2"):
            raise ValueError(f"Unexpected runtime state or link in distribution: {path.relative_to(install)}")
    report = dict(report, framework=framework_tag, gui=gui_tag, version=version, distribution=repository)
    try:
        report["adaptation_commit"] = git(ROOT, "rev-parse", "HEAD")
    except RuntimeError:
        report["adaptation_commit"] = "local-uncommitted"
    report["submodules"] = git(upstream, "submodule", "status")
    write_json(install / "cloud-build.json", report)
    write_json(
        install / "cloud-files.sha256.json",
        {
            str(path.relative_to(install)).replace("\\", "/"): digest(path)
            for path in sorted(install.rglob("*"))
            if path.is_file()
        },
    )
    output.mkdir(parents=True)
    name = f"MaaEnd-CloudWeb-win-x86_64-{report['commit'][:8]}"
    archive = Path(shutil.make_archive(str(output / name), "zip", install))
    (output / f"{name}.zip.sha256").write_text(f"{digest(archive)}  {archive.name}\n", encoding="ascii")
    shutil.copy2(install / "cloud-build.json", output / "cloud-build.json")
    return archive


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, default=ROOT / ".work")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--framework-tag", required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    print(package(args.workdir.resolve(), args.repository, args.framework_tag, args.output.resolve()))
