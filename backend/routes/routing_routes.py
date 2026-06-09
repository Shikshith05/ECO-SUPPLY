"""Fleet Optimizer route endpoints."""

import os
import sys
from flask import Blueprint, jsonify, request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from services.route_optimizer import greedy_estimate, graph_status, load_bangalore_graph, optimize_routes

routing_bp = Blueprint("routing", __name__)


@routing_bp.route("/optimize", methods=["POST"])
def optimize_route():
    try:
        payload = request.get_json(silent=True) or {}
        stops = payload.get("stops", [])
        vehicle_count = int(payload.get("vehicle_count", 1) or 1)
        weights = payload.get("weights") or {}

        if not isinstance(stops, list) or not stops:
            return jsonify({"status": "ok", "data": {"routes": [], "summary": {"distance_km": 0.0, "fuel_cost": 0.0, "co2_kg": 0.0, "delay_risk": 0.0, "baseline_co2_saved": 0.0}}})

        result = optimize_routes(stops, vehicle_count=vehicle_count, weights=weights)
        return jsonify({"status": "ok", "data": result})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@routing_bp.route("/graph/status", methods=["GET"])
def graph_route_status():
    try:
        load_bangalore_graph()
        return jsonify({"status": "ok", "data": graph_status()})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@routing_bp.route("/estimate", methods=["POST"])
def estimate_route():
    try:
        payload = request.get_json(silent=True) or {}
        stops = payload.get("stops", [])
        vehicle_count = int(payload.get("vehicle_count", 1) or 1)
        weights = payload.get("weights") or {}

        result = greedy_estimate(stops, vehicle_count=vehicle_count, weights=weights)
        return jsonify({"status": "ok", "data": result})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
