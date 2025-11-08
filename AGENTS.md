# TianGong AI Workspace — Agent Guide

## Overview
- Unified developer workspace that coordinates Codex, Gemini, Claude Code, and other AI tooling.
- Python 3.12+ project managed entirely with `uv`; do **not** rely on `pip`, `poetry`, or `conda`.
- Primary entry point is the Typer-based CLI `tiangong-workspace`, exposed via `uv run`.

## Repository Layout
- `src/tiangong_ai_workspace/`: Workspace Python package and CLI logic.
  - `cli.py`: User-facing commands plus a nested `mcp` subcommand for interacting with remote MCP services.
  - `mcp_client.py`: Synchronous wrapper around the official MCP Python SDK.
  - `secrets.py`: Loads `.sercrets/secrets.toml` for OpenAI keys and `*_mcp` service configs.
- `.sercrets/`: Local-only secrets directory (not for version control).
- Installation scripts (`install_ubuntu.sh`, `install_macos.sh`, `install_windows.ps1`) bootstrap Python, uv, Node.js, and optional tooling.

## Tooling Workflow
Run everything through `uv` to ensure the correct environment:

```bash
uv sync                  # one-time setup or when dependencies change
uv run tiangong-workspace --help
```

After **every** code change, run the following **in order** and ensure they pass:

```bash
uv run black .
uv run ruff check
uv run pytest
```

These commands must complete successfully before sharing updates or opening pull requests.

## MCP & Secrets
- Populate `.sercrets/secrets.toml` using `.sercrets/secrets.example.toml` as a template.
- Keep secrets out of version control; the example file documents expected fields.
- Use `uv run tiangong-workspace mcp services|tools|invoke` to discover and call configured MCP tools.

## Maintenance Rules
- Whenever you modify program code, synchronize documentation: update both `AGENTS.md` *and* `README.md` so they reflect the latest behaviour, commands, and workflows.
- Respect existing dependency declarations in `pyproject.toml`; use `uv add/remove` for changes.
- Prefer ASCII in source files unless the file already uses other encodings.

## Helpful Commands
```bash
uv run tiangong-workspace info      # summarize environment
uv run tiangong-workspace check     # validate Python/uv/Node + external CLIs
uv run tiangong-workspace mcp tools <service>   # enumerate remote MCP tools
```

This guide is optimized for automated agents; keep it current whenever the project evolves.
