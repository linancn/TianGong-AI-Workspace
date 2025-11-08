"""
Secrets loading utilities for the Tiangong AI Workspace.

This module centralises reading the local `.sercrets/secrets.toml` file so other
packages (such as CLI tools or MCP helpers) can obtain configuration without
needing to know the on-disk layout. The loader mirrors the structure defined in
`.sercrets/secrets.example.toml`.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, MutableMapping, Optional

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SECRETS_PATH = Path(os.environ.get("TIANGONG_SECRETS_FILE", WORKSPACE_ROOT / ".sercrets" / "secrets.toml"))


@dataclass(slots=True)
class OpenAISecrets:
    """Secrets required to authenticate with the OpenAI API."""

    api_key: str
    model: Optional[str] = None
    chat_model: Optional[str] = None
    deep_research_model: Optional[str] = None


@dataclass(slots=True)
class MCPServerSecrets:
    """Transport configuration needed to reach an MCP service."""

    service_name: str
    transport: str
    url: str
    api_key: Optional[str] = None
    api_key_header: str = "Authorization"
    api_key_prefix: Optional[str] = None
    timeout: Optional[float] = None

    def connection_payload(self) -> Dict[str, Any]:
        """
        Return keyword arguments expected by `mcp.client.streamable_http.streamablehttp_client`.
        """

        headers: MutableMapping[str, str] = {}
        if self.api_key:
            header_key = self.api_key_header or "Authorization"
            if self.api_key_prefix:
                headers[header_key] = f"{self.api_key_prefix} {self.api_key}"
            else:
                headers[header_key] = self.api_key

        payload: Dict[str, Any] = {"url": self.url}
        if headers:
            payload["headers"] = dict(headers)
        if self.timeout is not None:
            payload["timeout"] = self.timeout
        return payload


@dataclass(slots=True)
class Secrets:
    """Container bundling all supported secret entries."""

    openai: Optional[OpenAISecrets]
    mcp_servers: Mapping[str, MCPServerSecrets]


def discover_secrets_path() -> Path:
    """Return the secrets file path, raising if it does not exist."""

    secrets_path = DEFAULT_SECRETS_PATH
    if not secrets_path.exists():
        message = f"""Unable to locate secrets file at {secrets_path}. Create one based on `.sercrets/secrets.example.toml`."""
        raise FileNotFoundError(message)
    return secrets_path


def load_secrets(path: Optional[Path] = None) -> Secrets:
    """
    Load the secrets file and return strongly typed entries.

    Sections whose table name ends with `_mcp` are interpreted as MCP transport
    settings.
    """

    secrets_path = path or discover_secrets_path()
    with secrets_path.open("rb") as handle:
        data = tomllib.load(handle)

    openai_data = data.get("openai")
    openai_secrets = None
    if isinstance(openai_data, Mapping) and openai_data.get("api_key"):
        openai_secrets = OpenAISecrets(
            api_key=str(openai_data["api_key"]),
            model=_get_opt_str(openai_data, "model"),
            chat_model=_get_opt_str(openai_data, "chat_model"),
            deep_research_model=_get_opt_str(openai_data, "deep_research_model"),
        )

    mcp_entries: Dict[str, MCPServerSecrets] = {}
    for section_name, section in data.items():
        if not section_name.endswith("_mcp"):
            continue
        if not isinstance(section, Mapping):
            continue
        service_name = str(section.get("service_name") or section_name.removesuffix("_mcp"))
        transport = _require_str(section, "transport", section_name)
        url = _require_str(section, "url", section_name)
        mcp_entries[service_name] = MCPServerSecrets(
            service_name=service_name,
            transport=transport,
            url=url,
            api_key=_get_opt_str(section, "api_key"),
            api_key_header=_get_opt_str(section, "api_key_header") or "Authorization",
            api_key_prefix=_get_opt_str(section, "api_key_prefix"),
            timeout=_get_opt_float(section, "timeout"),
        )

    return Secrets(openai=openai_secrets, mcp_servers=dict(mcp_entries))


def _get_opt_str(container: Mapping[str, Any], key: str) -> Optional[str]:
    value = container.get(key)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return str(value)


def _get_opt_float(container: Mapping[str, Any], key: str) -> Optional[float]:
    value = container.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Expected a float-compatible value for '{key}'") from exc


def _require_str(container: Mapping[str, Any], key: str, section_name: str) -> str:
    value = container.get(key)
    if not value:
        raise ValueError(f"Section '{section_name}' must define '{key}'")
    if isinstance(value, str):
        return value
    return str(value)


__all__ = [
    "DEFAULT_SECRETS_PATH",
    "MCPServerSecrets",
    "OpenAISecrets",
    "Secrets",
    "discover_secrets_path",
    "load_secrets",
]
