"""
Atmospheric feature engineering module for वज्रSense (VajraSense).
Computes thermodynamically derived indices, kinematic shear proxies,
barometric tendencies, and temporal encodings for Mumbai convective nowcasting.

SCIENTIFIC INTEGRITY NOTE:
In adherence to research rigor, this module does NOT generate synthetic
or fake lightning labels. Severe convective risk targets are derived strictly
from validated physical atmospheric instability criteria (CAPE, Lifted Index,
WMO weather codes, and precipitation-gust dynamics) or external ground-truth
lightning detection logs.
"""

import logging
from pathlib import Path
from typing import Optional, List

import numpy as np
import pandas as pd

from vajrasense.config import (
    DATA_PROCESSED_DIR,
    CLEAN_DATA_FILENAME,
    ENGINEERED_DATA_FILENAME,
    CONVECTIVE_THRESHOLDS,
)

logger = logging.getLogger("vajrasense.features")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [VajraSense:Features] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class AtmosphericFeatureEngineer:
    """
    Computes domain-specific meteorological features and rolling nowcasting targets
    for the Mumbai tropical coastal convective regime.
    """

    def __init__(self, thresholds: Optional[dict] = None):
        self.thresholds = thresholds or CONVECTIVE_THRESHOLDS

    def compute_thermodynamic_proxies(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes moisture saturation deficit, approximate equivalent potential
        temperature (theta-e proxy), and kinematic shear.
        """
        # 1. Dew Point Depression (T - Td) in °C
        # Low depression indicates saturation near surface; when combined with high heat,
        # it fuels intense moisture convergence into convective updrafts.
        df["dew_point_depression"] = df["temperature_2m"] - df["dew_point_2m"]

        # 2. Approximate Potential Temperature (Theta) in Kelvin
        # theta = T_K * (1000 / P)**(R/Cp) where R/Cp ~ 0.286
        temp_k = df["temperature_2m"] + 273.15
        p_ratio = (1000.0 / df["surface_pressure"]).clip(lower=0.5, upper=1.5)
        df["potential_temperature"] = temp_k * (p_ratio ** 0.286)

        # 3. Moisture Mixing Ratio proxy (w in g/kg) via Magnus-Tetens approximation
        # e_s = 6.112 * exp((17.67 * Td) / (Td + 243.5))
        vapor_pressure = 6.112 * np.exp(
            (17.67 * df["dew_point_2m"]) / (df["dew_point_2m"] + 243.5)
        )
        mixing_ratio = 622.0 * (vapor_pressure / (df["surface_pressure"] - vapor_pressure))
        df["mixing_ratio_g_kg"] = mixing_ratio.clip(lower=0.0, upper=40.0)

        # 4. Equivalent Potential Temperature (Theta-e proxy) in Kelvin
        # High theta-e indicates a rich reservoir of latent and sensible heat
        # Lv ~ 2.5e6 J/kg, Cp ~ 1004 J/(kg K) -> Lv/Cp ~ 2500 K
        df["theta_e_proxy"] = df["potential_temperature"] * np.exp(
            (2500.0 * (df["mixing_ratio_g_kg"] / 1000.0)) / temp_k
        )

        # 5. Low-level Vertical Wind Shear Proxy (100m vs 10m) in km/h
        # Shear tilts updrafts, allowing storms to sustain longer without self-choking
        df["vertical_wind_shear"] = (
            df["wind_speed_100m"] - df["wind_speed_10m"]
        ).clip(lower=0.0)

        return df

    def compute_tendencies_and_rolling(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Computes rate-of-change (tendency) and rolling memory features
        over 1-hour and 3-hour windows.
        """
        # Ensure chronological order
        df = df.sort_values("time").copy()

        # 1. Barometric Pressure Tendency (Delta P) in hPa
        # Rapid pressure drop often precedes severe squalls, followed by gust surge
        df["pressure_tendency_1h"] = df["surface_pressure"].diff(1)
        df["pressure_tendency_3h"] = df["surface_pressure"].diff(3)

        # 2. Temperature Drop (Delta T) in °C
        # Cold pool / outflow boundary detection from active downdrafts
        df["temp_drop_1h"] = df["temperature_2m"].diff(1)

        # 3. Moisture Tendency (Delta Dew Point)
        df["dew_point_tendency_1h"] = df["dew_point_2m"].diff(1)

        # 4. Rolling Antecedent Max Gusts and Rainfall Accumulation
        df["rolling_max_gust_3h"] = df["wind_gusts_10m"].rolling(3, min_periods=1).max()
        df["rolling_rain_accum_3h"] = df["precipitation"].rolling(3, min_periods=1).sum()

        # 5. Rolling Mean CAPE (Atmospheric energy persistence)
        if "cape" in df.columns:
            df["rolling_cape_mean_3h"] = df["cape"].rolling(3, min_periods=1).mean()

        return df

    def compute_temporal_encodings(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Encodes cyclical diurnal and seasonal patterns using sine and cosine transforms.
        """
        hour = df["time"].dt.hour
        day_of_year = df["time"].dt.dayofyear

        # Diurnal Cycle (24h period)
        # Captures Mumbai afternoon heating (14:00-18:00 IST) vs morning stability
        df["hour_sin"] = np.sin(2 * np.pi * hour / 24.0)
        df["hour_cos"] = np.cos(2 * np.pi * hour / 24.0)

        # Seasonal Cycle (365.25 days period)
        # Captures pre-monsoon (May), monsoon peak (July-Aug), and post-monsoon (Oct)
        df["doy_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
        df["doy_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)

        return df

    def label_convective_targets(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Establishes scientifically grounded convective risk flags and nowcasting targets.

        Definition:
        A 'severe_convective_event' is flagged when the local atmosphere satisfies
        validated meteorological instability and squall/shower thresholds:
        - High CAPE (>= cape_moderate threshold) AND
        - Strongly negative Lifted Index (<= lifted_index_unstable) OR
        - WMO weather code indicating convective showers (80, 81, 82) or thunderstorms (95, 96, 99) OR
        - Heavy precipitation (>= 5 mm/h) coinciding with strong wind gusts (>= 35 km/h).

        Nowcasting Targets:
        - target_nowcast_1h: Event occurs in t+1
        - target_nowcast_2h: Event occurs within [t+1, t+2]
        - target_nowcast_3h: Event occurs within [t+1, t+3]
        """
        cape_thresh = self.thresholds.get("cape_moderate", 1000.0)
        li_thresh = self.thresholds.get("lifted_index_unstable", -2.0)
        rain_thresh = self.thresholds.get("heavy_rain_rate", 5.0)
        gust_thresh = self.thresholds.get("gust_threshold", 35.0)

        # Meteorological instability criteria
        instability_flag = (df["cape"] >= cape_thresh) & (df["lifted_index"] <= li_thresh)

        # WMO convective weather code criteria (80-82: Showers, 95-99: Thunderstorms)
        wmo_convective_flag = df["weather_code"].isin([80, 81, 82, 95, 96, 99])

        # Dynamic squall / heavy shower criteria
        squall_rain_flag = (df["precipitation"] >= rain_thresh) & (df["wind_gusts_10m"] >= gust_thresh)

        # Combined ground truth proxy
        df["convective_event_now"] = (
            instability_flag | wmo_convective_flag | squall_rain_flag
        ).astype(int)

        # Future Nowcasting Targets (Shift backward in time to predict future event from current state)
        df["target_nowcast_1h"] = df["convective_event_now"].shift(-1).fillna(0).astype(int)
        df["target_nowcast_2h"] = (
            df["convective_event_now"].rolling(2, min_periods=1).max().shift(-2).fillna(0).astype(int)
        )
        df["target_nowcast_3h"] = (
            df["convective_event_now"].rolling(3, min_periods=1).max().shift(-3).fillna(0).astype(int)
        )

        return df

    def transform(
        self,
        df_clean: Optional[pd.DataFrame] = None,
        input_csv_path: Optional[Path] = None,
        output_csv_path: Optional[Path] = None,
    ) -> pd.DataFrame:
        """
        Executes full feature engineering pipeline and writes results to CSV.
        """
        if df_clean is None:
            if input_csv_path is None:
                input_csv_path = DATA_PROCESSED_DIR / CLEAN_DATA_FILENAME
            logger.info(f"Loading cleaned data from: {input_csv_path}")
            df = pd.read_csv(input_csv_path)
            df["time"] = pd.to_datetime(df["time"])
        else:
            df = df_clean.copy()
            if not np.issubdtype(df["time"].dtype, np.datetime64):
                df["time"] = pd.to_datetime(df["time"])

        logger.info(f"Generating atmospheric features for {len(df):,} observations...")

        df = self.compute_thermodynamic_proxies(df)
        df = self.compute_tendencies_and_rolling(df)
        df = self.compute_temporal_encodings(df)
        df = self.label_convective_targets(df)

        # Drop initial boundary rows containing NaN from diff(3)
        df = df.bfill().ffill()

        if output_csv_path is None:
            output_csv_path = DATA_PROCESSED_DIR / ENGINEERED_DATA_FILENAME

        output_csv_path = Path(output_csv_path)
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_csv_path, index=False)
        logger.info(f"Feature engineering complete. Saved to: {output_csv_path.resolve()}")

        return df

    @staticmethod
    def get_feature_column_names() -> List[str]:
        """
        Returns list of predictive features available at nowcast time t (no lookahead).
        """
        return [
            "temperature_2m",
            "relative_humidity_2m",
            "dew_point_2m",
            "surface_pressure",
            "precipitation",
            "cloud_cover",
            "cloud_cover_low",
            "cloud_cover_mid",
            "cloud_cover_high",
            "wind_speed_10m",
            "wind_speed_100m",
            "wind_gusts_10m",
            "cape",
            "lifted_index",
            "convective_inhibition",
            "dew_point_depression",
            "potential_temperature",
            "mixing_ratio_g_kg",
            "theta_e_proxy",
            "vertical_wind_shear",
            "pressure_tendency_1h",
            "pressure_tendency_3h",
            "temp_drop_1h",
            "dew_point_tendency_1h",
            "rolling_max_gust_3h",
            "rolling_rain_accum_3h",
            "rolling_cape_mean_3h",
            "hour_sin",
            "hour_cos",
            "doy_sin",
            "doy_cos",
        ]
