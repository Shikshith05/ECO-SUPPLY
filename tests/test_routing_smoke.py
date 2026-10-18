"""API smoke tests for the Fleet Optimizer endpoints (no network, no road graph)."""

from backend.app import app

STOPS = [
    {"lat": 12.9716, "lng": 77.5946, "order_id": "A"},
    {"lat": 13.0055, "lng": 77.5721, "order_id": "B"},
    {"lat": 12.9784, "lng": 77.6408, "order_id": "C"},
]


def test_health_endpoint():
    response = app.test_client().get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_graph_status_endpoint_does_not_load_or_download():
    response = app.test_client().get("/api/route/graph/status")
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["loaded"] is False
    assert "fallback_detour_factor" in data


def test_quick_estimate_endpoint_keeps_old_payload_working():
    response = app.test_client().post("/api/route/estimate", json={
        "stops": STOPS, "vehicle_count": 1,
        "weights": {"alpha": 0.35, "beta": 0.25, "gamma": 0.20, "delta": 0.20},
    })
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["data"]["solver"] == "greedy"
    assert payload["data"]["routes"]
    assert "summary" in payload["data"]
    assert any("weights" in n.lower() for n in payload["data"]["notes"])


def test_optimize_endpoint_solvers():
    client = app.test_client()
    for query, solver in (("", "ga"), ("?solver=ortools", "ortools")):
        response = client.post(f"/api/route/optimize{query}",
                               json={"stops": STOPS, "vehicle_count": 2, "time_limit_s": 1})
        assert response.status_code == 200, response.get_json()
        assert response.get_json()["data"]["solver"] == solver


def test_bad_request_returns_400():
    response = app.test_client().post("/api/route/optimize?solver=nope", json={"stops": STOPS})
    assert response.status_code == 400
    assert response.get_json()["status"] == "error"


def test_empty_stops():
    response = app.test_client().post("/api/route/optimize", json={"stops": []})
    assert response.status_code == 200
    assert response.get_json()["data"]["routes"] == []
