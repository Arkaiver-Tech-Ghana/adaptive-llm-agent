"""Lets a Business's Tool dispatch span more than one ToolProvider. Every
Business already gets a domain-specific provider chosen by ``tool_provider``
(tools/registry.py), the generic entity-CRUD provider for whatever Custom
Tables it owns (tools/entity_crud_provider.py), *and* an MCP provider for
whichever of its Tools declare ``mcp_endpoint`` (tools/mcp_provider.py) —
none of them needs to know about the others.
"""

from typing import Any

from adaptive_agent.tools.base import ToolProvider, UnknownToolError


class CompositeToolProvider:
    """Implements ToolProvider. Tries each provider in order; the first
    that doesn't raise UnknownToolError wins. The last provider's
    UnknownToolError propagates as-is if none of them recognize the name."""

    def __init__(self, providers: list[ToolProvider]) -> None:
        if not providers:
            raise ValueError("CompositeToolProvider needs at least one provider")
        self._providers = providers

    def call(self, name: str, arguments: dict[str, Any]) -> Any:
        for provider in self._providers[:-1]:
            try:
                return provider.call(name, arguments)
            except UnknownToolError:
                continue
        return self._providers[-1].call(name, arguments)
