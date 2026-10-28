"""Apply the cloud adaptation to a fresh upstream checkout without changing a fork branch."""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(directory: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(directory), *args],
        capture_output=True,
        check=False,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")


def prepare(workdir: Path, ref: str = "", source: str = "") -> dict:
    config = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "adaptation.json").read_text(encoding="utf-8"))
    selected_ref = ref or config["ref"]
    if not selected_ref or selected_ref.startswith("-"):
        raise ValueError("Invalid upstream ref")
    if workdir.exists():
        raise ValueError("Work directory already exists; use a new directory to preserve previous results")
    workdir.mkdir(parents=True)
    report = {"repository": config["repository"], "ref": selected_ref, "patches": [], "status": "preparing"}
    report_path = workdir / "prepare.json"
    upstream = workdir / "upstream"
    upstream.mkdir()
    try:
        git(upstream, "init", "--quiet")
        git(upstream, "config", "core.autocrlf", "false")
        remote = str(Path(source).resolve()) if source else f"https://github.com/{config['repository']}.git"
        git(upstream, "remote", "add", "origin", remote)
        print(f"Fetching upstream ref: {selected_ref}", flush=True)
        git(
            upstream,
            "-c",
            "http.lowSpeedLimit=1024",
            "-c",
            "http.lowSpeedTime=60",
            "fetch",
            "--no-tags",
            "--filter=blob:none",
            "--depth=1",
            "origin",
            selected_ref,
        )
        commit = git(upstream, "rev-parse", "FETCH_HEAD^{commit}")
        git(upstream, "checkout", "--quiet", "--detach", commit)
        report["commit"] = commit
        # Three-way application needs the original preimage blobs, including
        # when the selected upstream ref is no longer descended from our base.
        git(upstream, "fetch", "--no-tags", "--filter=blob:none", "--depth=1", "origin", config["patch_base"])
        for entry in manifest["patches"]:
            patch = ROOT / entry["path"]
            if hashlib.sha256(patch.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError(f"Patch checksum mismatch: {entry['path']}")
            report["applying"] = entry["path"]
            write_json(report_path, report)
            print(f"Applying {entry['path']}", flush=True)
            git(upstream, "apply", "--3way", "--index", "--whitespace=error", str(patch))
            report["patches"].append(entry)
        git(upstream, "diff", "--cached", "--check")
        report.pop("applying", None)
        report["status"] = "prepared"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
        raise
    finally:
        write_json(report_path, report)
    return report


def install_fixtures(workdir: Path) -> int:
    root = workdir / "upstream" / "tests" / "MaaEndTestset"
    if not (root / ".git").exists():
        raise ValueError("Initialize the upstream testset submodule before installing fixtures")
    manifest = json.loads((ROOT / "adaptation.json").read_text(encoding="utf-8"))
    pending = []
    for entry in manifest["fixtures"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe fixture path")
        source = ROOT / "fixtures" / relative
        target = root / relative
        if not target.resolve().is_relative_to(root.resolve()):
            raise ValueError("Fixture target escapes testset")
        expected = entry["sha256"]
        if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Fixture checksum mismatch: {relative}")
        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Upstream changed fixture: {relative}; review instead of overwriting")
        pending.append((source, target))
    for source, target in pending:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return len(pending)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "fixtures"))
    parser.add_argument("--workdir", type=Path, default=ROOT / ".work")
    parser.add_argument("--ref", default="", help="Upstream branch, tag or commit")
    parser.add_argument("--source", default="", help="Local upstream repository for offline verification")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            report = prepare(args.workdir.resolve(), args.ref, args.source)
            print(f"Prepared upstream {report['commit']} with {len(report['patches'])} patches")
        else:
            print(f"Installed {install_fixtures(args.workdir.resolve())} cloud recognition fixtures")
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"Preparation failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
