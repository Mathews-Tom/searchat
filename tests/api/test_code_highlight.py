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
