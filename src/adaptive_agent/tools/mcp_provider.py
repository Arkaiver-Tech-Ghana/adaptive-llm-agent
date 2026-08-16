"""Dispatches a Tool that declares ``mcp_endpoint`` (business_config/schema.py's
``ToolConfig``) to a real MCP server over Streamable HTTP — the PRD's P0
"Tools are MCP-compatible" requirement, wired up as an *execution* backend
rather than a discovery mechanism. A Tool's ``name``/``description``/
``input_schema`` stay hand-authored in business.yaml exactly like any other
Tool, so ConfigPage's display, enable/disable, and the Tool Rail's
hallucination-guard DENY all keep working unchanged — only the call itself
proxies to the remote server's tool of the same name, over ``mcp_endpoint``.

Opens a fresh MCP session per call rather than holding a persistent
connection: this project's storage layer already favors "no connection
pool, no per-request pooling" simplicity (see sqlite_repository.py), and a
Tool call happens at most once per confirmed LLM turn — reconnect overhead
here is a non-issue, not a bottleneck worth a stateful client.
"""

import json
from typing import Any

import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.types import CallToolResult, TextContent

from adaptive_agent.tools.base import UnknownToolError


class MCPToolProvider:
    """Implements ToolProvider."""

    def __init__(self, endpoint_by_tool_name: dict[str, str]) -> None:
        self._endpoint_by_tool_name = endpoint_by_tool_name

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        endpoint = self._endpoint_by_tool_name.get(name)
        if endpoint is None:
            raise UnknownToolError(f"Unknown tool: {name!r}")
        return anyio.run(_call_over_mcp, endpoint, name, arguments)


async def _call_over_mcp(endpoint: str, name: str, arguments: dict[str, Any]) -> Any:
    async with (
        streamable_http_client(endpoint) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()
        result = await session.call_tool(name, arguments)
    return _unwrap_result(result)


def _unwrap_result(result: CallToolResult) -> Any:
    """Normalizes an MCP CallToolResult into the same JSON-friendly shape
    every other ToolProvider returns. Prefers structured_content (a real
    JSON value on the wire); falls back to parsing the text content blocks
    as JSON, then to the raw text, for servers that only ever answer in
    prose. An ``is_error`` result becomes a normal ``{"success": False,
    ...}`` result rather than an exception — matching this codebase's
    convention that only an unknown Tool *name* raises, never a bad or
    failed call."""
    if result.structured_content is not None:
        payload: Any = result.structured_content
    else:
        text = "".join(
            block.text for block in result.content if isinstance(block, TextContent)
        )
        try:
            payload = json.loads(text) if text else None
        except ValueError:
            payload = text

    if result.is_error:
        return {"success": False, "error": payload}
    if isinstance(payload, dict):
        return payload
    return {"result": payload}
