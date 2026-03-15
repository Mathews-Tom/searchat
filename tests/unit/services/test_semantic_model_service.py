from __future__ import annotations

from types import SimpleNamespace

from searchat.services.semantic_model_service import (
    build_embedding_service,
    build_reranking_service,
)


def test_build_embedding_service_uses_configured_model_and_device(monkeypatch):
    calls: dict[str, object] = {}

    def _fake_sentence_transformer(model_name: str, *, device: str):
        calls["model_name"] = model_name
        calls["device"] = device
        return object()

    monkeypatch.setattr(
        "sentence_transformers.SentenceTransformer",
        _fake_sentence_transformer,
    )

    config = SimpleNamespace(
        embedding=SimpleNamespace(
            model="all-MiniLM-L6-v2",
            get_device=lambda: "cpu",
        )
    )

    service = build_embedding_service(config)

    assert service is not None
    assert calls == {"model_name": "all-MiniLM-L6-v2", "device": "cpu"}


def test_build_reranking_service_uses_configured_model(monkeypatch):
    calls: dict[str, object] = {}

    def _fake_cross_encoder(model_name: str):
        calls["model_name"] = model_name
        return object()

    monkeypatch.setattr(
        "sentence_transformers.CrossEncoder",
        _fake_cross_encoder,
        raising=False,
    )

    config = SimpleNamespace(
        reranking=SimpleNamespace(
            model="cross-encoder/ms-marco-MiniLM-L-6-v2",
        )
    )

    service = build_reranking_service(config)

    assert service is not None
    assert calls == {"model_name": "cross-encoder/ms-marco-MiniLM-L-6-v2"}
