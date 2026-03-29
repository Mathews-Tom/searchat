from pathlib import Path
from types import SimpleNamespace


def test_build_retrieval_service_constructs_unified_search_engine(monkeypatch) -> None:
    from searchat.services.retrieval_service import build_retrieval_service

    created: list[tuple[Path, object]] = []

    class FakeUnifiedSearchEngine:
        def __init__(self, search_dir: Path, config: object) -> None:
            created.append((search_dir, config))

    monkeypatch.setitem(
        __import__("sys").modules,
        "searchat.core.unified_search",
        SimpleNamespace(UnifiedSearchEngine=FakeUnifiedSearchEngine),
    )

    cfg = SimpleNamespace(search=SimpleNamespace(engine="unified"))
    search_dir = Path("/tmp/searchat-test")
    service = build_retrieval_service(search_dir, config=cfg)
    assert isinstance(service, FakeUnifiedSearchEngine)
    assert created == [(search_dir, cfg)]
