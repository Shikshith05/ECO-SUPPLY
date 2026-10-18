"""Smoke tests: every page and the non-routing API endpoints respond (offline, no dataset needed)."""

import pytest

from backend.app import app


@pytest.fixture
def client():
    return app.test_client()


@pytest.mark.parametrize("path,marker", [
    ("/", b"Supply Chain Intelligence"),
    ("/producer", b"Demand Segments"),
    ("/consumer", b"Destination country"),
    ("/fleet", b"leaflet@1.9.4"),
])
def test_pages_are_served(client, path, marker):
    response = client.get(path)
    assert response.status_code == 200
    assert marker in response.data


def test_health_reports_artifacts(client):
    data = client.get("/api/health").get_json()
    assert data["status"] == "ok"
    assert set(data["artifacts"]) == {"delay_model", "demand_segments", "road_graph"}


def test_option_endpoints_degrade_gracefully_without_data(client, monkeypatch):
    from backend.routes import prediction_routes

    def missing():
        raise FileNotFoundError("no dataset")

    monkeypatch.setattr(prediction_routes, "_get_dataset", missing)
    for path, key in (("/api/predict/options/products", "products"),
                      ("/api/predict/options/cities", "cities"),
                      ("/api/predict/options/pincodes", "pincodes")):
        response = client.get(path)
        assert response.status_code == 200
        assert response.get_json()[key] == []


def test_weather_and_news_are_labelled_mock_without_keys(client):
    assert client.get("/api/recommend/weather").get_json()["source"] == "mock"
    assert client.get("/api/recommend/news").get_json()["source"] == "mock"


def test_demand_requires_inputs(client):
    assert client.post("/api/predict/demand", json={}).status_code == 400
