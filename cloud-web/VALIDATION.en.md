# Local verification record

Date: 2026-10-28. Patches are based on upstream `41b969f35c8285a44dca19d974059286d1f17d16` and use MaaEnd's Win32 compatibility bridge.

| Check | Result |
| --- | --- |
| Fetch upstream and apply three patch groups in an independent directory | Passed; `git diff --cached --check` reported no errors |
| Preserve independent upstream changes, stop on conflicts, protect work directories, and verify fixtures | 6 passed |
| Package update source, missing-host rejection, browser-state exclusion, and version records | 4 passed |
| Website startup, mouse, and frame policies | 32 passed |
| Release build of C++ Agent and WebView host | Passed using existing local SDKs and dependencies without changing their source |
| Native input and startup policy CTest | 2 passed |
| MaaUtils compatibility with Framework v5.14.3 | Both pin `f8994a38ddc6858800dfea8a04e958a0adbfb184` |
| GitHub workflow static validation | actionlint passed |
| Python linting and formatting, Markdown checks | Passed |
| SHA256 for three patches and 25 recognition images | Passed |

An upstream rename of input backend helper functions caused one patch conflict. The adaptation now preserves the upstream helper implementations and restores the cloud input branch. Regenerated patches applied without conflicts in a fresh directory.

The complete GitHub download, recognition regression, Go build, and distribution packaging workflow has not run yet and requires an Actions run after uploading. This record does not establish a complete GUI daily run or actual high-DPI desktop validation for the new combination.

Build and runtime directories are excluded by `.gitignore`. This record covers local checks before synchronization to the fork; subsequent cloud build results are recorded in GitHub Actions.
