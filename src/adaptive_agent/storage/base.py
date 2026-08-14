"""The pluggable storage axis — stub. Not wired into the Agent Core Day 1.

Storage is keyed by database-id + schema-identity per docs/adr/0003. This
Protocol exists now so a real StorageBackend slots in later without
touching agent_core.py.
"""

from typing import Any, Protocol


class StorageBackend(Protocol):
    def get(self, key: str) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
