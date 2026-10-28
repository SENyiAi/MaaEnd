"""Regenerate reviewed patches from a development checkout using a temporary Git index."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from prepare import ROOT, write_json

SUBMODULES = {"agent/cpp-algo/MaaUtils", "assets/resource/model", "tests/MaaEndTestset", "Android/MaaFwApp"}
PREFIXES = ("agent/", "assets/", "tools/", "tests/", "docs/")


def run(source: Path, *args: str, env: dict | None = None, data: bytes | None = None) -> bytes:
    return subprocess.run(
        ["git", "-C", str(source), *args], check=True, stdout=subprocess.PIPE, env=env, input=data
    ).stdout


def export(source: Path, keep_fixtures: bool = False) -> None:
    config = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))
    base = config["patch_base"]
    changed = run(source, "diff", "--ignore-submodules=all", "--name-only", "-z", base)
    untracked = run(source, "ls-files", "--others", "--exclude-standard", "-z")
    paths = sorted(
        path
        for path in set((changed + untracked).decode("utf-8").split("\0"))
        if path.startswith(PREFIXES) and path not in SUBMODULES
    )
    groups = {"host-and-agent": [], "resources": [], "tests-and-docs": []}
    for path in paths:
        if (source / path).is_symlink():
            raise ValueError(f"Refusing symlink in adaptation: {path}")
        group = (
            "resources"
            if path.startswith("assets/")
            else ("tests-and-docs" if path.startswith(("tests/", "docs/")) else "host-and-agent")
        )
        groups[group].append(path)
    patches = []
    with tempfile.TemporaryDirectory() as temporary:
        # Never stage files into the developer's real index.
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(temporary) / "index"))
        run(source, "read-tree", base, env=env)
        for path in paths:
            if (source / path).is_file():
                data = (source / path).read_bytes()
                if Path(path).suffix in {".cpp", ".h", ".go", ".py", ".md", ".json", ".mts", ".mjs", ".txt", ".cmake"}:
                    data = data.replace(b"\r\n", b"\n").rstrip(b"\n") + b"\n"
                blob = run(source, "hash-object", "-w", "--stdin", data=data).decode().strip()
                run(source, "update-index", "--add", "--cacheinfo", "100644", blob, path, env=env)
            else:
                run(source, "update-index", "--force-remove", "--", path, env=env)
        for number, (name, group) in enumerate(groups.items(), 1):
            if not group:
                continue
            data = run(source, "diff", "--cached", "--binary", "--full-index", base, "--", *group, env=env)
            relative = f"patches/{number:04d}-{name}.patch"
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            patches.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest(), "files": len(group)})
    if keep_fixtures:
        fixtures = json.loads((ROOT / "adaptation.json").read_text(encoding="utf-8"))["fixtures"]
        for fixture in fixtures:
            if hashlib.sha256((ROOT / "fixtures" / fixture["path"]).read_bytes()).hexdigest() != fixture["sha256"]:
                raise ValueError(f"Fixture checksum mismatch: {fixture['path']}")
        write_json(ROOT / "adaptation.json", {"patches": patches, "fixtures": fixtures})
        print(f"Exported {len(paths)} adapted files; retained {len(fixtures)} reviewed fixtures")
        return
    fixture_repo = source / "tests" / "MaaEndTestset"
    fixture_base = run(source, "rev-parse", f"{base}:tests/MaaEndTestset").decode().strip()
    fixture_paths = run(fixture_repo, "diff", "--name-only", "--diff-filter=A", "-z", fixture_base, "HEAD")
    fixtures = []
    for path in sorted(filter(None, fixture_paths.decode("utf-8").split("\0"))):
        if not path.startswith("Win32/Official_CN/云终末地_") or not path.endswith(".png"):
            raise ValueError(f"Unexpected fixture; review before export: {path}")
        target = ROOT / "fixtures" / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture_repo / path, target)
        fixtures.append({"path": path, "sha256": hashlib.sha256(target.read_bytes()).hexdigest()})
    write_json(ROOT / "adaptation.json", {"patches": patches, "fixtures": fixtures})
    print(f"Exported {len(paths)} adapted files and {len(fixtures)} recognition fixtures")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--keep-fixtures", action="store_true", help="Reuse existing verified fixtures after rebasing")
    args = parser.parse_args()
    export(args.source.resolve(), args.keep_fixtures)
