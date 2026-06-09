"""
Feature engineering for delay prediction models.

Transforms raw traffic data into ML-ready features.
"""

import pandas as pd
import numpy as np
from sklearn.preprocessing import OneHotEncoder, StandardScaler


class DelayFeatureEngineer:
    """
    Feature engineering pipeline for delay prediction.
    """

    def __init__(self):
        self.encoder = OneHotEncoder(sparse_output=False, handle_unknown="ignore")
        self.scaler = StandardScaler()
        self.fitted = False

    def _encode_time(self, hour_series):
        """
        Encode hour of day as cyclic features.
        """
        hour_rad = 2 * np.pi * hour_series / 24
        return np.sin(hour_rad), np.cos(hour_rad)

    def fit_transform(self, df: pd.DataFrame):
        """
        Fit encoders and transform training data.
        """

        # Target
        y = df["delay_sec"].values

        # Categorical: road type
        road_type_encoded = self.encoder.fit_transform(df[["road_type"]])

        # Numeric features
        length = df[["length_m"]].values
        base_time = df[["base_time_sec"]].values

        # Time features
        sin_hour, cos_hour = self._encode_time(df["hour_of_day"])

        X_numeric = np.hstack([
            length,
            base_time,
            np.array(sin_hour).reshape(-1, 1),
            np.array(cos_hour).reshape(-1, 1)
        ])

        X_numeric_scaled = self.scaler.fit_transform(X_numeric)

        X = np.hstack([road_type_encoded, X_numeric_scaled])

        self.fitted = True
        return X, y

    def transform(self, df: pd.DataFrame):
        """
        Transform new/unseen data using fitted encoders.
        """

        if not self.fitted:
            raise RuntimeError("FeatureEngineer must be fitted before calling transform.")

        road_type_encoded = self.encoder.transform(df[["road_type"]])

        length = df[["length_m"]].values
        base_time = df[["base_time_sec"]].values

        sin_hour, cos_hour = self._encode_time(df["hour_of_day"])

        X_numeric = np.hstack([
            length,
            base_time,
            np.array(sin_hour).reshape(-1, 1),
            np.array(cos_hour).reshape(-1, 1)
        ])

        X_numeric_scaled = self.scaler.transform(X_numeric)

        X = np.hstack([road_type_encoded, X_numeric_scaled])

        return X
