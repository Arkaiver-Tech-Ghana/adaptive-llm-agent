"""Maps a Business Config's ``tool_provider`` string to a concrete
ToolProvider instance. Mirrors llm/registry.py's build_llm_provider
pattern: keyed by provider *type*, not business_id, so a new Business
onboards by picking an existing type in its business.yaml — no code
change — the same way a new Business picks ``llm.provider: google``
without anyone touching llm/registry.py. A genuinely new backend shape
still needs a new ToolProvider class and one new entry here; that's
irreducible execution logic, not per-business hardcoding.
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


def _build_sqlite_menu_provider(
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
    "in_memory": lambda storage_config, db_path: InMemoryToolProvider(),
    "sqlite_menu": _build_sqlite_menu_provider,
}


def build_tool_provider(
    provider_type: str, storage_config: StorageConfig, db_path: Path
) -> ToolProvider:
    try:
        factory = _PROVIDERS[provider_type]
    except KeyError:
        known = ", ".join(sorted(_PROVIDERS))
        raise UnknownToolProviderError(
            f"Unknown tool provider type '{provider_type}'. Known types: {known}"
        ) from None
    return factory(storage_config, db_path)
