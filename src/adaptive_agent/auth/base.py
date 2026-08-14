"""The pluggable auth axis — stub. Not wired into the Agent Core Day 1.

Ships with the Interface Layer on Day 3. This Protocol exists now so a
real AuthProvider slots in later without touching agent_core.py.
"""

from typing import Protocol


class AuthProvider(Protocol):
    def authenticate(self, credential: str) -> bool: ...
