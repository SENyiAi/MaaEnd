# MaaEnd CloudWeb 独立适配

仓库保存云网页适配补丁，不复制维护整份上游源码。GitHub Actions 每次拉取 MaaEnd，应用补丁，运行回归检查，再构建 Windows x64 GUI 测试包。MXU 与 MaaFramework 使用官方发布版。

本目录为 `SENyiAi/MaaEnd` fork 的独立适配层。仓库根目录保留原有源码；实际分发包从构建时获取的上游提交加本目录补丁生成，具体提交见包内 `cloud-build.json`。

## 在 GitHub 构建

1. 在本仓库 `v2` 分支打开 Actions。
2. 打开 **Actions → Build CloudWeb GUI → Run workflow**。
3. `upstream_ref` 留空时跟随 `upstream.json` 中的 `v2`；也可填写上游标签或完整提交号。
4. 成功后下载 `MaaEnd-CloudWeb-Windows-x64-*` artifact，解开其中的 GUI ZIP，运行 `MaaEnd.exe`。

修改本目录或专用工作流并推送到 `v2` 会自动构建；每天北京时间 05:17 也会拉取上游并构建一次。暂不自动发布 Release，不向上游提交或自动推送同步分支。定时任务需要此工作流位于默认分支；长期不活跃的公开仓库可能被 GitHub 暂停定时执行。

## 更新与故障处理

- `upstream.json`：上游仓库、分支、补丁基准和 Framework 版本。Framework 跟随最新正式发布版，并检查 MaaUtils 兼容性。GUI 直接复用本次拉取的 MaaEnd `tools.setup.setup_workspace.install_mxu()` 安装结果，版本选择、下载和版本记录由上游脚本负责；不再单独固定 MXU 版本或重复下载。打包时仅将 `install/mxu.exe` 重命名为 `MaaEnd.exe`，并记录实际安装版本。
- `patches/0001-*`：宿主、输入桥接、Agent 与构建接入。
- `patches/0002-*`：控制器、任务入口与云网页专属资源。
- `patches/0003-*`：识别测试与原有开发文档。
- `fixtures/`：25 张既有游戏识别图，注入上游测试集；不修改测试集的远程地址或提交指针。
- `adaptation.json`：补丁与识别图 SHA256，防止遗漏或意外替换。

补丁通过 `git apply --3way --index` 合入独立构建目录。上游无冲突变更可自动合入；补丁冲突、依赖不匹配、测试或编译失败都会中止，不生成 GUI 包。打开失败步骤及诊断 artifact 查看原因。必要时先指定上一次成功的上游提交重建，再在开发副本处理冲突；不会清理或覆盖之前的工作目录。

修改适配后，在已人工审查的 MaaEnd 开发副本运行以下命令重新导出补丁，再检查补丁差异并提交。脚本仅导出 `agent/`、`assets/`、`tools/`、`tests/`、`docs/` 的变化，排除子模块和上游工作流，不修改开发副本的 Git index。此流程会将这些目录中的未跟踪文件也纳入候选，导出前须确认目录里只有拟交付代码。

```powershell
python scripts/export_adaptation.py --source D:/path/to/MaaEnd-development
```

更新补丁基准时，先在独立开发副本解决冲突，再把 `patch_base` 改为该副本的上游提交。若测试图未改，导出时附加 `--keep-fixtures`，沿用校验通过的既有图片。

构建包的 `cloud-build.json` 记录上游完整提交、适配仓库提交、依赖版本、子模块和补丁校验和；同目录还有文件校验清单及 ZIP SHA256。发布包指向自己的 GitHub 仓库，移除上游 MirrorChyan 更新源、公告和遥测配置，避免被上游原版覆盖或向上游发送独立版运行数据。构建只使用 GitHub 自动提供的只读临时凭据，不需要个人令牌。

## 本地准备与验证

准备脚本只依赖 Python 标准库和 Git。构建阶段复用上游 uv、Node、Go 与 CMake 工具链，游戏运行代码不引入新语言。以下命令在本目录执行。

```powershell
python -m unittest discover -s tests -v
python scripts/prepare.py prepare --workdir .work/example --ref v2
git -C .work/example/upstream submodule update --init --recursive agent/cpp-algo/MaaUtils assets/resource/model tests/MaaEndTestset
python scripts/prepare.py fixtures --workdir .work/example
```

离线重放可增加 `--source D:/path/to/local-upstream-repository` 并指定本地已有提交。每次使用新目录，不会重置现有修改。完整构建步骤见 [cloud-web-build.yml](../.github/workflows/cloud-web-build.yml)。

当前适配来自兼容桥成熟测试版本，包含后续启动恢复修复；这不是 #6841 CloudShell 迁移版。自动构建与回归检查不能代替登录账号后的完整日常及真实 DPI、复杂桌面场景验收。Linux 可复用现有传输接口，但目前不提供 Linux 云网页宿主。

Windows 需要系统已安装 WebView2 Runtime；无 GPU 设备可使用包内 `Start-CPU-mode.cmd`。
