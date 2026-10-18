"""
Road-network distances for the Fleet Optimizer.

* The OSMnx drive graph is downloaded ONCE by `scripts/download_osm_graph.py`
  and saved as GraphML. Nothing in the web app ever downloads it.
* On first load the GraphML is converted to a compact cache (`.npz`: node
  coordinates plus a CSR adjacency matrix of edge lengths). Later loads read
  only the `.npz`, which takes about a second instead of parsing XML.
* Distance matrix: every stop snaps to its nearest graph node (KD-tree on
  local planar coordinates), then one multi-source Dijkstra
  (`scipy.sparse.csgraph.dijkstra`, implemented in C) gives directed
  shortest-path lengths between all snapped nodes. The straight-line snap
  distance is added at both ends. One-way streets make the matrix asymmetric.
* Only the largest strongly connected component is kept, so every node can
  reach every other node.
"""

from __future__ import annotations

import math
import os
import threading
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

from backend.config import ROOT, load_config

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = phi2 - phi1
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(h)))


def haversine_matrix(points: Sequence[Tuple[float, float]]) -> np.ndarray:
    lat = np.radians([p[0] for p in points])[:, None]
    lon = np.radians([p[1] for p in points])[:, None]
    dphi = lat.T - lat
    dlmb = lon.T - lon
    h = np.sin(dphi / 2) ** 2 + np.cos(lat) * np.cos(lat.T) * np.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.minimum(1.0, np.sqrt(h)))


def routing_config() -> dict:
    return load_config().get("routing") or {}


def graph_path() -> str:
    rel = routing_config().get("graph_path", "data/external/osm/bangalore_drive.graphml")
    return rel if os.path.isabs(rel) else os.path.join(ROOT, rel)


def cache_path() -> str:
    return graph_path() + ".npz"


@dataclass
class RoadNetwork:
    node_ids: np.ndarray        # OSM node ids
    lat: np.ndarray
    lon: np.ndarray
    adjacency: csr_matrix       # directed, edge length in km
    lat0: float

    def __post_init__(self) -> None:
        self._tree = cKDTree(self._project(self.lat, self.lon))

    # Equirectangular projection around the network's mean latitude: at city
    # scale its error is far below GPS noise, and it lets a KD-tree do the
    # nearest-node search.
    def _project(self, lat, lon) -> np.ndarray:
        lat = np.asarray(lat, dtype=float)
        lon = np.asarray(lon, dtype=float)
        x = np.radians(lon) * math.cos(math.radians(self.lat0)) * EARTH_RADIUS_KM
        y = np.radians(lat) * EARTH_RADIUS_KM
        return np.column_stack([x, y])

    @property
    def n_nodes(self) -> int:
        return len(self.node_ids)

    def nearest_nodes(self, points: Sequence[Tuple[float, float]]) -> Tuple[np.ndarray, np.ndarray]:
        lat = [p[0] for p in points]
        lon = [p[1] for p in points]
        dist, idx = self._tree.query(self._project(lat, lon))
        return idx.astype(np.int64), dist

    def distance_matrix(self, points: Sequence[Tuple[float, float]]):
        """Return (matrix_km, snapped node idx, snap km, predecessors)."""
        nodes, snap = self.nearest_nodes(points)
        unique, inverse = np.unique(nodes, return_inverse=True)
        dist, pred = dijkstra(self.adjacency, directed=True, indices=unique, return_predecessors=True)
        road = dist[:, unique][inverse][:, inverse]
        matrix = road + snap[:, None] + snap[None, :]
        np.fill_diagonal(matrix, 0.0)
        return matrix, nodes, snap, (unique, inverse, pred)

    def path_coords(self, pred_info, i: int, j: int) -> List[List[float]]:
        """Coordinates of the shortest road path between snapped points i and j."""
        unique, inverse, pred = pred_info
        row = pred[inverse[i]]
        target = unique[inverse[j]]
        source = unique[inverse[i]]
        seq = [target]
        while seq[-1] != source:
            prev = row[seq[-1]]
            if prev < 0:
                return []
            seq.append(prev)
        seq.reverse()
        return [[round(float(self.lat[k]), 6), round(float(self.lon[k]), 6)] for k in seq]

    # ── persistence ──────────────────────────────────────────────────────────
    def save_npz(self, path: str) -> None:
        a = self.adjacency
        np.savez_compressed(path, node_ids=self.node_ids, lat=self.lat, lon=self.lon,
                            data=a.data, indices=a.indices, indptr=a.indptr, shape=np.array(a.shape))

    @classmethod
    def load_npz(cls, path: str) -> "RoadNetwork":
        z = np.load(path)
        adj = csr_matrix((z["data"], z["indices"], z["indptr"]), shape=tuple(z["shape"]))
        return cls(z["node_ids"], z["lat"], z["lon"], adj, float(np.mean(z["lat"])))

    @classmethod
    def from_networkx(cls, graph) -> "RoadNetwork":
        """Build from an (unprojected) OSMnx MultiDiGraph, keeping its largest SCC."""
        import networkx as nx

        largest = max(nx.strongly_connected_components(graph), key=len)
        g = graph.subgraph(largest)
        node_ids = np.array(list(g.nodes), dtype=np.int64)
        index = {n: i for i, n in enumerate(node_ids.tolist())}
        lat = np.array([float(g.nodes[n]["y"]) for n in node_ids.tolist()])
        lon = np.array([float(g.nodes[n]["x"]) for n in node_ids.tolist()])
        best = {}
        for u, v, data in g.edges(data=True):
            if u == v:
                continue
            length_km = float(data.get("length", 0.0)) / 1000.0
            key = (index[u], index[v])
            if key not in best or length_km < best[key]:   # parallel edges: keep the shortest
                best[key] = length_km
        rows = np.fromiter((k[0] for k in best), dtype=np.int64, count=len(best))
        cols = np.fromiter((k[1] for k in best), dtype=np.int64, count=len(best))
        vals = np.fromiter(best.values(), dtype=float, count=len(best))
        adj = csr_matrix((vals, (rows, cols)), shape=(len(node_ids), len(node_ids)))
        return cls(node_ids, lat, lon, adj, float(lat.mean()))


# ── process-wide cache ────────────────────────────────────────────────────────

_LOCK = threading.Lock()
_NETWORK: Optional[RoadNetwork] = None
_LOAD_ERROR: Optional[str] = None
_LOADING = False


def load_network() -> Optional[RoadNetwork]:
    """
    Load the road network from disk once per process (thread-safe). Returns None
    if the graph file does not exist or cannot be read; it NEVER downloads.
    """
    global _NETWORK, _LOAD_ERROR, _LOADING
    if _NETWORK is not None:
        return _NETWORK
    with _LOCK:
        if _NETWORK is not None:
            return _NETWORK
        _LOADING = True
        try:
            gpath, cpath = graph_path(), cache_path()
            if os.path.exists(cpath) and (not os.path.exists(gpath) or os.path.getmtime(cpath) >= os.path.getmtime(gpath)):
                _NETWORK = RoadNetwork.load_npz(cpath)
            elif os.path.exists(gpath):
                import osmnx as ox

                _NETWORK = RoadNetwork.from_networkx(ox.load_graphml(gpath))
                _NETWORK.save_npz(cpath)
            else:
                _LOAD_ERROR = (f"Road graph not found at {os.path.relpath(gpath, ROOT)}; "
                               "run `python scripts/download_osm_graph.py` once to create it.")
                return None
            _LOAD_ERROR = None
            return _NETWORK
        except Exception as exc:  # corrupt file, missing optional dependency, ...
            _LOAD_ERROR = f"Could not load road graph: {exc}"
            return None
        finally:
            _LOADING = False


def warm_up_async() -> None:
    """Start loading the graph in the background so the first request is fast."""
    if os.path.exists(graph_path()) or os.path.exists(cache_path()):
        threading.Thread(target=load_network, name="road-graph-warmup", daemon=True).start()


def status() -> dict:
    return {
        "graph_file_present": os.path.exists(graph_path()),
        "cache_file_present": os.path.exists(cache_path()),
        "loaded": _NETWORK is not None,
        "loading": _LOADING,
        "nodes": _NETWORK.n_nodes if _NETWORK is not None else None,
        "edges": int(_NETWORK.adjacency.nnz) if _NETWORK is not None else None,
        "error": _LOAD_ERROR,
        "graph_path": os.path.relpath(graph_path(), ROOT),
        "fallback_detour_factor": float(routing_config()["haversine_detour_factor"]),
    }
