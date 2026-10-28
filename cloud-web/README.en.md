# MaaEnd CloudWeb adaptation

This directory stores the cloud website adaptation as patches instead of maintaining a separate copy of upstream source. GitHub Actions fetches MaaEnd, applies these patches, runs regression checks, and builds a Windows x64 GUI test package. MXU and MaaFramework use their official releases.

This is the independent adaptation layer in the `SENyiAi/MaaEnd` fork. Existing source remains at the repository root. Distribution packages use the upstream commit fetched during the build plus the patches in this directory; the exact commit is recorded in `cloud-build.json`.

## Build on GitHub

1. Open Actions on this repository's `v2` branch.
2. Open **Build CloudWeb GUI → Run workflow**.
3. Leave `upstream_ref` empty to use `v2` from `upstream.json`, or enter an upstream tag or full commit SHA.
4. After a successful run, download the `MaaEnd-CloudWeb-Windows-x64-*` artifact, extract its GUI ZIP, and run `MaaEnd.exe`.

Pushing changes to this directory or its workflow on `v2` starts a build. A daily schedule also fetches and builds upstream at 05:17 Beijing time. The workflow does not publish releases, submit upstream changes, or push synchronization branches. Scheduled workflows must exist on the default branch; GitHub may disable scheduled runs in inactive public repositories.

## Updates and failures

- `upstream.json`: upstream repository, branch, patch base, and dependency versions. The GUI is pinned to the tested v2.8.0 release. Framework follows its latest stable release with a MaaUtils compatibility check.
- `patches/0001-*`: host, input bridge, Agents, and build integration.
- `patches/0002-*`: controller, task entries, and cloud website resources.
- `patches/0003-*`: recognition tests and existing developer documentation.
- `fixtures/`: 25 existing game recognition images installed into the upstream testset without changing its remote or commit pointer.
- `adaptation.json`: SHA256 checksums for patches and recognition images.

Patches are applied with `git apply --3way --index` in an independent build directory. Compatible upstream changes merge automatically. Conflicts, dependency mismatches, test failures, and compilation failures stop the workflow without producing a GUI package. Inspect the failing step and diagnostics artifact. If needed, rebuild a previously successful upstream commit while resolving conflicts in a development checkout. Existing work directories are never reset or removed.

After reviewing changes in a MaaEnd development checkout, regenerate the patches with the following command, review their diff, and commit them. The script exports changes under `agent/`, `assets/`, `tools/`, `tests/`, and `docs/`, excluding submodules and upstream workflows. It does not change the development checkout's Git index. Untracked files under these directories are also candidates, so ensure they contain only intended deliverables before exporting.

```powershell
python scripts/export_adaptation.py --source D:/path/to/MaaEnd-development
```

When updating the patch base, resolve conflicts in an independent development checkout first, then set `patch_base` to its upstream commit. Add `--keep-fixtures` when exporting if recognition images have not changed, preserving the verified existing fixtures.

The package's `cloud-build.json` records the full upstream commit, adaptation repository commit, dependency versions, submodules, and patch checksums. File checksums and a ZIP SHA256 are also included. Packages point to this fork and remove upstream MirrorChyan update, announcement, and telemetry settings to avoid replacing the adaptation with the original upstream distribution or sending independent distribution data upstream. Builds use GitHub's automatic read-only temporary credential; no personal token is required.

## Local preparation and verification

Preparation uses only Python's standard library and Git. Builds reuse upstream uv, Node, Go, and CMake tooling. Runtime game code introduces no additional language. Run the following commands from this directory.

```powershell
python -m unittest discover -s tests -v
python scripts/prepare.py prepare --workdir .work/example --ref v2
git -C .work/example/upstream submodule update --init --recursive agent/cpp-algo/MaaUtils assets/resource/model tests/MaaEndTestset
python scripts/prepare.py fixtures --workdir .work/example
```

For offline replay, add `--source D:/path/to/local-upstream-repository` and select an existing local commit. Use a new work directory for each run; existing changes are never reset. Full build steps are in [cloud-web-build.yml](../.github/workflows/cloud-web-build.yml).

This adaptation comes from the tested compatibility bridge implementation with subsequent startup recovery fixes. It is separate from the #6841 CloudShell migration. Automated builds and regression checks do not replace full GUI daily runs on a logged-in account or validation of actual DPI and complex desktop scenarios. Linux can reuse the transport interfaces, but no Linux cloud website host is currently provided.

Windows requires WebView2 Runtime. Devices without a GPU can use `Start-CPU-mode.cmd` from the package.
