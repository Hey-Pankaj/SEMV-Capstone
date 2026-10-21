"""
Data ingestion module for वज्रSense (VajraSense).
Downloads historical and near-real-time atmospheric weather data for Mumbai
from Open-Meteo's API (ERA5 Reanalysis and GFS Seamless models).
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

import pandas as pd
import requests

from vajrasense.config import (
    MUMBAI_LATITUDE,
    MUMBAI_LONGITUDE,
    MUMBAI_ELEVATION,
    TIMEZONE,
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_FORECAST_URL,
    SURFACE_VARIABLES,
    CONVECTIVE_VARIABLES,
    DATA_RAW_DIR,
    RAW_DATA_FILENAME,
    DEFAULT_START_DATE,
    DEFAULT_END_DATE,
)

logger = logging.getLogger("vajrasense.ingestion")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [VajraSense:Ingestion] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class IngestionError(Exception):
    """Custom exception raised when weather data ingestion fails."""
    pass


class OpenMeteoIngestion:
    """
    Robust data acquisition client for Mumbai atmospheric conditions
    leveraging the Open-Meteo API.
    """

    def __init__(
        self,
        latitude: float = MUMBAI_LATITUDE,
        longitude: float = MUMBAI_LONGITUDE,
        elevation: float = MUMBAI_ELEVATION,
        timezone: str = TIMEZONE,
        max_retries: int = 3,
        backoff_factor: float = 2.0,
        request_timeout: int = 45,
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.elevation = elevation
        self.timezone = timezone
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.request_timeout = request_timeout
        self.session = requests.Session()

    def _execute_api_request(
        self, url: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Executes an HTTP GET request with exponential backoff retry logic.
        """
        attempt = 0
        last_exception = None

        while attempt < self.max_retries:
            attempt += 1
            try:
                logger.info(
                    f"Requesting Open-Meteo API (Attempt {attempt}/{self.max_retries}) | URL: {url}"
                )
                response = self.session.get(
                    url, params=params, timeout=self.request_timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    if "error" in data and data["error"]:
                        raise IngestionError(
                            f"Open-Meteo API error message: {data.get('reason', 'Unknown reason')}"
                        )
                    return data

                elif response.status_code == 429:
                    wait_time = self.backoff_factor ** attempt
                    logger.warning(
                        f"Rate limit encountered (HTTP 429). Backing off for {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.warning(
                        f"HTTP {response.status_code}: {response.text[:200]}"
                    )
                    time.sleep(self.backoff_factor ** attempt)

            except (requests.RequestException, ValueError) as ex:
                last_exception = ex
                wait_time = self.backoff_factor ** attempt
                logger.warning(
                    f"Network or parsing error on attempt {attempt}: {ex}. Retrying in {wait_time:.1f}s..."
                )
                time.sleep(wait_time)

        raise IngestionError(
            f"Failed to query Open-Meteo after {self.max_retries} attempts: {last_exception}"
        )

    def fetch_period_data(
        self, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        Fetches both surface ERA5 reanalysis and GFS convective sounding
        parameters for a specified date range and merges them on hourly timestamps.
        """
        logger.info(
            f"Fetching atmospheric reanalysis for Mumbai [{start_date} to {end_date}]..."
        )

        # 1. Fetch Surface Parameters (ERA5 Reanalysis)
        surface_params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join(SURFACE_VARIABLES),
            "timezone": self.timezone,
        }
        surface_json = self._execute_api_request(
            OPEN_METEO_ARCHIVE_URL, surface_params
        )

        if "hourly" not in surface_json or "time" not in surface_json["hourly"]:
            raise IngestionError("Surface weather API response missing 'hourly' payload.")

        df_surface = pd.DataFrame(surface_json["hourly"])
        logger.info(
            f"Retrieved {len(df_surface)} surface records across {len(df_surface.columns)} variables."
        )

        # 2. Fetch Convective Sounding Instability Indices (GFS Seamless)
        convective_params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": self.elevation,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": ",".join(CONVECTIVE_VARIABLES),
            "models": "gfs_seamless",
            "timezone": self.timezone,
        }

        try:
            convective_json = self._execute_api_request(
                OPEN_METEO_ARCHIVE_URL, convective_params
            )
            if "hourly" in convective_json and "time" in convective_json["hourly"]:
                df_convective = pd.DataFrame(convective_json["hourly"])
                logger.info(
                    f"Retrieved {len(df_convective)} convective sounding records (CAPE, LI, CIN)."
                )
                df_merged = pd.merge(df_surface, df_convective, on="time", how="left")
            else:
                logger.warning(
                    "Convective indices payload missing; falling back to surface data only."
                )
                df_merged = df_surface
                for col in CONVECTIVE_VARIABLES:
                    df_merged[col] = float("nan")
        except Exception as ex:
            logger.warning(
                f"Could not retrieve GFS convective sounding indices ({ex}). Proceeding with surface features."
            )
            df_merged = df_surface
            for col in CONVECTIVE_VARIABLES:
                df_merged[col] = float("nan")

        return df_merged

    def download_historical_archive(
        self,
        start_date: str = DEFAULT_START_DATE,
        end_date: str = DEFAULT_END_DATE,
        output_filepath: Optional[Path] = None,
        chunk_years: bool = True,
    ) -> pd.DataFrame:
        """
        Downloads historical weather data spanning multiple years.
        Supports yearly chunking to avoid timeouts on large queries.
        Saves the resulting dataset to a CSV file.
        """
        if output_filepath is None:
            output_filepath = DATA_RAW_DIR / RAW_DATA_FILENAME

        output_filepath = Path(output_filepath)
        output_filepath.parent.mkdir(parents=True, exist_ok=True)

        dt_start = datetime.strptime(start_date, "%Y-%m-%d")
        dt_end = datetime.strptime(end_date, "%Y-%m-%d")

        if dt_start > dt_end:
            raise ValueError(
                f"Start date {start_date} cannot be after end date {end_date}"
            )

        # If span is greater than 1 year and chunking requested, batch by calendar year
        if chunk_years and (dt_end.year - dt_start.year >= 1):
            chunks: List[pd.DataFrame] = []
            current_year = dt_start.year

            while current_year <= dt_end.year:
                chunk_start = max(
                    dt_start, datetime(current_year, 1, 1)
                ).strftime("%Y-%m-%d")
                chunk_end = min(
                    dt_end, datetime(current_year, 12, 31)
                ).strftime("%Y-%m-%d")

                logger.info(
                    f"--- Downloading Ingestion Chunk: {chunk_start} to {chunk_end} ---"
                )
                chunk_df = self.fetch_period_data(chunk_start, chunk_end)
                chunks.append(chunk_df)
                current_year += 1
                # Courtesy pause between batch queries to respect public endpoint rate limits
                time.sleep(1.0)

            full_df = pd.concat(chunks, ignore_index=True)
            # Remove any duplicate timestamps at chunk boundaries
            full_df = full_df.drop_duplicates(subset=["time"]).reset_index(drop=True)
        else:
            full_df = self.fetch_period_data(start_date, end_date)

        logger.info(
            f"Successfully compiled dataset with {len(full_df):,} hourly observations."
        )

        # Save to CSV
        full_df.to_csv(output_filepath, index=False)
        logger.info(f"Raw data successfully saved to: {output_filepath.resolve()}")

        return full_df

    def fetch_live_nowcast_feed(
        self, past_hours: int = 48, forecast_hours: int = 24
    ) -> pd.DataFrame:
        """
        Fetches the recent 48-hour observational sequence + 24-hour upcoming forecast
        from Open-Meteo's operational forecast endpoint for live nowcasting inference.
        """
        logger.info("Fetching operational live nowcasting feed for Mumbai...")
        all_variables = SURFACE_VARIABLES + CONVECTIVE_VARIABLES

        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "past_days": max(1, past_hours // 24),
            "forecast_days": max(1, forecast_hours // 24),
            "hourly": ",".join(all_variables),
            "timezone": self.timezone,
        }

        feed_json = self._execute_api_request(OPEN_METEO_FORECAST_URL, params)
        if "hourly" not in feed_json:
            raise IngestionError("Operational forecast feed missing 'hourly' payload.")

        df_feed = pd.DataFrame(feed_json["hourly"])
        logger.info(f"Retrieved {len(df_feed)} operational sequence records.")
        return df_feed
