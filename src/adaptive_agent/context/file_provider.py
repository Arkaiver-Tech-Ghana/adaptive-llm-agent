"""The one concrete ContextProvider Day 1 ships: plain files on disk."""

from pathlib import Path

from adaptive_agent.context.base import ContextDocument


class ContextDirectoryNotFoundError(Exception):
    pass


class FileContextProvider:
    """Implements ContextProvider. Reads matching files under a directory."""

    def __init__(self, directory: Path, include_patterns: list[str]):
        self._directory = directory
        self._include_patterns = include_patterns

    def load(self) -> list[ContextDocument]:
        if not self._directory.is_dir():
            raise ContextDirectoryNotFoundError(
                f"Context directory not found: {self._directory}"
            )

        docs: list[ContextDocument] = []
        seen: set[Path] = set()
        for pattern in self._include_patterns:
            for path in sorted(self._directory.glob(pattern)):
                if not path.is_file() or path in seen:
                    continue
                seen.add(path)
                docs.append(
                    ContextDocument(
                        name=str(path.relative_to(self._directory)),
                        content=path.read_text(),
                    )
                )
        return docs
