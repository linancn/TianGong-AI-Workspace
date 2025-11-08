"""
Command line utilities for the Tiangong AI Workspace.

The CLI provides quick checks for local prerequisites (Python, uv, Node.js)
and lists the external AI tooling CLIs that this workspace integrates with.
Edit this file to tailor the workspace to your own toolchain.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional, Tuple

import typer

from . import __version__
from .mcp_client import MCPToolClient
from .secrets import MCPServerSecrets, discover_secrets_path, load_secrets

app = typer.Typer(help="Tiangong AI Workspace CLI for managing local AI tooling.")
mcp_app = typer.Typer(help="Interact with Model Context Protocol services configured for this workspace.")
app.add_typer(mcp_app, name="mcp")

# (command, label) pairs for CLI integrations that the workspace cares about.
REGISTERED_TOOLS: Iterable[Tuple[str, str]] = (
    ("openai", "OpenAI CLI (Codex)"),
    ("gcloud", "Google Cloud CLI (Gemini)"),
    ("claude", "Claude Code CLI"),
)


def _get_version(command: str) -> str | None:
    """
    Return the version string for a CLI command if available.

    Many CLIs support `--version` and emit to stdout; others may use stderr.
    """
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None

    output = (result.stdout or result.stderr).strip()
    return output or None


@app.command()
def info() -> None:
    """Print a short summary of the workspace."""
    typer.echo(f"Tiangong AI Workspace v{__version__}")
    typer.echo("Unified CLI workspace for Codex, Gemini, and Claude Code automation.")
    typer.echo("")
    typer.echo(f"Project root : {Path.cwd()}")
    typer.echo(f"Python       : {sys.version.split()[0]} (requires >=3.12)")
    uv_path = shutil.which("uv")
    typer.echo(f"uv executable: {uv_path or 'not found in PATH'}")


@app.command("tools")
def list_tools() -> None:
    """List the external AI tooling CLIs tracked by the workspace."""
    typer.echo("Configured AI tooling commands:")
    for command, label in REGISTERED_TOOLS:
        typer.echo(f"- {label}: `{command}`")
    typer.echo("")
    typer.echo("Edit src/tiangong_ai_workspace/cli.py to customize this list.")


@app.command()
def check() -> None:
    """Validate local prerequisites such as Python, uv, Node.js, and AI CLIs."""
    typer.echo("Checking workspace prerequisites...\n")

    python_ok = sys.version_info >= (3, 12)
    python_status = "[OK]" if python_ok else "[WARN]"
    typer.echo(f"{python_status} Python {sys.version.split()[0]} (requires >=3.12)")

    uv_path = shutil.which("uv")
    uv_status = "[OK]" if uv_path else "[MISSING]"
    typer.echo(f"{uv_status} Astral uv: {uv_path or 'not found'}")

    node_path = shutil.which("node")
    if node_path:
        node_version = _get_version("node") or "version unknown"
        typer.echo(f"[OK] Node.js: {node_version} ({node_path})")
    else:
        typer.echo("[MISSING] Node.js: required for Node-based CLIs such as Claude Code")

    typer.echo("")
    typer.echo("AI coding toolchains:")
    for command, label in REGISTERED_TOOLS:
        location = shutil.which(command)
        status = "[OK]" if location else "[MISSING]"
        version = _get_version(command) if location else None
        detail = version or "not installed"
        typer.echo(f"{status} {label} ({command}): {location or detail}")

    typer.echo("")
    typer.echo("Update src/tiangong_ai_workspace/cli.py to adjust tool detection rules.")


# --------------------------------------------------------------------------- MCP


def _load_mcp_configs() -> Mapping[str, MCPServerSecrets]:
    try:
        secrets = load_secrets()
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED)
        raise typer.Exit(code=2)
    if not secrets.mcp_servers:
        secrets_path = discover_secrets_path()
        message = f"""No MCP services configured in {secrets_path}. Populate a *_mcp section (see `.sercrets/secrets.example.toml`)."""
        typer.secho(message, fg=typer.colors.YELLOW)
        raise typer.Exit(code=3)
    return secrets.mcp_servers


@mcp_app.command("services")
def list_mcp_services() -> None:
    """List configured MCP services from the secrets file."""

    configs = _load_mcp_configs()
    typer.echo("Configured MCP services:")
    for service in configs.values():
        typer.echo(f"- {service.service_name} ({service.transport}) -> {service.url}")


@mcp_app.command("tools")
def list_mcp_tools(service_name: str) -> None:
    """Enumerate tools exposed by a configured MCP service."""

    configs = _load_mcp_configs()
    if service_name not in configs:
        available = ", ".join(sorted(configs)) or "none"
        typer.secho(f"Service '{service_name}' not found. Available: {available}", fg=typer.colors.RED)
        raise typer.Exit(code=4)

    with MCPToolClient(configs) as client:
        tools = client.list_tools(service_name)

    if not tools:
        typer.echo(f"No tools advertised by service '{service_name}'.")
        return

    typer.echo(f"Tools available on '{service_name}':")
    for tool in tools:
        description = getattr(tool, "description", "") or ""
        if description:
            typer.echo(f"- {tool.name}: {description}")
        else:
            typer.echo(f"- {tool.name}")


@mcp_app.command("invoke")
def invoke_mcp_tool(
    service_name: str,
    tool_name: str,
    args: Optional[str] = typer.Option(None, "--args", "-a", help="JSON object with tool arguments."),
    args_file: Optional[Path] = typer.Option(
        None,
        "--args-file",
        path_type=Path,
        help="Path to a JSON file containing tool arguments.",
    ),
) -> None:
    """Invoke a tool exposed by a configured MCP service."""

    if args and args_file:
        typer.secho("Use either --args or --args-file, not both.", fg=typer.colors.RED)
        raise typer.Exit(code=5)

    payload: Mapping[str, Any] = {}
    if args:
        try:
            payload = json.loads(args)
        except json.JSONDecodeError as exc:
            typer.secho(f"Invalid JSON for --args: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=6) from exc
    elif args_file:
        try:
            payload = json.loads(args_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            typer.secho(f"Invalid JSON in file {args_file}: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=7) from exc
        except OSError as exc:
            typer.secho(f"Failed to read arguments file {args_file}: {exc}", fg=typer.colors.RED)
            raise typer.Exit(code=8) from exc

    configs = _load_mcp_configs()
    if service_name not in configs:
        available = ", ".join(sorted(configs)) or "none"
        typer.secho(f"Service '{service_name}' not found. Available: {available}", fg=typer.colors.RED)
        raise typer.Exit(code=9)

    with MCPToolClient(configs) as client:
        result, attachments = client.invoke_tool(service_name, tool_name, payload)

    typer.echo("Tool result:")
    typer.echo(_format_result(result))
    if attachments:
        typer.echo("\nAttachments:")
        for attachment in attachments:
            typer.echo(_format_result(attachment))


def _format_result(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, indent=2, ensure_ascii=True)
    except TypeError:
        return repr(value)


def main() -> None:
    """Entry point for python -m execution."""
    app()


if __name__ == "__main__":
    main()
