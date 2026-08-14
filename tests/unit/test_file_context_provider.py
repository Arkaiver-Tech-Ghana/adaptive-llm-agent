from pathlib import Path

import pytest

from adaptive_agent.context.file_provider import (
    ContextDirectoryNotFoundError,
    FileContextProvider,
)

FIXTURES = Path(__file__).parent / "fixtures" / "context_files"


def test_load_returns_matching_documents():
    provider = FileContextProvider(FIXTURES, include_patterns=["*.md", "*.txt"])
    docs = provider.load()
    names = {d.name for d in docs}
    assert names == {"sample.md", "notes.txt"}


def test_include_patterns_filter():
    provider = FileContextProvider(FIXTURES, include_patterns=["*.md"])
    docs = provider.load()
    assert [d.name for d in docs] == ["sample.md"]
    assert "sample context content" in docs[0].content


def test_missing_directory_raises():
    provider = FileContextProvider(FIXTURES / "does-not-exist", include_patterns=["*.md"])
    with pytest.raises(ContextDirectoryNotFoundError):
        provider.load()
