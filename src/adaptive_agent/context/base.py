"""The pluggable "context files" axis."""

from typing import Protocol

from pydantic import BaseModel


class ContextDocument(BaseModel):
    name: str
    content: str


class ContextProvider(Protocol):
    def load(self) -> list[ContextDocument]: ...
