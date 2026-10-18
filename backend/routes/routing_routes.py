"""
Fleet Optimizer route endpoints.

  POST /api/route/estimate              greedy nearest-neighbour (instant)
  POST /api/route/optimize              genetic algorithm (default)
  POST /api/route/optimize?solver=...   ga | ortools | greedy
  GET  /api/route/graph/status          road-graph status (never downloads)
"""

from flask import Blueprint, jsonify, request

from backend.services import route_optimizer
from backend.services.route_optimizer import RoutingInputError

routing_bp = Blueprint("routing", __name__)


def _plan(solver: str):
    try:
        payload = request.get_json(silent=True) or {}
        return jsonify({"status": "ok", "data": route_optimizer.plan_routes(payload, solver=solver)})
    except RoutingInputError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@routing_bp.route("/optimize", methods=["POST"])
def optimize_route():
    return _plan(request.args.get("solver", "ga").strip().lower())


@routing_bp.route("/estimate", methods=["POST"])
def estimate_route():
    return _plan("greedy")


@routing_bp.route("/graph/status", methods=["GET"])
def graph_route_status():
    # Reports whether the cached graph is on disk / loaded. It does NOT download:
    # the graph is created offline by scripts/download_osm_graph.py.
    return jsonify({"status": "ok", "data": route_optimizer.graph_status()})
