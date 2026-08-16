"""Maps a business_id to a concrete ToolProvider instance. Mirrors
llm/registry.py's build_llm_provider pattern.

Replaces load_conversation_runtime's old hardcoded ``InMemoryToolProvider()``
for every Business — a DB-backed KampusCrave Tool can't share hotel's
dict-backed provider, so each Business now selects its own provider here
instead of the core conversation code special-casing a Business by name.
"""

from collections.abc import Callable
from pathlib import Path

from adaptive_agent.business_config.schema import StorageConfig
from adaptive_agent.menu.sqlite_repository import DEFAULT_TABLE, SqliteMenuRepository
from adaptive_agent.tools.base import ToolProvider
from adaptive_agent.tools.in_memory_provider import InMemoryToolProvider
from adaptive_agent.tools.kampuscrave_provider import KampusCraveToolProvider


class UnknownToolProviderError(Exception):
    pass


def _build_kampuscrave_provider(
    storage_config: StorageConfig, db_path: Path
) -> ToolProvider:
    return KampusCraveToolProvider(
        SqliteMenuRepository(
            db_path,
            table=storage_config.table or DEFAULT_TABLE,
            columns=storage_config.columns,
        )
    )


_PROVIDERS: dict[str, Callable[[StorageConfig, Path], ToolProvider]] = {
    "hotel": lambda storage_config, db_path: InMemoryToolProvider(),
    "kampuscrave": _build_kampuscrave_provider,
}


def build_tool_provider(
    business_id: str, storage_config: StorageConfig, db_path: Path
) -> ToolProvider:
    try:
        factory = _PROVIDERS[business_id]
    except KeyError:
        known = ", ".join(sorted(_PROVIDERS))
        raise UnknownToolProviderError(
            f"Unknown tool provider for business '{business_id}'. Known businesses: {known}"
        ) from None
    return factory(storage_config, db_path)
