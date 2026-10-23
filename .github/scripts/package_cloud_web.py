"""Package a clean Windows GUI build from this fork's pinned source commits."""

import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path


def git_revision(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def main() -> None:
    root = Path("install").resolve()
    if not root.is_dir() or root.is_symlink() or root.is_junction():
        raise RuntimeError("Expected a regular install directory")
    for path in root.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise RuntimeError(f"Unexpected link in package: {path.relative_to(root)}")
        if path.is_file() and (path.name in {".git", ".gitkeep"} or path.suffix == ".pdb"):
            path.unlink()

    launcher = '@echo off\nsetlocal\ncd /d "%~dp0"\nset "PATH=%~dp0maafw;%PATH%"\n'
    command = 'start "" "%~dp0MaaEnd.exe"\n'
    (root / "Start-MaaEnd.bat").write_text(launcher + command, encoding="ascii", newline="\r\n")
    (root / "Start-MaaEnd-CPU.bat").write_text(
        launcher + 'set "MAAEND_CLOUD_SOFTWARE_RENDERING=1"\n' + command,
        encoding="ascii",
        newline="\r\n",
    )
    required = (
        "MaaEnd.exe",
        "agent/go-service.exe",
        "agent/cpp-algo.exe",
        "agent/cloud-webview.exe",
        "agent/MaaUtils.dll",
        "agent/WebView2Loader.dll",
        "maafw/MaaFramework.dll",
        "maafw/MaaToolkit.dll",
        "maafw/MaaCustomControlUnit.dll",
        "resource_cloud_web/pipeline/nodes.json",
        "tasks/pretasks/LaunchCloudWeb.json",
    )
    for name in required:
        if not (root / name).is_file():
            raise RuntimeError(f"Missing build output: {name}")
    interface = json.loads((root / "interface.json").read_text(encoding="utf-8"))
    if interface["agent"][0]["child_exec"] != "agent/go-service":
        raise RuntimeError("The GUI must load the Go agent from agent/go-service")
    if not any(controller["name"] == "Win32-CloudWeb" for controller in interface["controller"]):
        raise RuntimeError("The cloud web controller is missing")

    forbidden = {".git", "debug", "logs", "user data", "cookies", "login data", "local state"}
    files = sorted(path for path in root.rglob("*") if path.is_file())
    for path in files:
        relative = path.relative_to(root)
        if any(part.lower() in forbidden or part.lower().endswith(".webview2") for part in relative.parts):
            raise RuntimeError(f"Unexpected private or diagnostic data: {relative}")
    manifest = {
        "maaend_commit": git_revision("rev-parse", "HEAD"),
        "mxu_repository": os.environ["MXU_REPOSITORY"],
        "mxu_commit": git_revision("-C", "cloud-mxu", "rev-parse", "HEAD"),
        "testset_commit": git_revision("-C", "tests/MaaEndTestset", "rev-parse", "HEAD"),
        "maafw_version": os.environ["MAAFW_VERSION"],
        "version": os.environ["PACKAGE_VERSION"],
        "files_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in files
        },
    }
    if manifest["mxu_commit"] != os.environ["MXU_COMMIT"]:
        raise RuntimeError("MXU checkout does not match the pinned source")
    (root / "build-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    destination = Path("dist")
    destination.mkdir(exist_ok=True)
    archive = destination / f"MaaEnd-CloudWeb-Windows-x64-{os.environ['GITHUB_RUN_NUMBER']}.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as stream:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                stream.write(path, path.relative_to(root).as_posix())
    with zipfile.ZipFile(archive) as stream:
        if stream.testzip() is not None:
            raise RuntimeError("Package CRC validation failed")
    print(f"Package: {archive}, bytes: {archive.stat().st_size}")
    print(f"SHA256: {hashlib.sha256(archive.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
