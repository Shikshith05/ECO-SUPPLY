"""
Train and evaluate the leakage-free late-delivery model.

    .venv\\Scripts\\python scripts/train_delay_model.py [--csv data/raw/DataCoSupplyChainDataset.csv]

Protocol
  * Population: orders that actually shipped. Canceled orders have no
    meaningful late/on-time outcome (they are labelled 0) and are excluded.
  * Time-based split on Order_Date: oldest 70 % train, next 10 % validation,
    newest 20 % test. Rows with the same timestamp stay on the same side, so
    items of one order never straddle a boundary.
  * Models: majority class, shipping-mode lookup (training late rate per
    mode), logistic regression (one-hot + scaling), XGBoost (ordinal
    encoding, early stopping on validation).
  * The decision threshold that maximises F1 is chosen on VALIDATION and then
    applied unchanged to TEST. F1 at 0.5 is reported too.
  * The test set is scored once per model, after all choices are made.

Outputs
  saved_models/delay_model.joblib        (gitignored) XGBoost pipeline + lookups + metadata
  results/delay_model_metrics.json       all metrics, split dates, feature list
  results/delay_model_calibration.png    reliability diagram on the test set
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.utils.preprocessing import load_and_clean_csv  # noqa: E402
from models.consumer_models.delay_model import (  # noqa: E402
    BANNED_COLUMNS, CATEGORICAL_FEATURES, FEATURES, MODEL_PATH, NUMERIC_FEATURES, TARGET,
    assert_no_leakage, build_feature_frame, build_lookups, encoded_feature_order, make_xgb_pipeline,
    shap_contributions,
)

SEED = 42


def time_split(df: pd.DataFrame, train_frac=0.7, val_frac=0.1):
    df = df.sort_values("Order_Date", kind="mergesort").reset_index(drop=True)
    dates = df["Order_Date"]
    t1 = dates.iloc[int(len(df) * train_frac)]
    t2 = dates.iloc[int(len(df) * (train_frac + val_frac))]
    train = df[dates < t1]
    val = df[(dates >= t1) & (dates < t2)]
    test = df[dates >= t2]
    return train, val, test


def metrics(y, proba, threshold):
    from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss, f1_score,
                                 log_loss, precision_score, recall_score, roc_auc_score)

    pred = (proba >= threshold).astype(int)
    out = {
        "roc_auc": float(roc_auc_score(y, proba)) if len(np.unique(proba)) > 1 else 0.5,
        "pr_auc": float(average_precision_score(y, proba)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "accuracy": float(accuracy_score(y, pred)),
        "brier": float(brier_score_loss(y, proba)),
        "log_loss": float(log_loss(y, np.clip(proba, 1e-6, 1 - 1e-6))),
        "threshold": float(threshold),
        "f1_at_0.5": float(f1_score(y, (proba >= 0.5).astype(int), zero_division=0)),
    }
    return {k: round(v, 4) for k, v in out.items()}


def best_f1_threshold(y, proba):
    from sklearn.metrics import f1_score

    grid = np.unique(np.round(proba, 3))
    if len(grid) > 400:
        grid = np.quantile(proba, np.linspace(0.01, 0.99, 197))
    scores = [(f1_score(y, (proba >= t).astype(int), zero_division=0), t) for t in grid]
    return float(max(scores)[1])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(ROOT, "data", "raw", "DataCoSupplyChainDataset.csv"))
    args = ap.parse_args()

    from sklearn.compose import ColumnTransformer
    from sklearn.dummy import DummyClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler
    import joblib

    t0 = time.time()
    assert_no_leakage(FEATURES)
    df = load_and_clean_csv(args.csv)
    df = df.dropna(subset=["Order_Date", TARGET])
    # Label definition: "if this order ships, will it ship late?". Canceled orders
    # (Delivery_Status == "Shipping canceled", i.e. Order_Status CANCELED or
    # SUSPECTED_FRAUD) never shipped, yet carry Late_delivery_risk = 0, which would
    # teach the model to predict cancellations as "on time". They are removed from
    # train AND test. Delivery_Status is used only to define the population, never
    # as a feature.
    n_before = len(df)
    df = df[df["Delivery_Status"].astype(str).str.strip() != "Shipping canceled"]
    excluded_canceled = n_before - len(df)
    train, val, test = time_split(df)
    X_tr, X_va, X_te = (build_feature_frame(d) for d in (train, val, test))
    y_tr, y_va, y_te = (d[TARGET].astype(int).to_numpy() for d in (train, val, test))
    assert not (set(X_tr.columns) & BANNED_COLUMNS)
    print(f"excluded {excluded_canceled} canceled rows; rows train/val/test: {len(X_tr)}/{len(X_va)}/{len(X_te)}")

    results = {}
    val_proba, test_proba = {}, {}

    # 1) Majority class.
    dummy = DummyClassifier(strategy="most_frequent").fit(X_tr, y_tr)
    val_proba["majority_class"] = dummy.predict_proba(X_va)[:, 1]
    test_proba["majority_class"] = dummy.predict_proba(X_te)[:, 1]

    # 2) Shipping-mode lookup: training late rate per mode.
    rate = pd.Series(y_tr).groupby(X_tr["Shipping_Mode"].to_numpy()).mean()
    prior = float(y_tr.mean())
    val_proba["shipping_mode_lookup"] = X_va["Shipping_Mode"].map(rate).fillna(prior).to_numpy()
    test_proba["shipping_mode_lookup"] = X_te["Shipping_Mode"].map(rate).fillna(prior).to_numpy()

    # 3) Logistic regression.
    logreg = Pipeline([
        ("pre", ColumnTransformer([
            ("cat", OneHotEncoder(handle_unknown="ignore", min_frequency=20), CATEGORICAL_FEATURES),
            ("num", Pipeline([("scale", StandardScaler())]), NUMERIC_FEATURES),
        ])),
        ("model", LogisticRegression(max_iter=2000, C=1.0)),
    ]).fit(X_tr.fillna(0), y_tr)
    val_proba["logistic_regression"] = logreg.predict_proba(X_va.fillna(0))[:, 1]
    test_proba["logistic_regression"] = logreg.predict_proba(X_te.fillna(0))[:, 1]

    # 4) XGBoost with early stopping on validation.
    xgb_pipe = make_xgb_pipeline(X_tr, y_tr, X_va, y_va, seed=SEED)
    booster = xgb_pipe.named_steps["model"]
    val_proba["xgboost"] = xgb_pipe.predict_proba(X_va)[:, 1]
    test_proba["xgboost"] = xgb_pipe.predict_proba(X_te)[:, 1]

    for name in val_proba:
        thr = best_f1_threshold(y_va, val_proba[name])
        results[name] = {"validation": metrics(y_va, val_proba[name], thr),
                         "test": metrics(y_te, test_proba[name], thr)}
        print(f"{name:22s} test ROC-AUC {results[name]['test']['roc_auc']:.4f}  "
              f"PR-AUC {results[name]['test']['pr_auc']:.4f}  F1 {results[name]['test']['f1']:.4f}")

    # Per shipping mode (test): where does the signal come from? In this dataset
    # some modes are almost deterministic, so the pooled AUC can hide how little
    # the model adds inside a mode.
    from sklearn.metrics import roc_auc_score

    per_mode = {}
    for mode in sorted(X_te["Shipping_Mode"].unique()):
        mask = (X_te["Shipping_Mode"] == mode).to_numpy()
        y_m = y_te[mask]
        entry = {"test_rows": int(mask.sum()), "test_late_rate": round(float(y_m.mean()), 4)}
        for name in ("logistic_regression", "xgboost"):
            p_m = test_proba[name][mask]
            entry[f"{name}_roc_auc"] = (round(float(roc_auc_score(y_m, p_m)), 4)
                                        if len(np.unique(y_m)) > 1 else None)
        per_mode[mode] = entry
    hour = X_te["order_hour"].to_numpy()
    same_day = (X_te["Shipping_Mode"] == "Same Day").to_numpy()
    structure = {
        "same_day_late_rate_order_hour_lt_12": round(float(y_te[same_day & (hour < 12)].mean()), 4),
        "same_day_late_rate_order_hour_ge_12": round(float(y_te[same_day & (hour >= 12)].mean()), 4),
    }
    print("per-mode test AUC:", json.dumps(per_mode))

    # Calibration (test set) for the probabilistic models.
    from sklearn.calibration import calibration_curve

    calib = {}
    for name in ("shipping_mode_lookup", "logistic_regression", "xgboost"):
        frac_pos, mean_pred = calibration_curve(y_te, test_proba[name], n_bins=10, strategy="quantile")
        calib[name] = {"mean_predicted": [round(float(v), 4) for v in mean_pred],
                       "fraction_late": [round(float(v), 4) for v in frac_pos]}
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(5.5, 5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="#888888", label="perfectly calibrated")
    for name, color in (("shipping_mode_lookup", "#E89A3C"), ("logistic_regression", "#4C78A8"), ("xgboost", "#2CA58D")):
        ax.plot(calib[name]["mean_predicted"], calib[name]["fraction_late"], marker="o", color=color, label=name)
    ax.set_xlabel("Mean predicted probability (test, 10 quantile bins)")
    ax.set_ylabel("Observed fraction late")
    ax.set_title("Late-delivery model calibration (time-based test split)")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    fig.savefig(os.path.join(ROOT, "results", "delay_model_calibration.png"), dpi=120)

    # Global importance: mean |SHAP| on a test sample.
    sample = X_te.sample(n=min(5000, len(X_te)), random_state=SEED)
    contrib = shap_contributions(xgb_pipe, sample)[:, :-1]
    names = encoded_feature_order(xgb_pipe)
    importance = sorted(((n, round(float(v), 4)) for n, v in zip(names, np.abs(contrib).mean(axis=0))),
                        key=lambda kv: kv[1], reverse=True)

    # Plain-language quality note shown next to every prediction, built from the numbers above.
    weak = [m for m, e in per_mode.items() if e["xgboost_roc_auc"] is not None and e["xgboost_roc_auc"] < 0.55]
    weak_share = sum(per_mode[m]["test_rows"] for m in weak) / len(X_te)
    quality_note = (
        f"Test ROC-AUC {results['xgboost']['test']['roc_auc']:.3f} vs {results['shipping_mode_lookup']['test']['roc_auc']:.3f} "
        f"for a shipping-mode-only lookup. Within {', '.join(weak) or 'no mode'} "
        f"({weak_share:.0%} of test orders) the model's ROC-AUC is "
        + ", ".join(f"{per_mode[m]['xgboost_roc_auc']:.2f}" for m in weak)
        + " (chance level): most of the signal comes from the shipping mode and the order time of day."
    )

    thr = results["xgboost"]["validation"]["threshold"]
    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    split_info = {
        name: {"rows": int(len(d)), "from": str(d["Order_Date"].min()), "to": str(d["Order_Date"].max()),
               "late_rate": round(float(d[TARGET].mean()), 4)}
        for name, d in (("train", train), ("validation", val), ("test", test))
    }
    metadata = {
        "model_name": "xgboost", "trained_at": trained_at, "threshold": thr,
        "features": FEATURES, "banned_columns": sorted(BANNED_COLUMNS),
        "best_iteration": int(booster.best_iteration), "test_metrics": results["xgboost"]["test"],
        "split": split_info, "quality_note": quality_note,
    }
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump({"pipeline": xgb_pipe, "lookups": build_lookups(df), "metadata": metadata}, MODEL_PATH)

    report = {
        "generated_at": trained_at,
        "dataset": os.path.basename(args.csv),
        "target": TARGET,
        "population": "orders that shipped (Delivery_Status != 'Shipping canceled')",
        "excluded_canceled_rows": int(excluded_canceled),
        "split": split_info,
        "features": {"categorical": CATEGORICAL_FEATURES, "numeric": NUMERIC_FEATURES},
        "banned_columns": sorted(BANNED_COLUMNS),
        "threshold_selection": "threshold maximising F1 on validation, applied unchanged to test",
        "models": results,
        "per_shipping_mode_test": per_mode,
        "quality_note": quality_note,
        "dataset_structure_test": structure,
        "xgboost": {"best_iteration": int(booster.best_iteration),
                    "params": {k: v for k, v in booster.get_params().items()
                               if k in ("learning_rate", "max_depth", "subsample", "colsample_bytree",
                                        "min_child_weight", "reg_lambda", "n_estimators")}},
        "xgboost_mean_abs_shap_test_sample": dict(importance),
        "calibration_test": calib,
        "runtime_s": round(time.time() - t0, 1),
    }
    with open(os.path.join(ROOT, "results", "delay_model_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Saved {MODEL_PATH} and results/delay_model_metrics.json in {report['runtime_s']}s")


if __name__ == "__main__":
    main()
