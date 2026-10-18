"""
Download the OSM drive network once, cache it to disk, and measure the
road-vs-straight-line detour factor used by the haversine fallback.

    .venv\\Scripts\\python scripts/download_osm_graph.py [--place "Bangalore, India"] [--pairs 2000]

Outputs
  data/external/osm/bangalore_drive.graphml       (gitignored, canonical graph)
  data/external/osm/bangalore_drive.graphml.npz   (gitignored, fast-load cache)
  results/osm_detour_factor.json                  (ratio statistics)

The detour factor is the ratio road distance / great-circle distance between
random pairs of graph nodes. Its median goes into config
`routing.haversine_detour_factor`, and is applied only when the graph is
unavailable.
"""

import argparse
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.services.road_network import RoadNetwork, cache_path, graph_path, haversine_km  # noqa: E402


def measure_detour(net: RoadNetwork, pairs: int, seed: int, min_km: float) -> dict:
    rng = np.random.default_rng(seed)
    ratios, crow, road_km = [], [], []
    sources = rng.choice(net.n_nodes, size=pairs, replace=False)
    targets = rng.choice(net.n_nodes, size=pairs, replace=False)
    from scipy.sparse.csgraph import dijkstra

    # Dijkstra in chunks of sources (a full row per source is ~1 MB per 100k nodes).
    road = np.empty(pairs)
    for start in range(0, pairs, 100):
        chunk = slice(start, start + 100)
        dist = dijkstra(net.adjacency, directed=True, indices=sources[chunk])
        road[chunk] = dist[np.arange(dist.shape[0]), targets[chunk]]
    for s, t, d in zip(sources, targets, road):
        straight = haversine_km(net.lat[s], net.lon[s], net.lat[t], net.lon[t])
        if straight < min_km or not np.isfinite(d):
            continue
        crow.append(straight)
        road_km.append(float(d))
        ratios.append(float(d) / straight)
    r = np.array(ratios)
    return {
        "pairs_requested": pairs,
        "pairs_used": int(len(r)),
        "min_straight_line_km": min_km,
        "seed": seed,
        "median_ratio": round(float(np.median(r)), 4),
        "mean_ratio": round(float(np.mean(r)), 4),
        "p10_ratio": round(float(np.percentile(r, 10)), 4),
        "p90_ratio": round(float(np.percentile(r, 90)), 4),
        "mean_straight_line_km": round(float(np.mean(crow)), 3),
        "mean_road_km": round(float(np.mean(road_km)), 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--place", default="Bangalore, India")
    ap.add_argument("--pairs", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--min-km", type=float, default=0.5, help="ignore very short pairs (snap noise dominates)")
    ap.add_argument("--force", action="store_true", help="re-download even if the GraphML exists")
    args = ap.parse_args()

    import osmnx as ox

    gpath = graph_path()
    os.makedirs(os.path.dirname(gpath), exist_ok=True)
    t0 = time.time()
    if os.path.exists(gpath) and not args.force:
        print(f"Loading existing {gpath}")
        graph = ox.load_graphml(gpath)
    else:
        print(f"Downloading drive network for {args.place!r} (takes a few minutes)...")
        graph = ox.graph_from_place(args.place, network_type="drive", simplify=True)
        ox.save_graphml(graph, gpath)
        print(f"Saved {gpath}")
    net = RoadNetwork.from_networkx(graph)
    net.save_npz(cache_path())
    print(f"Largest strongly connected component: {net.n_nodes} nodes, {net.adjacency.nnz} edges "
          f"(cache {cache_path()}) in {time.time() - t0:.0f}s")

    stats = measure_detour(net, args.pairs, args.seed, args.min_km)
    stats.update({"place": args.place, "nodes": net.n_nodes, "edges": int(net.adjacency.nnz)})
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    out = os.path.join(ROOT, "results", "osm_detour_factor.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)
    print(json.dumps(stats, indent=2))
    print(f"Wrote {out}. Set routing.haversine_detour_factor in config to median_ratio if it changed.")


if __name__ == "__main__":
    main()
