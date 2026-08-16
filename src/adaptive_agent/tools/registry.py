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
from adaptive_agent.entities.base import ColumnDef, ColumnType, TableDef
from adaptive_agent.entities.menu_repository_adapter import EntityBackedMenuRepository
from adaptive_agent.entities.sqlite_repository import SqliteEntityRepository
from adaptive_agent.tools.base import ToolProvider
from adaptive_agent.tools.in_memory_provider import InMemoryToolProvider
from adaptive_agent.tools.kampuscrave_provider import KampusCraveToolProvider

# The table a fresh Business gets the first time its tool_provider resolves
# to "sqlite_menu" and no table is linked to it yet (e.g. before an owner
# has customized their own Database tables). Matches SqliteMenuRepository's
# old DEFAULT_TABLE/DEFAULT_COLUMNS shape so KampusCrave's live menu keeps
# the same table name across this migration.
DEFAULT_MENU_TABLE = TableDef(
    table_name="menu_items",
    display_name="Menu Items",
    tool_linked="sqlite_menu",
    columns=[
        ColumnDef(name="name", type=ColumnType.TEXT, required=True),
        ColumnDef(name="category", type=ColumnType.TEXT, required=True),
        ColumnDef(name="price", type=ColumnType.NUMBER, required=True),
        ColumnDef(name="stock_quantity", type=ColumnType.NUMBER, required=True),
    ],
)


class UnknownToolProviderError(Exception):
    pass


def resolve_or_create_menu_table(entity_repository: SqliteEntityRepository) -> str:
    """Finds the Business's ``tool_linked="sqlite_menu"`` table, creating
    the default one (matching SqliteMenuRepository's old shape) if this is
    the first time a Business with this tool_provider has run. Shared by
    _build_sqlite_menu_provider and scripts/seed_kampuscrave_menu.py so
    there's exactly one place that decides what "the menu table" means."""
    existing = next(
        (t.table_name for t in entity_repository.list_tables() if t.tool_linked == "sqlite_menu"),
        None,
    )
    if existing is not None:
        return existing
    entity_repository.create_table(DEFAULT_MENU_TABLE)
    return DEFAULT_MENU_TABLE.table_name


def _build_sqlite_menu_provider(
    storage_config: StorageConfig, db_path: Path
) -> ToolProvider:
    entity_repository = SqliteEntityRepository(db_path)
    table_name = resolve_or_create_menu_table(entity_repository)
    return KampusCraveToolProvider(EntityBackedMenuRepository(entity_repository, table_name))


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
