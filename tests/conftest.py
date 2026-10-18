"""
Shared test fixtures.

Tests must never touch the network: the OSM road-graph loader is replaced
with a stub that reports "graph unavailable", and any outbound socket
connection raises immediately so an accidental download fails loudly
instead of silently slowing the suite down.
"""

import os
import socket

import pytest

# Must be set before backend.app is imported: no background graph loading in tests.
os.environ["EPOCH_GRAPH_WARMUP"] = "0"


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
    """Pretend the cached OSM graph is not available (no disk load, no download)."""
    from backend.services import road_network

    monkeypatch.setattr(road_network, "load_network", lambda: None)
