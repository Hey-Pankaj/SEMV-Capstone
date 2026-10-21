"""
Unit and integration tests for the वज्रSense pipeline.
Validates configurations, cleaning logic, meteorological calculations,
and CPU-based model training.
"""

import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from vajrasense.config import (
    MUMBAI_LATITUDE,
    MUMBAI_LONGITUDE,
    PHYSICAL_BOUNDS,
    CONVECTIVE_THRESHOLDS,
)
from vajrasense.preprocessing import DataCleaner
from vajrasense.feature_engineering import AtmosphericFeatureEngineer
from vajrasense.pipeline import NowcastingPipeline


class TestVajraSensePipeline(unittest.TestCase):
    """Test cases for वज्रSense modules."""

    def setUp(self):
        # Create a synthetic 48-hour meteorological sample
        timestamps = pd.date_range("2024-06-01 00:00", periods=48, freq="1h")
        np.random.seed(42)

        self.sample_df = pd.DataFrame({
            "time": timestamps,
            "temperature_2m": np.random.uniform(26.0, 36.0, size=48),
            "relative_humidity_2m": np.random.uniform(50.0, 95.0, size=48),
            "dew_point_2m": np.random.uniform(22.0, 28.0, size=48),
            "apparent_temperature": np.random.uniform(28.0, 42.0, size=48),
            "surface_pressure": np.random.uniform(1000.0, 1012.0, size=48),
            "precipitation": np.random.choice([0.0, 0.5, 3.0, 12.0], size=48, p=[0.7, 0.15, 0.1, 0.05]),
            "rain": np.random.choice([0.0, 0.5, 3.0, 12.0], size=48, p=[0.7, 0.15, 0.1, 0.05]),
            "weather_code": np.random.choice([0, 1, 51, 80, 95], size=48, p=[0.5, 0.2, 0.15, 0.1, 0.05]),
            "cloud_cover": np.random.uniform(10.0, 100.0, size=48),
            "cloud_cover_low": np.random.uniform(0.0, 80.0, size=48),
            "cloud_cover_mid": np.random.uniform(0.0, 60.0, size=48),
            "cloud_cover_high": np.random.uniform(0.0, 70.0, size=48),
            "wind_speed_10m": np.random.uniform(5.0, 30.0, size=48),
            "wind_speed_100m": np.random.uniform(10.0, 45.0, size=48),
            "wind_direction_10m": np.random.uniform(0.0, 360.0, size=48),
            "wind_gusts_10m": np.random.uniform(10.0, 50.0, size=48),
            "cape": np.random.uniform(100.0, 2500.0, size=48),
            "lifted_index": np.random.uniform(-6.0, 4.0, size=48),
            "convective_inhibition": np.random.uniform(-150.0, 0.0, size=48),
        })

    def test_geographic_configuration(self):
        """Verifies Mumbai spatial parameters are correctly located."""
        self.assertAlmostEqual(MUMBAI_LATITUDE, 19.0760, places=2)
        self.assertAlmostEqual(MUMBAI_LONGITUDE, 72.8777, places=2)
        self.assertIn("temperature_2m", PHYSICAL_BOUNDS)
        self.assertIn("cape_moderate", CONVECTIVE_THRESHOLDS)

    def test_cleaner_physical_bounds_and_duplicates(self):
        """Tests that out-of-bound values are clamped and duplicate rows are removed."""
        df_dirty = self.sample_df.copy()

        # Inject anomalies: negative humidity, extreme temp, duplicate row
        df_dirty.loc[0, "relative_humidity_2m"] = -25.0
        df_dirty.loc[1, "temperature_2m"] = 85.0
        duplicate_row = df_dirty.iloc[[2]]
        df_dirty = pd.concat([df_dirty, duplicate_row], ignore_index=True)

        cleaner = DataCleaner()
        df_clean = cleaner.clean_weather_data(df_raw=df_dirty)

        # Check deduplication
        self.assertEqual(len(df_clean), 48)

        # Check bounding
        self.assertGreaterEqual(df_clean["relative_humidity_2m"].min(), 5.0)
        self.assertLessEqual(df_clean["temperature_2m"].max(), 48.0)

    def test_feature_engineering_physics(self):
        """Validates meteorological derived variables and temporal encodings."""
        engineer = AtmosphericFeatureEngineer()
        df_feats = engineer.transform(df_clean=self.sample_df)

        # 1. Dew point depression = T - Td >= 0 (or close, within numerical rounding)
        dep = df_feats["dew_point_depression"]
        self.assertTrue((dep >= -0.5).all())

        # 2. Wind shear = V100m - V10m >= 0
        shear = df_feats["vertical_wind_shear"]
        self.assertTrue((shear >= 0.0).all())

        # 3. Cyclical hour encoding: sin^2 + cos^2 == 1
        hour_circle = (df_feats["hour_sin"] ** 2) + (df_feats["hour_cos"] ** 2)
        np.testing.assert_allclose(hour_circle, 1.0, atol=1e-5)

        # 4. Nowcasting targets exist
        self.assertIn("target_nowcast_1h", df_feats.columns)
        self.assertIn("target_nowcast_2h", df_feats.columns)
        self.assertIn("target_nowcast_3h", df_feats.columns)

    def test_cpu_nowcasting_pipeline_train_eval(self):
        """Tests end-to-end CPU pipeline training and evaluation on sample data."""
        engineer = AtmosphericFeatureEngineer()
        df_feats = engineer.transform(df_clean=self.sample_df)

        pipeline = NowcastingPipeline(target_column="target_nowcast_1h", model_type="hist_gb")
        X_train, X_test, y_train, y_test = pipeline.prepare_data(df=df_feats, train_ratio=0.75)

        self.assertEqual(len(X_train) + len(X_test), 48)
        self.assertGreater(len(pipeline.feature_names), 15)

        results = pipeline.train_and_evaluate(X_train, X_test, y_train, y_test)
        self.assertIn("roc_auc", results)
        self.assertIn("brier_score", results)
        self.assertIn("precision", results)
        self.assertIn("recall_pod", results)

        # Verify Brier score is in [0, 1]
        self.assertGreaterEqual(results["brier_score"], 0.0)
        self.assertLessEqual(results["brier_score"], 1.0)


if __name__ == "__main__":
    unittest.main()
