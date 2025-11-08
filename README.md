# TianGong AI Workspace

## 项目简介
- 通用的 AI 编程 CLI 工作区，用于统一管理 Codex、Gemini CLI、Claude Code 等智能体工具。
- 基于 `uv` 管理 Python 依赖，默认打包了数据处理、可视化与实验探索需要的库，方便后续扩展。
- 提供 `tiangong-workspace` 命令行应用，用于查看环境信息并检查本地 CLI 集成情况。
- 跨平台安装脚本覆盖 Ubuntu、macOS 与 Windows，可按需安装 Node.js、Pandoc/MiKTeX 等可选组件。

## 目录结构
- `install_ubuntu.sh` / `install_macos.sh` / `install_windows.ps1`：一键安装脚本。
- `src/tiangong_ai_workspace/`：工作区 Python 包与 CLI 入口。
  - `__init__.py`：版本信息。
  - `cli.py`：`tiangong-workspace` 的 Typer 实现，可自定义要检测的外部 CLI。
- `pyproject.toml`：项目元数据与依赖定义（请勿改动现有依赖列表）。
- `LICENSE`：MIT 许可证。

## 快速安装
1. 克隆或下载本仓库。
2. 根据操作系统执行对应脚本（支持 `--full`、`--minimal`、`--with-pdf`、`--with-node` 等参数）：

```bash
# Ubuntu
bash install_ubuntu.sh --full

# macOS
bash install_macos.sh --full

# Windows（在管理员 PowerShell 中）
PowerShell -ExecutionPolicy Bypass -File install_windows.ps1 -Full
```

脚本会检查/安装：
- Python 3.12+
- Astral `uv`
- Node.js 22+（仅在需要 Node 生态 CLI 时安装）
- Pandoc + LaTeX/MiKTeX（用于 PDF/DOCX 导出，可选）

## 手动安装
若不使用脚本，可手动执行以下步骤：

```bash
uv sync                 # 安装 Python 依赖
uv run tiangong-workspace info
```

如需激活虚拟环境可运行 `source .venv/bin/activate`（在 Windows 上为 `.venv\Scripts\activate`）。

## CLI 使用
工作区提供 `tiangong-workspace` 命令，可快速了解环境状态：

```bash
uv run tiangong-workspace --help
uv run tiangong-workspace info      # 查看版本、项目路径等信息
uv run tiangong-workspace check     # 检查 Python、uv、Node.js 以及外部 CLI
uv run tiangong-workspace tools     # 查看已配置的外部 CLI 列表
```

`check` 命令默认检测 `openai`（Codex）、`gcloud`（Gemini）与 `claude`（Claude Code）执行文件，可自行扩展。

## 自定义集成
1. 编辑 `src/tiangong_ai_workspace/cli.py` 中的 `REGISTERED_TOOLS`，新增或修改要检测的 CLI。
2. 根据需要扩展 `check()` 命令的逻辑，例如调用自定义脚本、校验凭证等。
3. 重新运行 `uv run tiangong-workspace check` 验证配置。

## 开发提示
- 依赖管理：`uv add <package>` / `uv remove <package>`。
- 每次修改程序后，务必按以下顺序运行并全部通过：

```bash
uv run black .
uv run ruff check
uv run pytest
```

- 测试运行：`uv run pytest`（默认提供空测试环境，可按需添加用例）。
- 更新代码的同时请同步维护 `AGENTS.md` 与 `README.md`，确保两者记录的信息始终与仓库状态一致。

## 许可证
本项目采用 [MIT License](LICENSE)。
