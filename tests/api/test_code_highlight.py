from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from searchat.api.app import app


@pytest.fixture
def client():
    return TestClient(app)


def test_code_highlight_honors_fence_language(client):
    resp = client.post(
        "/api/code/highlight",
        json={
            "blocks": [
                {
                    "code": "def hello():\n    return 1\n",
                    "language": "python",
                    "language_source": "fence",
                }
            ]
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1

    r0 = data["results"][0]
    assert r0["guessed"] is False
    assert r0["html"]


def test_code_highlight_guesses_for_unlabelled_blocks(client):
    resp = client.post(
        "/api/code/highlight",
        json={
            "blocks": [
                {
                    "code": "function test() {\n  console.log('hi')\n}\n",
                    "language": None,
                    "language_source": "detected",
                }
            ]
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["results"]) == 1

    r0 = data["results"][0]
    assert r0["guessed"] is True
    assert r0["html"]
    assert r0["used_language"]


def test_code_highlight_empty_code_returns_plaintext(client):
    resp = client.post(
        "/api/code/highlight",
        json={
            "blocks": [
                {
                    "code": "   ",
                    "language": "python",
                    "language_source": "fence",
                }
            ]
        },
    )

    assert resp.status_code == 200
    data = resp.json()
    r0 = data["results"][0]
    assert r0["used_language"] == "plaintext"
    assert r0["guessed"] is False
    assert r0["html"] == ""


def test_code_highlight_invalid_fence_language_falls_back_to_text(client):
    resp = client.post(
        "/api/code/highlight",
        json={
            "blocks": [
                {
                    "code": "hello\n",
                    "language": "notalanguage",
                    "language_source": "fence",
                }
            ]
        },
    )

    assert resp.status_code == 200
    r0 = resp.json()["results"][0]
    assert r0["used_language"] == "plaintext"
    assert r0["guessed"] is False
    assert r0["html"]


def test_code_highlight_guess_lexer_failure_falls_back_to_text(client, monkeypatch: pytest.MonkeyPatch):
    import pygments.lexers

    def boom(_code: str):
        raise RuntimeError("no lexer")

    monkeypatch.setattr(pygments.lexers, "guess_lexer", boom)
    resp = client.post(
        "/api/code/highlight",
        json={
            "blocks": [
                {
                    "code": "SELECT 1;\n",
                    "language": None,
                    "language_source": "detected",
                }
            ]
        },
    )

    assert resp.status_code == 200
    r0 = resp.json()["results"][0]
    assert r0["used_language"] == "plaintext"
    assert r0["guessed"] is True
    assert r0["html"]


def test_code_highlight_missing_pygments_returns_500(client, monkeypatch: pytest.MonkeyPatch):
    import sys

    monkeypatch.setitem(sys.modules, "pygments", None)
    monkeypatch.setitem(sys.modules, "pygments.formatters", None)
    monkeypatch.setitem(sys.modules, "pygments.lexers", None)

    resp = client.post(
        "/api/code/highlight",
        json={
            "blocks": [
                {
                    "code": "x",
                    "language": None,
                    "language_source": "detected",
                }
            ]
        },
    )
    assert resp.status_code == 500
    assert "Pygments is required" in resp.json()["detail"]
