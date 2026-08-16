"""Unit tests for MCPToolProvider's result-normalization logic
(_unwrap_result, exercised directly against hand-built CallToolResults —
every branch: structured_content, text-only JSON, plain-text fallback, and
is_error), plus one true round trip against a real MCP server running
in-process over Streamable HTTP (an ASGI transport, no real socket) to
prove the wiring — session init, tools/call, response parsing — actually
works end to end.
"""

import httpx2
import pytest
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, TextContent

from adaptive_agent.tools.base import UnknownToolError
from adaptive_agent.tools.mcp_provider import MCPToolProvider, _unwrap_result


def _text_result(text: str, is_error: bool = False) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=text)], is_error=is_error)


def test_unwrap_prefers_structured_content():
    result = CallToolResult(
        content=[TextContent(type="text", text="ignored")],
        structured_content={"success": True, "value": 42},
    )
    assert _unwrap_result(result) == {"success": True, "value": 42}


def test_unwrap_parses_json_text_when_no_structured_content():
    result = _text_result('{"available": true, "count": 3}')
    assert _unwrap_result(result) == {"available": True, "count": 3}


def test_unwrap_falls_back_to_raw_text_for_non_json_prose():
    result = _text_result("Sorry, no rooms available.")
    assert _unwrap_result(result) == {"result": "Sorry, no rooms available."}


def test_unwrap_is_error_becomes_a_normal_failure_result():
    result = _text_result("boom", is_error=True)
    assert _unwrap_result(result) == {"success": False, "error": "boom"}


def test_call_with_unknown_tool_name_raises_without_any_network_call():
    provider = MCPToolProvider({"book_room": "http://127.0.0.1:1/mcp"})
    with pytest.raises(UnknownToolError):
        provider.call("check_room_availability", {})


# --- Real MCP round trip, in-process over an ASGI transport -------------

_MCP_SERVER = MCPServer("test-server")


@_MCP_SERVER.tool()
def echo_tool(message: str) -> str:
    return f"echo: {message}"


_MCP_APP = _MCP_SERVER.streamable_http_app(
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False)
)


@pytest.fixture
def patch_transport_to_asgi(monkeypatch):
    """Redirects mcp_provider's ``streamable_http_client`` to talk to the
    in-process ASGI app (no real socket) instead of the given URL — the
    module-level name is what _call_over_mcp actually calls, so patching it
    here covers the exact code path MCPToolProvider.call() uses."""
    import mcp.client.streamable_http as real_transport

    def _asgi_streamable_http_client(_endpoint, **_ignored):
        transport = httpx2.ASGITransport(app=_MCP_APP)
        http_client = httpx2.AsyncClient(transport=transport, base_url="http://127.0.0.1")
        return real_transport.streamable_http_client(
            "http://127.0.0.1/mcp", http_client=http_client
        )

    import adaptive_agent.tools.mcp_provider as provider_module

    monkeypatch.setattr(provider_module, "streamable_http_client", _asgi_streamable_http_client)


def test_call_round_trips_through_a_real_mcp_server(patch_transport_to_asgi):
    import anyio

    from adaptive_agent.tools.mcp_provider import _call_over_mcp

    async def run():
        async with _MCP_SERVER.session_manager.run():
            return await _call_over_mcp("http://ignored/mcp", "echo_tool", {"message": "hi"})

    result = anyio.run(run)
    assert result == {"result": "echo: hi"}
