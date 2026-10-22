"""
वज्रSense (VajraSense) — Pipeline: Weather Data & Scenario Generation
Simulates multi-sensor atmospheric data with realistic meteorology for Indian convective regimes:
- Doppler Weather Radar: Reflectivity (dBZ, 0-65+), Vertically Integrated Liquid (VIL, kg/m²)
- Geostationary Satellite: Cloud Top Brightness Temperature (IR 10.8µm, °C)
- Lightning Detection Network: Real-time stroke coordinates and strike density (flashes/100km²/10min)
- Numerical Weather Prediction (NWP): CAPE (J/kg), Lifted Index (°C), 0-6km Bulk Wind Shear (m/s), Precipitable Water (mm)
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Any


# Standard Meteorological Stations / Radar Nodes in India for Demo & Monitoring
STATIONS = {
    "VABB_MUMBAI": {
        "name": "Mumbai (Konkan Coast / MMR)",
        "lat": 19.0760,
        "lon": 72.8777,
        "elevation_m": 14,
        "climate_zone": "Tropical Coastal Monsoon & Pre-monsoon Convective",
        "radar_range_km": 250
    },
    "VECC_KOLKATA": {
        "name": "Kolkata (Gangetic West Bengal)",
        "lat": 22.5726,
        "lon": 88.3639,
        "elevation_m": 9,
        "climate_zone": "Tropical Wet & Dry (Kalbaishakhi / Nor'wester belt)",
        "radar_range_km": 250
    },
    "VIDP_DELHI": {
        "name": "Delhi-NCR (Indira Gandhi Int'l)",
        "lat": 28.5562,
        "lon": 77.1000,
        "elevation_m": 237,
        "climate_zone": "Semi-Arid / Pre-monsoon Dust-Thunderstorms",
        "radar_range_km": 250
    },
    "VOBL_BENGALURU": {
        "name": "Bengaluru (Deccan Plateau)",
        "lat": 13.1986,
        "lon": 77.7066,
        "elevation_m": 920,
        "climate_zone": "Tropical Savanna / Convective High-Plateau",
        "radar_range_km": 250
    },
    "VEBS_BHUBANESWAR": {
        "name": "Bhubaneswar (Odisha Coastal Belt)",
        "lat": 20.2444,
        "lon": 85.8178,
        "elevation_m": 42,
        "climate_zone": "Severe Coastal Convective Zone",
        "radar_range_km": 250
    },
    "VEGT_GUWAHATI": {
        "name": "Guwahati (Brahmaputra Valley)",
        "lat": 26.1061,
        "lon": 91.5859,
        "elevation_m": 55,
        "climate_zone": "Subtropical Humid Orographic Convection",
        "radar_range_km": 250
    }
}


# Pre-configured Convective Atmospheric Scenarios
SCENARIOS = {
    "mumbai_severe": {
        "id": "mumbai_severe",
        "title": "Mumbai Severe Convective Squall (Severe)",
        "station_key": "VABB_MUMBAI",
        "description": "Explosive coastal thunderstorm cluster advancing from Arabian Sea across Mumbai, Thane, and Navi Mumbai with intense cloud-to-ground lightning and severe wind gusts.",
        "severity_expected": "Severe",
        "env_cape": 3480.0,
        "env_cin": 18.0,
        "env_lifted_index": -7.2,
        "env_shear_0_6km": 23.0,
        "env_pw": 58.0,
        "storm_cells": [
            {
                "id": "CELL_MUMBAI_NORTH",
                "center_lat": 19.22,
                "center_lon": 72.86,
                "max_dbz": 63.0,
                "vil": 48.0,
                "cloud_top_temp_c": -70.0,
                "radius_km": 26.0,
                "speed_kmh": 46.0,
                "heading_deg": 75.0, # Moving ENE across Borivali & Thane
                "growth_rate_dbz_hr": 4.0,
                "flash_rate_per_min": 88
            },
            {
                "id": "CELL_MUMBAI_SOUTH",
                "center_lat": 18.94,
                "center_lon": 72.76,
                "max_dbz": 56.0,
                "vil": 38.0,
                "cloud_top_temp_c": -62.0,
                "radius_km": 22.0,
                "speed_kmh": 40.0,
                "heading_deg": 70.0, # Moving ENE across Colaba & Harbour
                "growth_rate_dbz_hr": 2.2,
                "flash_rate_per_min": 45
            }
        ]
    },
    "mumbai_pulse": {
        "id": "mumbai_pulse",
        "title": "Mumbai Afternoon Heat Convection (Elevated)",
        "station_key": "VABB_MUMBAI",
        "description": "Diurnal sea-breeze convergence thunderstorm cell developing over Thane-Navi Mumbai with localized high-rate lightning.",
        "severity_expected": "Elevated",
        "env_cape": 2550.0,
        "env_cin": 35.0,
        "env_lifted_index": -4.8,
        "env_shear_0_6km": 14.5,
        "env_pw": 46.0,
        "storm_cells": [
            {
                "id": "CELL_THANE_PULSE",
                "center_lat": 19.14,
                "center_lon": 73.01,
                "max_dbz": 50.0,
                "vil": 30.0,
                "cloud_top_temp_c": -57.0,
                "radius_km": 18.0,
                "speed_kmh": 22.0,
                "heading_deg": 80.0,
                "growth_rate_dbz_hr": -1.2,
                "flash_rate_per_min": 30
            }
        ]
    },
    "norwester": {
        "id": "norwester",
        "title": "Kalbaishakhi / Nor'wester Supercell",
        "station_key": "VECC_KOLKATA",
        "description": "Violent squall line with severe hail, intense cloud-to-ground lightning, and explosive updrafts advancing southeastward.",
        "severity_expected": "Severe",
        "env_cape": 3650.0,
        "env_cin": 25.0,
        "env_lifted_index": -7.5,
        "env_shear_0_6km": 24.5,
        "env_pw": 56.0,
        "storm_cells": [
            {
                "id": "CELL_ALPHA",
                "center_lat": 22.85,
                "center_lon": 88.05,
                "max_dbz": 62.0,
                "vil": 48.0,
                "cloud_top_temp_c": -72.0,
                "radius_km": 28.0,
                "speed_kmh": 54.0,
                "heading_deg": 125.0, # Moving Southeast
                "growth_rate_dbz_hr": 4.5,
                "flash_rate_per_min": 85
            },
            {
                "id": "CELL_BETA",
                "center_lat": 23.20,
                "center_lon": 87.80,
                "max_dbz": 54.0,
                "vil": 36.0,
                "cloud_top_temp_c": -64.0,
                "radius_km": 22.0,
                "speed_kmh": 48.0,
                "heading_deg": 130.0,
                "growth_rate_dbz_hr": 2.0,
                "flash_rate_per_min": 42
            }
        ]
    },
    "isolated_pulse": {
        "id": "isolated_pulse",
        "title": "Afternoon Convective Pulse Storm",
        "station_key": "VIDP_DELHI",
        "description": "Diurnally heated multi-cellular thunderstorm cell producing sudden high-intensity lightning strikes and localized microbursts.",
        "severity_expected": "Elevated",
        "env_cape": 2450.0,
        "env_cin": 45.0,
        "env_lifted_index": -4.8,
        "env_shear_0_6km": 14.0,
        "env_pw": 44.0,
        "storm_cells": [
            {
                "id": "CELL_PULSE_01",
                "center_lat": 28.68,
                "center_lon": 77.02,
                "max_dbz": 49.0,
                "vil": 28.0,
                "cloud_top_temp_c": -58.0,
                "radius_km": 16.0,
                "speed_kmh": 22.0,
                "heading_deg": 85.0, # Slow Eastward drift
                "growth_rate_dbz_hr": -1.5,
                "flash_rate_per_min": 28
            }
        ]
    },
    "monsoon_squall": {
        "id": "monsoon_squall",
        "title": "Monsoon Convective Band",
        "station_key": "VABB_MUMBAI",
        "description": "Broad maritime convective band with heavy precipitation, embedded thunder cells, and moderate lightning hazard.",
        "severity_expected": "Moderate",
        "env_cape": 1850.0,
        "env_cin": 60.0,
        "env_lifted_index": -2.8,
        "env_shear_0_6km": 12.0,
        "env_pw": 68.0,
        "storm_cells": [
            {
                "id": "CELL_COAST_01",
                "center_lat": 18.95,
                "center_lon": 72.65,
                "max_dbz": 44.0,
                "vil": 24.0,
                "cloud_top_temp_c": -52.0,
                "radius_km": 35.0,
                "speed_kmh": 36.0,
                "heading_deg": 65.0, # Moving inland NE
                "growth_rate_dbz_hr": 0.5,
                "flash_rate_per_min": 14
            }
        ]
    },
    "fair_weather": {
        "id": "fair_weather",
        "title": "Mumbai Fair Weather / Stable Coast",
        "station_key": "VABB_MUMBAI",
        "description": "High barometric stability, dry air aloft, clear skies over Mumbai and Konkan coast without convective vertical development.",
        "severity_expected": "Low",
        "env_cape": 420.0,
        "env_cin": 180.0,
        "env_lifted_index": 3.2,
        "env_shear_0_6km": 6.0,
        "env_pw": 28.0,
        "storm_cells": []
    }
}


def generate_grid_reflectivity(center_lat: float, center_lon: float,
                               cells: List[Dict[str, Any]],
                               radius_deg: float = 1.2,
                               resolution: int = 35) -> Dict[str, Any]:
    """
    Computes a 2D synthetic radar reflectivity grid centered around the station.
    Calculates dBZ values using Gaussian convective profiles for storm cells.
    """
    lats = np.linspace(center_lat - radius_deg, center_lat + radius_deg, resolution)
    lons = np.linspace(center_lon - radius_deg, center_lon + radius_deg, resolution)
    grid_points = []

    km_per_deg_lat = 111.0
    km_per_deg_lon = 111.0 * np.cos(np.radians(center_lat))

    for lat in lats:
        for lon in lons:
            dbz = float(np.random.uniform(5.0, 15.0))
            active_cell = None

            for cell in cells:
                d_lat_km = (lat - cell["center_lat"]) * km_per_deg_lat
                d_lon_km = (lon - cell["center_lon"]) * km_per_deg_lon
                dist_km = np.sqrt(d_lat_km**2 + d_lon_km**2)
                
                if dist_km <= cell["radius_km"] * 1.5:
                    profile = np.exp(-0.5 * (dist_km / (cell["radius_km"] * 0.45))**2)
                    cell_dbz = cell["max_dbz"] * profile
                    if cell_dbz > dbz:
                        dbz = float(cell_dbz)
                        active_cell = cell["id"]

            grid_points.append({
                "lat": round(float(lat), 4),
                "lon": round(float(lon), 4),
                "dbz": round(float(np.clip(dbz, 0.0, 75.0)), 1),
                "cell_id": active_cell
            })

    return {
        "resolution": resolution,
        "points": grid_points,
        "center": {"lat": center_lat, "lon": center_lon}
    }


def generate_lightning_strikes(cells: List[Dict[str, Any]], count_scale: float = 1.0) -> List[Dict[str, Any]]:
    """
    Synthesizes discrete cloud-to-ground and intra-cloud lightning strikes
    clustered in high-reflectivity (>38 dBZ) updraft cores.
    """
    strikes = []
    strike_id = 1

    for cell in cells:
        num_strikes = int(np.random.poisson(cell.get("flash_rate_per_min", 10) * count_scale * 0.5))
        for _ in range(num_strikes):
            rad_deg = (cell["radius_km"] * 0.35) / 111.0
            angle = np.random.uniform(0, 2 * np.pi)
            r = np.random.normal(0, rad_deg * 0.6)
            s_lat = cell["center_lat"] + r * np.sin(angle)
            s_lon = cell["center_lon"] + (r * np.cos(angle)) / np.cos(np.radians(cell["center_lat"]))
            
            peak_current_ka = float(np.random.exponential(scale=22.0) + 8.0)
            stroke_type = np.random.choice(["CG_NEGATIVE", "CG_POSITIVE", "INTRA_CLOUD"], p=[0.68, 0.12, 0.20])
            age_secs = int(np.random.randint(5, 540))

            strikes.append({
                "id": f"FL_{strike_id:04d}",
                "lat": round(float(s_lat), 4),
                "lon": round(float(s_lon), 4),
                "peak_current_ka": round(peak_current_ka, 1),
                "type": stroke_type,
                "age_secs": age_secs,
                "cell_id": cell["id"]
            })
            strike_id += 1

    return strikes
