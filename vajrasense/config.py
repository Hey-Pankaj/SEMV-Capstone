"""
Configuration settings for वज्रSense (VajraSense).
Contains geographic coordinates, API endpoints, physical boundary thresholds,
and pipeline paths.
"""

from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = BASE_DIR / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
MODELS_DIR = BASE_DIR / "models_saved"

# Create directories if they do not exist
for directory in [DATA_RAW_DIR, DATA_PROCESSED_DIR, FIGURES_DIR, MODELS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Geographic Coordinates for Mumbai (Centroid covering Santacruz & Colaba observatories)
MUMBAI_LATITUDE = 19.0760
MUMBAI_LONGITUDE = 72.8777
MUMBAI_ELEVATION = 14.0  # meters above sea level
TIMEZONE = "Asia/Kolkata"

# Open-Meteo Endpoints
OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# Default Historical Ingestion Window (3 Full Years for robust seasonal coverage)
DEFAULT_START_DATE = "2022-01-01"
DEFAULT_END_DATE = "2024-12-31"

# Target Filenames
RAW_DATA_FILENAME = "mumbai_weather_raw_2022_2024.csv"
CLEAN_DATA_FILENAME = "mumbai_weather_clean.csv"
ENGINEERED_DATA_FILENAME = "mumbai_weather_features.csv"

# Meteorological Variables Requested from Open-Meteo ERA5 Reanalysis
SURFACE_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "apparent_temperature",
    "surface_pressure",
    "precipitation",
    "rain",
    "weather_code",
    "cloud_cover",
    "cloud_cover_low",
    "cloud_cover_mid",
    "cloud_cover_high",
    "wind_speed_10m",
    "wind_speed_100m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

# Thermodynamic Sounding & Instability Variables (from GFS Seamless Reanalysis)
CONVECTIVE_VARIABLES = [
    "cape",                    # Convective Available Potential Energy (J/kg)
    "lifted_index",            # Lifted Index (°C, negative = unstable)
    "convective_inhibition",   # CIN (J/kg)
]

# Physical Plausibility Ranges for Data Quality Auditing (Mumbai Coastal Climate)
PHYSICAL_BOUNDS = {
    "temperature_2m": (10.0, 48.0),       # Celsius (historical Mumbai min ~11°C, max ~42°C)
    "relative_humidity_2m": (5.0, 100.0), # Percentage
    "dew_point_2m": (5.0, 32.0),          # Celsius
    "surface_pressure": (970.0, 1035.0),  # hPa (low during cyclonic depression, high in winter)
    "precipitation": (0.0, 180.0),        # mm/hour (intense tropical cloudburst limit)
    "wind_speed_10m": (0.0, 150.0),       # km/h
    "wind_speed_100m": (0.0, 180.0),      # km/h
    "wind_gusts_10m": (0.0, 180.0),       # km/h
    "cape": (0.0, 6000.0),                # J/kg
    "lifted_index": (-15.0, 15.0),        # Celsius
    "convective_inhibition": (-800.0, 0.0)# J/kg
}

# Meteorological Convective Regimes for Physical Ground-Truth Proxy
# Note: In accordance with project scientific standards, we do NOT fabricate fake lightning strikes.
# Convective storm regimes are defined by validated atmospheric instability and radar/reanalysis proxies.
CONVECTIVE_THRESHOLDS = {
    "cape_moderate": 1000.0,    # J/kg: minimum energy for moderate tropical convection
    "cape_severe": 1800.0,      # J/kg: high potential for deep convective updrafts & electrification
    "lifted_index_unstable": -2.0,  # Below -2 indicates significant atmospheric instability
    "lifted_index_extreme": -5.0,   # Below -5 indicates severe thunderstorm & lightning probability
    "heavy_rain_rate": 5.0,     # mm/hour
    "gust_threshold": 35.0,     # km/h squall line threshold
}
