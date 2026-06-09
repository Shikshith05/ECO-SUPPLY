import os
import sys

from backend.app import app


def test_health_endpoint():
    client = app.test_client()
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"


def test_graph_status_endpoint():
    client = app.test_client()
    response = client.get("/api/route/graph/status")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert "data" in payload


def test_quick_estimate_endpoint():
    client = app.test_client()
    response = client.post(
        "/api/route/estimate",
        json={
            "stops": [
                {"lat": 12.9716, "lng": 77.5946, "order_id": "A"},
                {"lat": 13.0055, "lng": 77.5721, "order_id": "B"},
            ],
            "vehicle_count": 1,
            "weights": {"alpha": 0.35, "beta": 0.25, "gamma": 0.20, "delta": 0.20},
        },
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert "summary" in payload["data"]
    assert payload["data"]["routes"]
