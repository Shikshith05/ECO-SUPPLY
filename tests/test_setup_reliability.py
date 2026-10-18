"""Fresh-clone reliability: config fallback and safe numeric column access."""

import pandas as pd

from backend import config as app_config
from backend.utils.feature_engineering import add_demand_score
from backend.utils.preprocessing import numeric_column


def test_config_falls_back_to_example(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config, "CONFIG_PATH", str(tmp_path / "missing.yaml"))
    app_config.load_config.cache_clear()
    try:
        assert app_config.config_path() == app_config.EXAMPLE_PATH
        assert "app" in app_config.load_config()
    finally:
        app_config.load_config.cache_clear()


def test_placeholder_api_keys_are_treated_as_missing(monkeypatch):
    monkeypatch.setattr(app_config, "load_config", lambda: {"apis": {"k": "YOUR_KEY_HERE", "real": "abc123"}})
    assert app_config.api_key("k") is None
    assert app_config.api_key("real") == "abc123"
    assert app_config.api_key("absent") is None


def test_numeric_column_missing_column_returns_aligned_series():
    df = pd.DataFrame({"a": [1, 2, 3]}, index=[10, 20, 30])
    s = numeric_column(df, "missing", 4.0)
    assert list(s.index) == [10, 20, 30]
    assert s.tolist() == [4.0, 4.0, 4.0]
    # Series methods that crashed with the old `pd.to_numeric(df.get(col, 0))` pattern:
    s.fillna(0).clip(lower=0)


def test_numeric_column_coerces_bad_values():
    df = pd.DataFrame({"a": ["1", "x", None]})
    assert numeric_column(df, "a", -1.0).tolist() == [1.0, -1.0, -1.0]


def test_feature_builders_tolerate_missing_columns():
    df = pd.DataFrame({"Order_Region": ["A", "B"]}, index=[5, 7])
    score = add_demand_score(df)
    assert list(score.index) == [5, 7]
