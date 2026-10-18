"""
Shared test fixtures.

Tests must never touch the network: the OSM road-graph loader is replaced
with a stub that reports "graph unavailable", and any outbound socket
connection raises immediately so an accidental download fails loudly
instead of silently slowing the suite down.
"""

import socket

import pytest


class NetworkBlockedError(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _block_network(monkeypatch):
    real_connect = socket.socket.connect

    def guarded_connect(self, address):
        host = address[0] if isinstance(address, tuple) else address
        if host in ("127.0.0.1", "localhost", "::1"):
            return real_connect(self, address)
        raise NetworkBlockedError(f"Network access attempted in tests: {address!r}")

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)


@pytest.fixture(autouse=True)
def _no_osm_graph(monkeypatch):
    """Pretend the OSM graph is not available (no download, no disk load)."""
    from backend.routes import routing_routes
    from backend.services import route_optimizer

    def unavailable():
        return {"loaded": False, "cached": False, "graph": None, "reason": "disabled in tests"}

    # Patch both the service module and the name the route module imported.
    monkeypatch.setattr(route_optimizer, "load_bangalore_graph", unavailable)
    monkeypatch.setattr(routing_routes, "load_bangalore_graph", unavailable)
