"""
Baseline shortest-path routing using Dijkstra's algorithm.

This module represents traditional distance-only routing.
It ignores fuel, CO2, delay, load, and other constraints.

Used ONLY for baseline comparison.
"""

import heapq
from typing import Dict, List, Tuple, Any


class DijkstraBaseline:
    """
    Dijkstra-based shortest path solver (distance only).
    """

    def __init__(self, graph: Dict[Any, List[Tuple[Any, float]]]):
        """
        Parameters
        ----------
        graph : dict
            Adjacency list representation of the graph.
            {
              node: [(neighbor, distance), ...]
            }
        """
        self.graph = graph

    def shortest_path(
        self,
        source: Any,
        target: Any
    ) -> Tuple[List[Any], float]:
        """
        Compute shortest path from source to target using distance only.

        Returns
        -------
        path : list
            List of nodes representing the shortest path
        total_distance : float
            Total distance of the path
        """

        # Distance table
        dist = {node: float("inf") for node in self.graph}
        parent = {node: None for node in self.graph}

        dist[source] = 0.0
        pq = [(0.0, source)]  # (distance, node)

        while pq:
            curr_dist, u = heapq.heappop(pq)

            # Skip outdated queue entries
            if curr_dist > dist[u]:
                continue

            if u == target:
                break

            for v, weight in self.graph[u]:
                new_dist = dist[u] + weight

                if new_dist < dist[v]:
                    dist[v] = new_dist
                    parent[v] = u
                    heapq.heappush(pq, (new_dist, v))

        path = self._reconstruct_path(parent, source, target)
        return path, dist[target]

    @staticmethod
    def _reconstruct_path(
        parent: Dict[Any, Any],
        source: Any,
        target: Any
    ) -> List[Any]:
        """
        Reconstruct path from parent pointers.
        """
        path = []
        curr = target

        while curr is not None:
            path.append(curr)
            curr = parent[curr]

        path.reverse()

        if path[0] != source:
            return []  # No path exists

        return path
