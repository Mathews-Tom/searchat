"""Regression test for the default web server bind address.

DEFAULT_HOST used to be "0.0.0.0", so `searchat web` bound to every
network interface unless a user explicitly set SEARCHAT_HOST. Combined
with a fully unauthenticated API (no auth of any kind gates any
endpoint), this made every indexed conversation -- and every
state-changing endpoint (backup restore/delete, compaction, shutdown)
-- reachable by any device on the same network, not just the local
machine.

A live reproduction confirmed the concrete difference: starting a real
`searchat-web` process with SEARCHAT_HOST unset and inspecting the
actual bound socket (`lsof -iTCP:<port> -sTCP:LISTEN`) showed
`TCP *:<port> (LISTEN)` (all interfaces) against the pre-fix default,
and `TCP 127.0.0.1:<port> (LISTEN)` (loopback only) against the fix.
SEARCHAT_HOST=0.0.0.0 remains available for a user who explicitly wants
to expose the server on their network.
"""
from __future__ import annotations

from searchat.config.constants import DEFAULT_HOST


def test_default_host_is_loopback_only() -> None:
    assert DEFAULT_HOST == "127.0.0.1", (
        "the default bind address must be loopback-only; binding to "
        "0.0.0.0 by default exposes the fully unauthenticated API to "
        "every device on the local network"
    )


def test_default_host_is_not_all_interfaces() -> None:
    assert DEFAULT_HOST not in {"0.0.0.0", "::", ""}
