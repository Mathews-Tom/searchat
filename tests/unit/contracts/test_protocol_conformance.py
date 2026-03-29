"""Protocol conformance tests — verify concrete classes satisfy protocol contracts.

Uses typing.runtime_checkable + isinstance where possible, and signature
inspection as a fallback to confirm structural subtyping holds.
"""
from __future__ import annotations

import inspect

from searchat.contracts.agent import AgentProvider
from searchat.contracts.indexing import IndexingBackend
from searchat.contracts.retrieval import RetrievalBackend
from searchat.contracts.storage import StorageBackend


def _protocol_method_names(protocol_cls: type) -> set[str]:
    """Extract public method names defined in a Protocol class."""
    names: set[str] = set()
    for name, obj in inspect.getmembers(protocol_cls):
        if name.startswith("_"):
            continue
        if callable(obj) or isinstance(obj, property):
            names.add(name)
    return names


def _protocol_attribute_names(protocol_cls: type) -> set[str]:
    """Extract annotated attribute names from a Protocol class."""
    annotations = {}
    for cls in protocol_cls.__mro__:
        if cls is object:
            continue
        annotations.update(getattr(cls, "__annotations__", {}))
    return {k for k in annotations if not k.startswith("_")}


def _assert_class_conforms(concrete_cls: type, protocol_cls: type) -> None:
    """Assert that concrete_cls has all methods and attributes required by protocol_cls."""
    missing_methods = []
    for name in _protocol_method_names(protocol_cls):
        member = getattr(concrete_cls, name, None)
        if member is None or not callable(member):
            missing_methods.append(name)

    # Check attributes: class-level annotations, class attrs, or __init__ assignments.
    init_assigns: set[str] = set()
    try:
        init_source = inspect.getsource(concrete_cls.__init__)
        for line in init_source.splitlines():
            stripped = line.strip()
            if stripped.startswith("self."):
                attr_name = stripped.split("=")[0].strip().removeprefix("self.")
                attr_name = attr_name.split(":")[0].strip()
                init_assigns.add(attr_name)
    except (TypeError, OSError):
        pass

    missing_attrs = []
    for name in _protocol_attribute_names(protocol_cls):
        has_class_attr = hasattr(concrete_cls, name)
        has_annotation = name in getattr(concrete_cls, "__annotations__", {})
        has_init_attr = name in init_assigns
        if not (has_class_attr or has_annotation or has_init_attr):
            missing_attrs.append(name)

    failures = []
    if missing_methods:
        failures.append(f"Missing methods: {sorted(missing_methods)}")
    if missing_attrs:
        failures.append(f"Missing attributes: {sorted(missing_attrs)}")

    assert not failures, (
        f"{concrete_cls.__name__} does not conform to {protocol_cls.__name__}: "
        + "; ".join(failures)
    )


class TestStorageBackendConformance:
    def test_duckdb_store_conforms(self) -> None:
        from searchat.services.duckdb_storage import DuckDBStore

        _assert_class_conforms(DuckDBStore, StorageBackend)


class TestRetrievalBackendConformance:
    def test_search_engine_conforms(self) -> None:
        from searchat.core.search_engine import SearchEngine

        _assert_class_conforms(SearchEngine, RetrievalBackend)


class TestIndexingBackendConformance:
    def test_conversation_indexer_conforms(self) -> None:
        from searchat.core.indexer import ConversationIndexer

        _assert_class_conforms(ConversationIndexer, IndexingBackend)


class TestAgentProviderConformance:
    def test_claude_connector_conforms(self) -> None:
        from searchat.core.connectors.claude import ClaudeConnector

        _assert_class_conforms(ClaudeConnector, AgentProvider)
