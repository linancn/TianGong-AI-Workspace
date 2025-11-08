"""
Synchronous bridge for interacting with Model Context Protocol servers.

This helper mirrors the usage patterns captured in the TianGong LCA spec coding
repository but is adapted for the Tiangong AI Workspace CLI. It provides a thin
wrapper over the official ``mcp`` Python SDK so callers can interact with remote
MCP tools without juggling async event loops directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, MutableMapping, Optional, Sequence

from anyio.from_thread import BlockingPortal, start_blocking_portal
from httpx import HTTPStatusError
from mcp import ClientSession, McpError, types
from mcp.client.streamable_http import streamablehttp_client

from .secrets import MCPServerSecrets


@dataclass(slots=True)
class _ServerConnection:
    client_cm: Any
    session_cm: Any
    session: ClientSession
    closed: bool = False

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        try:
            if self.session_cm is not None:
                self.session_cm.__exit__(None, None, None)
        finally:
            if self.client_cm is not None:
                self.client_cm.__exit__(None, None, None)


class MCPToolClient:
    """
    Synchronous wrapper around the official Python MCP client.

    Instantiate once per workflow and reuse for multiple tool invocations to
    benefit from the shared ``BlockingPortal``.
    """

    def __init__(
        self,
        servers: Mapping[str, MCPServerSecrets] | Iterable[MCPServerSecrets],
    ) -> None:
        if isinstance(servers, Mapping):
            configs = list(servers.values())
        else:
            configs = list(servers)
        self._configs: MutableMapping[str, MCPServerSecrets] = {}
        for config in configs:
            if config.service_name in self._configs:
                raise ValueError(f"Duplicate MCP service name '{config.service_name}' detected.")
            self._configs[config.service_name] = config
        self._portal_cm = start_blocking_portal()
        self._portal: BlockingPortal = self._portal_cm.__enter__()
        self._connections: MutableMapping[str, _ServerConnection] = {}
        self._closed = False

    # ------------------------------------------------------------------ lifecycle

    def close(self) -> None:
        """Close all active sessions and the underlying portal."""

        if self._closed:
            return
        self._closed = True
        try:
            for connection in list(self._connections.values()):
                try:
                    connection.close()
                except Exception:
                    pass  # pragma: no cover - best effort cleanup
            self._connections.clear()
        finally:
            self._portal_cm.__exit__(None, None, None)

    def __enter__(self) -> MCPToolClient:
        if self._closed:
            raise RuntimeError("Cannot enter a closed MCPToolClient")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    # ------------------------------------------------------------------ public API

    def list_tools(self, service_name: str) -> Sequence[types.Tool]:
        """Return the list of tools exposed by the remote server."""

        connection = self._ensure_connection(service_name)
        result = self._portal.call(connection.session.list_tools)
        tools = getattr(result, "tools", [])
        return tools

    def invoke_tool(
        self,
        service_name: str,
        tool_name: str,
        arguments: Mapping[str, Any] | None = None,
    ) -> tuple[Any, Optional[list[dict[str, Any]]]]:
        """
        Invoke a remote tool and return its payload along with optional attachments.
        """

        connection = self._ensure_connection(service_name)
        args = dict(arguments or {})
        try:
            result = self._portal.call(connection.session.call_tool, tool_name, args)
        except (McpError, HTTPStatusError) as exc:
            raise RuntimeError(f"MCP tool '{tool_name}' on '{service_name}' failed") from exc

        if result.isError:
            message = self._collect_text(result) or "Unknown MCP tool error"
            raise RuntimeError(f"MCP tool '{tool_name}' on '{service_name}' reported an error: {message}")

        payload = result.structuredContent
        if payload is None:
            payload = self._collect_text_blocks(result)
            if not payload:
                payload = ""
            elif len(payload) == 1:
                payload = payload[0]
        attachments = self._collect_attachments(result)
        return payload, attachments or None

    # ------------------------------------------------------------------ internals

    def _ensure_connection(self, service_name: str) -> _ServerConnection:
        if self._closed:
            raise RuntimeError("Cannot use MCPToolClient after close()")
        connection = self._connections.get(service_name)
        if connection is not None:
            return connection

        config = self._configs.get(service_name)
        if not config:
            raise ValueError(f"MCP service '{service_name}' is not configured.")

        if config.transport != "streamable_http":
            raise ValueError(f"Unsupported MCP transport '{config.transport}' for service '{service_name}'.")

        payload = config.connection_payload()
        client_async_cm = streamablehttp_client(
            payload["url"],
            headers=payload.get("headers"),
            timeout=payload.get("timeout"),
        )
        client_cm = self._portal.wrap_async_context_manager(client_async_cm)
        try:
            read_stream, write_stream, _ = client_cm.__enter__()
        except Exception:
            client_cm.__exit__(None, None, None)
            raise

        session_async_cm = ClientSession(read_stream, write_stream)
        session_cm = self._portal.wrap_async_context_manager(session_async_cm)
        try:
            session = session_cm.__enter__()
            self._portal.call(session.initialize)
        except Exception:
            session_cm.__exit__(None, None, None)
            client_cm.__exit__(None, None, None)
            raise

        connection = _ServerConnection(client_cm=client_cm, session_cm=session_cm, session=session)
        self._connections[service_name] = connection
        return connection

    @staticmethod
    def _collect_text(result: types.CallToolResult) -> str:
        blocks = MCPToolClient._collect_text_blocks(result)
        if not blocks:
            return ""
        if len(blocks) == 1:
            return blocks[0]
        return "\n".join(blocks)

    @staticmethod
    def _collect_text_blocks(result: types.CallToolResult) -> list[str]:
        texts: list[str] = []
        for content in result.content:
            if isinstance(content, types.TextContent):
                if content.text:
                    texts.append(content.text)
        return texts

    @staticmethod
    def _collect_attachments(result: types.CallToolResult) -> list[dict[str, Any]]:
        attachments: list[dict[str, Any]] = []
        for content in result.content:
            if isinstance(content, types.TextContent):
                continue
            if hasattr(content, "model_dump"):
                attachments.append(content.model_dump())
            else:  # pragma: no cover - defensive fallback
                attachments.append({"type": content.__class__.__name__})
        return attachments


__all__ = ["MCPToolClient"]
