"""
Machine Learning model for delay prediction.
Uses regression models (Linear Regression, Random Forest) to predict delivery delays.

Integrates:
- delay_rules.py: Rule-based delay estimation (for data generation & fallback)
- feature_engineering.py: Feature transformation pipeline
"""

import os
import joblib
import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from .delay_rules import DelayRulesEstimator
from .feature_engineering import DelayFeatureEngineer


class DelayMLModel:
    """
    Machine Learning model for delay prediction.
    Supports Linear Regression and Random Forest models.
    """

    def __init__(self, model_type: str = "random_forest"):
        """
        Initialize the delay prediction model.

        Args:
            model_type: Either "linear_regression" or "random_forest"
        """
        self.model_type = model_type
        self.feature_engineer = DelayFeatureEngineer()
        self.model = None
        self.trained = False
        self.feature_importance_ = None
        self.metrics_ = {}

        # Initialize the model
        if model_type == "linear_regression":
            self.model = LinearRegression()
        elif model_type == "random_forest":
            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=15,
                min_samples_split=10,
                random_state=42,
                n_jobs=-1
            )
        else:
            raise ValueError(
                f"Unknown model_type: {model_type}. "
                "Use 'linear_regression' or 'random_forest'"
            )

    def train(
        self,
        df: pd.DataFrame,
        test_size: float = 0.2,
        random_state: int = 42,
        use_cross_validation: bool = True
    ):
        """
        Train the delay prediction model.

        Args:
            df: DataFrame with columns: road_type, length_m, hour_of_day, 
                base_time_sec, delay_sec
            test_size: Proportion of data to use for testing
            random_state: Random seed for reproducibility
            use_cross_validation: Whether to perform cross-validation

        Returns:
            Dictionary containing training metrics
        """
        print(f"Training {self.model_type} model...")

        # Feature engineering
        X, y = self.feature_engineer.fit_transform(df)

        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        # Train the model
        self.model.fit(X_train, y_train)
        self.trained = True

        # Predictions
        y_train_pred = self.model.predict(X_train)
        y_test_pred = self.model.predict(X_test)

        # Calculate metrics
        self.metrics_ = {
            "train_mae": mean_absolute_error(y_train, y_train_pred),
            "train_rmse": np.sqrt(mean_squared_error(y_train, y_train_pred)),
            "train_r2": r2_score(y_train, y_train_pred),
            "test_mae": mean_absolute_error(y_test, y_test_pred),
            "test_rmse": np.sqrt(mean_squared_error(y_test, y_test_pred)),
            "test_r2": r2_score(y_test, y_test_pred)
        }

        # Cross-validation
        if use_cross_validation:
            cv_scores = cross_val_score(
                self.model, X_train, y_train, cv=5,
                scoring='neg_mean_absolute_error', n_jobs=-1
            )
            self.metrics_["cv_mae_mean"] = -cv_scores.mean()
            self.metrics_["cv_mae_std"] = cv_scores.std()

        # Feature importance (for tree-based models)
        if hasattr(self.model, "feature_importances_"):
            self.feature_importance_ = self.model.feature_importances_

        print("Training complete!")
        self._print_metrics()

        return self.metrics_

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """
        Predict delays for new data.

        Args:
            df: DataFrame with columns: road_type, length_m, hour_of_day, base_time_sec

        Returns:
            Array of predicted delays in seconds
        """
        if not self.trained:
            raise RuntimeError("Model must be trained before making predictions.")

        X = self.feature_engineer.transform(df)
        predictions = self.model.predict(X)

        return predictions

    def predict_single(
        self,
        road_type: str,
        length_m: float,
        hour_of_day: int,
        base_time_sec: float = None
    ) -> float:
        """
        Predict delay for a single road segment.

        Args:
            road_type: Type of road (e.g., 'motorway', 'residential')
            length_m: Length of segment in meters
            hour_of_day: Hour (0-23)
            base_time_sec: Base travel time (optional, will be estimated if not provided)

        Returns:
            Predicted delay in seconds
        """
        # Estimate base_time if not provided
        if base_time_sec is None:
            estimator = DelayRulesEstimator()
            base_speed = estimator.ROAD_BASE_SPEED.get(road_type, 25)
            base_time_sec = (length_m / 1000) / base_speed * 3600

        df = pd.DataFrame([{
            "road_type": road_type,
            "length_m": length_m,
            "hour_of_day": hour_of_day,
            "base_time_sec": base_time_sec
        }])

        return self.predict(df)[0]

    def get_feature_importance(self) -> dict:
        """
        Get feature importance (for tree-based models).

        Returns:
            Dictionary mapping feature names to importance scores
        """
        if self.feature_importance_ is None:
            return {}

        # Get feature names
        n_road_types = len(self.feature_engineer.encoder.categories_[0])
        feature_names = (
            [f"road_type_{i}" for i in range(n_road_types)] +
            ["length_m", "base_time_sec", "sin_hour", "cos_hour"]
        )

        importance_dict = dict(zip(feature_names, self.feature_importance_))
        # Sort by importance
        return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

    def save(self, directory: str, model_name: str = "delay_model"):
        """
        Save the trained model to disk.

        Args:
            directory: Directory to save the model
            model_name: Base name for the saved files
        """
        if not self.trained:
            raise RuntimeError("Cannot save an untrained model.")

        os.makedirs(directory, exist_ok=True)

        model_path = os.path.join(directory, f"{model_name}.pkl")
        fe_path = os.path.join(directory, f"{model_name}_feature_engineer.pkl")

        joblib.dump(self.model, model_path)
        joblib.dump(self.feature_engineer, fe_path)

        print(f"Model saved to {directory}/")
        print(f"   - {model_name}.pkl")
        print(f"   - {model_name}_feature_engineer.pkl")

    def load(self, directory: str, model_name: str = "delay_model"):
        """
        Load a trained model from disk.

        Args:
            directory: Directory containing the saved model
            model_name: Base name of the saved files
        """
        model_path = os.path.join(directory, f"{model_name}.pkl")
        fe_path = os.path.join(directory, f"{model_name}_feature_engineer.pkl")

        if not os.path.exists(model_path) or not os.path.exists(fe_path):
            raise FileNotFoundError(f"Model files not found in {directory}/")

        self.model = joblib.load(model_path)
        self.feature_engineer = joblib.load(fe_path)
        self.trained = True

        print(f"Model loaded from {directory}/")

    def _print_metrics(self):
        """Print training metrics in a formatted way."""
        print("\nModel Performance Metrics:")
        print("=" * 50)
        print(f"{'Metric':<20} {'Train':<15} {'Test':<15}")
        print("-" * 50)
        print(f"{'MAE (seconds)':<20} {self.metrics_['train_mae']:<15.2f} {self.metrics_['test_mae']:<15.2f}")
        print(f"{'RMSE (seconds)':<20} {self.metrics_['train_rmse']:<15.2f} {self.metrics_['test_rmse']:<15.2f}")
        print(f"{'R² Score':<20} {self.metrics_['train_r2']:<15.3f} {self.metrics_['test_r2']:<15.3f}")

        if "cv_mae_mean" in self.metrics_:
            print("-" * 50)
            print(f"Cross-Validation MAE: {self.metrics_['cv_mae_mean']:.2f} ± {self.metrics_['cv_mae_std']:.2f}")
        print("=" * 50)


# --------------------------------------------------
# Standalone usage: Train model on synthetic data
# --------------------------------------------------
if __name__ == "__main__":
    
    # Path to synthetic data
    DATA_FILE = os.path.join("data", "processed", "synthetic_delay_data.csv")
    MODEL_DIR = os.path.join("data", "models")

    # Check if synthetic data exists
    if not os.path.exists(DATA_FILE):
        print(f"Synthetic data not found at {DATA_FILE}")
        print("Generating synthetic data...")
        
        from .delay_rules import DelayRulesEstimator
        import random
        
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        
        estimator = DelayRulesEstimator(is_weekend=False)
        road_types = list(DelayRulesEstimator.ROAD_BASE_SPEED.keys())
        samples = []
        
        for _ in range(5000):
            samples.append({
                "road_type": random.choice(road_types),
                "length_m": random.uniform(50, 1500),
                "hour_of_day": random.randint(0, 23)
            })
        
        df = estimator.estimate_batch(samples)
        df.to_csv(DATA_FILE, index=False)
        print(f"Generated synthetic data at {DATA_FILE}")
    
    # Load data
    print(f"\nLoading data from {DATA_FILE}")
    df = pd.read_csv(DATA_FILE)
    print(f"   Dataset size: {len(df)} samples")
    
    # Train both model types
    for model_type in ["linear_regression", "random_forest"]:
        print(f"\n{'='*60}")
        print(f"Training {model_type.upper()} model")
        print(f"{'='*60}")
        
        model = DelayMLModel(model_type=model_type)
        model.train(df, test_size=0.2, use_cross_validation=True)
        
        # Show feature importance for RF
        if model_type == "random_forest":
            print("\n Top 5 Feature Importances:")
            importance = model.get_feature_importance()
            for i, (feature, imp) in enumerate(list(importance.items())[:5]):
                print(f"{i+1}. {feature}: {imp:.4f}")
        
        # Save model
        model.save(MODEL_DIR, f"delay_{model_type}")
        
        # Test single prediction
        print("\nTest prediction:")
        delay = model.predict_single(
            road_type="primary",
            length_m=500,
            hour_of_day=9  # Morning peak
        )
        print(f"   Predicted delay for 500m primary road at 9 AM: {delay:.2f} seconds")
    
    print("\nll models trained and saved successfully!")
