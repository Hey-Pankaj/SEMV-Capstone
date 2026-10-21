"""
Data cleaning and quality assurance module for वज्रSense (VajraSense).
Applies physical plausibility bounds, enforces regular hourly frequency,
handles missing observations, and produces audit metrics.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

import numpy as np
import pandas as pd

from vajrasense.config import (
    PHYSICAL_BOUNDS,
    DATA_PROCESSED_DIR,
    CLEAN_DATA_FILENAME,
    DATA_RAW_DIR,
    RAW_DATA_FILENAME,
)

logger = logging.getLogger("vajrasense.preprocessing")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [VajraSense:Cleaner] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class DataCleaner:
    """
    Cleans raw meteorological observations, validates physical bounds,
    and prepares a regular continuous time series.
    """

    def __init__(self, physical_bounds: Optional[Dict[str, Tuple[float, float]]] = None):
        self.physical_bounds = physical_bounds or PHYSICAL_BOUNDS
        self.audit_report: Dict[str, Any] = {}

    def clean_weather_data(
        self,
        df_raw: Optional[pd.DataFrame] = None,
        input_csv_path: Optional[Path] = None,
        output_csv_path: Optional[Path] = None,
    ) -> pd.DataFrame:
        """
        Executes the complete data cleaning and audit pipeline.
        """
        if df_raw is None:
            if input_csv_path is None:
                input_csv_path = DATA_RAW_DIR / RAW_DATA_FILENAME
            logger.info(f"Loading raw data from: {input_csv_path}")
            if not Path(input_csv_path).exists():
                raise FileNotFoundError(
                    f"Raw data file not found at {input_csv_path}. Please run ingestion first."
                )
            df = pd.read_csv(input_csv_path)
        else:
            df = df_raw.copy()

        initial_rows = len(df)
        logger.info(f"Starting data cleaning on {initial_rows:,} raw records.")

        # 1. Parse and Standardize Timestamps
        if "time" not in df.columns:
            raise KeyError("Dataset missing mandatory 'time' column.")

        df["time"] = pd.to_datetime(df["time"])
        df = df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
        dedup_rows = len(df)
        logger.info(f"Deduplication complete: {initial_rows - dedup_rows} duplicate rows removed.")

        # 2. Enforce Continuous Hourly Grid
        df = df.set_index("time")
        full_time_index = pd.date_range(
            start=df.index.min(), end=df.index.max(), freq="1h", name="time"
        )
        missing_hours = len(full_time_index) - len(df)
        if missing_hours > 0:
            logger.warning(
                f"Detected {missing_hours} missing hourly timestamps in sequence. Reindexing to continuous 1h grid..."
            )
            df = df.reindex(full_time_index)

        # 3. Audit Initial Missing Values
        missing_before = df.isna().sum().to_dict()

        # 4. Physical Plausibility Auditing and Outlier Clamping
        anomalies_detected: Dict[str, int] = {}
        for col, (min_val, max_val) in self.physical_bounds.items():
            if col in df.columns:
                out_of_bounds = (df[col] < min_val) | (df[col] > max_val)
                count_anomalies = int(out_of_bounds.sum())
                if count_anomalies > 0:
                    logger.warning(
                        f"Variable '{col}': {count_anomalies} records outside plausible range [{min_val}, {max_val}]. Clamping values."
                    )
                    df[col] = df[col].clip(lower=min_val, upper=max_val)
                anomalies_detected[col] = count_anomalies

        # 5. Missing Value Imputation Strategy
        # Surface variables: short gaps (<= 3h) filled via forward-fill (persistence)
        # Followed by linear time interpolation
        numeric_cols = df.select_dtypes(include=[np.number]).columns

        for col in numeric_cols:
            if df[col].isna().any():
                # Short gap persistence
                df[col] = df[col].ffill(limit=3).bfill(limit=3)
                # Linear interpolation for remaining gaps
                df[col] = df[col].interpolate(method="time")
                # Fallback to column median if any NaNs remain (e.g. edge boundaries)
                if df[col].isna().any():
                    median_val = df[col].median()
                    df[col] = df[col].fillna(median_val)

        # Discrete WMO weather_code: forward fill or fill with 0 (clear sky default)
        if "weather_code" in df.columns:
            df["weather_code"] = df["weather_code"].ffill().fillna(0).astype(int)

        missing_after = df.isna().sum().to_dict()

        # 6. Reset index back to column
        df = df.reset_index()

        # 7. Compile Audit Report
        self.audit_report = {
            "initial_record_count": initial_rows,
            "cleaned_record_count": len(df),
            "date_start": str(df["time"].min()),
            "date_end": str(df["time"].max()),
            "missing_hours_reindexed": missing_hours,
            "anomalies_clamped": anomalies_detected,
            "missing_values_before": missing_before,
            "missing_values_after": missing_after,
        }

        # 8. Save Cleaned Data to CSV
        if output_csv_path is None:
            output_csv_path = DATA_PROCESSED_DIR / CLEAN_DATA_FILENAME

        output_csv_path = Path(output_csv_path)
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv_path, index=False)
        logger.info(f"Cleaned dataset successfully saved to: {output_csv_path.resolve()}")

        return df

    def get_audit_summary(self) -> Dict[str, Any]:
        """Returns the dictionary audit report from the latest cleaning run."""
        return self.audit_report
