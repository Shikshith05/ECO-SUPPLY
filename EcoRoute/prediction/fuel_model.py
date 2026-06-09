"""
Machine Learning model for fuel consumption prediction.
Optional ML-based approach for more accurate fuel estimation.

Supports:
- Random Forest
- Gradient Boosting
- Training & evaluation
- Prediction (single & batch)
- Model save/load
"""

import os
import joblib
import random
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score
)

from .fuel_rules import FuelRulesEstimator


class FuelMLModel:
    """
    ML model for fuel consumption prediction.
    """

    def __init__(self, model_type: str = "random_forest"):
        """
        Initialize the fuel ML model.

        model_type:
            - "random_forest"
            - "gradient_boosting"
        """

        self.model_type = model_type
        self.model = None
        self.encoder = OneHotEncoder(sparse=False, handle_unknown="ignore")
        self.scaler = StandardScaler()
        self.trained = False
        self.metrics_ = {}

        if model_type == "random_forest":
            self.model = RandomForestRegressor(
                n_estimators=150,
                max_depth=12,
                min_samples_split=8,
                random_state=42,
                n_jobs=-1
            )
        elif model_type == "gradient_boosting":
            self.model = GradientBoostingRegressor(
                n_estimators=200,
                learning_rate=0.05,
                max_depth=4,
                random_state=42
            )
        else:
            raise ValueError(
                "model_type must be 'random_forest' or 'gradient_boosting'"
            )

    # --------------------------------------------------
    # FEATURE ENGINEERING
    # --------------------------------------------------

    def _prepare_features(self, df: pd.DataFrame, fit: bool = False):
        """
        Convert raw fuel data into ML-ready features.
        """

        categorical = df[["vehicle_type", "area_type"]]
        numeric = df[["distance_km", "load_kg"]]

        if fit:
            cat_encoded = self.encoder.fit_transform(categorical)
            num_scaled = self.scaler.fit_transform(numeric)
        else:
            cat_encoded = self.encoder.transform(categorical)
            num_scaled = self.scaler.transform(numeric)

        X = np.hstack([cat_encoded, num_scaled])
        return X

    # --------------------------------------------------
    # TRAINING
    # --------------------------------------------------

    def train(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42,
        use_cross_validation: bool = True
    ):
        """
        Train the fuel prediction model.
        """

        print(f"\nTraining Fuel Model ({self.model_type})")

        y = df["fuel_liters"].values
        X = self._prepare_features(df, fit=True)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        self.model.fit(X_train, y_train)
        self.trained = True

        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)

        self.metrics_ = {
            "train_mae": mean_absolute_error(y_train, y_train_pred),
            "test_mae": mean_absolute_error(y_test, y_test_pred),
            "train_rmse": np.sqrt(mean_squared_error(y_train, y_train_pred)),
            "test_rmse": np.sqrt(mean_squared_error(y_test, y_test_pred)),
            "train_r2": r2_score(y_train, y_train_pred),
            "test_r2": r2_score(y_test, y_test_pred),
            "test_mape": np.mean(
                np.abs((y_test - y_test_pred) / y_test)
            ) * 100
        }

        if use_cross_validation:
            cv_scores = cross_val_score(
                self.model,
                X_train,
                y_train,
                cv=5,
                scoring="neg_mean_absolute_error"
            )
            self.metrics_["cv_mae"] = -cv_scores.mean()

        self._print_metrics()
        return self.metrics_

    # --------------------------------------------------
    # PREDICTION
    # --------------------------------------------------

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        if not self.trained:
            raise RuntimeError("Model must be trained before prediction.")

        X = self._prepare_features(df, fit=False)
        return self.model.predict(X)

    def predict_single(
        self,
        distance_km: float,
        vehicle_type: str,
        load_kg: float = 0.0,
        area_type: str = "urban"
    ) -> float:
        """
        Predict fuel consumption for a single route segment.
        """

        df = pd.DataFrame([{
            "distance_km": distance_km,
            "vehicle_type": vehicle_type,
            "load_kg": load_kg,
            "area_type": area_type
        }])

        return float(self.predict(df)[0])

    # --------------------------------------------------
    # SAVE / LOAD
    # --------------------------------------------------

    def save(self, directory: str, model_name: str = "fuel_model"):
        if not self.trained:
            raise RuntimeError("Train the model before saving.")

        os.makedirs(directory, exist_ok=True)

        joblib.dump(self.model, os.path.join(directory, f"{model_name}.pkl"))
        joblib.dump(self.encoder, os.path.join(directory, f"{model_name}_encoder.pkl"))
        joblib.dump(self.scaler, os.path.join(directory, f"{model_name}_scaler.pkl"))

        print(f"Model saved to {directory}/")

    def load(self, directory: str, model_name: str = "fuel_model"):
        self.model = joblib.load(os.path.join(directory, f"{model_name}.pkl"))
        self.encoder = joblib.load(os.path.join(directory, f"{model_name}_encoder.pkl"))
        self.scaler = joblib.load(os.path.join(directory, f"{model_name}_scaler.pkl"))
        self.trained = True

        print(f"Model loaded from {directory}/")

    # --------------------------------------------------
    # METRICS PRINTING
    # --------------------------------------------------

    def _print_metrics(self):
        print("\nFuel Model Performance")
        print("=" * 50)
        print(f"Train MAE : {self.metrics_['train_mae']:.4f}")
        print(f"Test  MAE : {self.metrics_['test_mae']:.4f}")
        print(f"Train RMSE: {self.metrics_['train_rmse']:.4f}")
        print(f"Test  RMSE: {self.metrics_['test_rmse']:.4f}")
        print(f"Train R²  : {self.metrics_['train_r2']:.4f}")
        print(f"Test  R²  : {self.metrics_['test_r2']:.4f}")
        print(f"Test MAPE : {self.metrics_['test_mape']:.2f}%")
        if "cv_mae" in self.metrics_:
            print(f"CV MAE    : {self.metrics_['cv_mae']:.4f}")
        print("=" * 50)


# --------------------------------------------------
# STANDALONE TRAINING (Synthetic Data)
# --------------------------------------------------
if __name__ == "__main__":

    OUTPUT_DIR = os.path.join("data", "models")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print("Generating synthetic fuel data...")

    rules = FuelRulesEstimator()
    samples = []

    vehicle_types = ["bike", "car", "van"]
    area_types = ["urban", "suburban", "highway"]

    for _ in range(5000):
        distance_km = random.uniform(0.5, 15)
        vehicle = random.choice(vehicle_types)
        load = random.uniform(0, 300)
        area = random.choice(area_types)

        fuel = rules.estimate_fuel(
            distance_km=distance_km,
            vehicle_type=vehicle,
            load_kg=load,
            area_type=area
        )

        samples.append({
            "distance_km": distance_km,
            "vehicle_type": vehicle,
            "load_kg": load,
            "area_type": area,
            "fuel_liters": fuel
        })

    df = pd.DataFrame(samples)
    print(f"Dataset size: {len(df)}")

    for model_type in ["random_forest", "gradient_boosting"]:
        print(f"\nTraining {model_type.upper()} model")
        model = FuelMLModel(model_type=model_type)
        model.train(df)
        model.save(OUTPUT_DIR, f"fuel_{model_type}")

        pred = model.predict_single(
            distance_km=5,
            vehicle_type="van",
            load_kg=120,
            area_type="urban"
        )
        print(f"Test prediction (5 km, van, urban): {pred:.3f} liters")

    print("\nFuel ML models trained and saved successfully!")
