"""
वज्रSense (VajraSense) — Storm Cell Tracking & Multi-Horizon Nowcaster
Calculates storm centroid advection vectors, cell kinematics, and projected hazard cones
for the 0–30 min, 30–60 min, and 60–120 min forecasting windows.
"""

import numpy as np
from typing import Dict, List, Any


def project_cell_position(lat: float, lon: float, speed_kmh: float, heading_deg: float, minutes: float) -> Dict[str, float]:
    distance_km = (speed_kmh / 60.0) * minutes
    heading_rad = np.radians(heading_deg)

    d_lat = (distance_km * np.cos(heading_rad)) / 111.0
    d_lon = (distance_km * np.sin(heading_rad)) / (111.0 * np.cos(np.radians(lat)))

    proj_lat = lat + d_lat
    proj_lon = lon + d_lon
    uncertainty_radius_km = 3.0 + (distance_km * 0.35)

    return {
        "lat": round(float(proj_lat), 4),
        "lon": round(float(proj_lon), 4),
        "distance_km": round(float(distance_km), 1),
        "uncertainty_radius_km": round(float(uncertainty_radius_km), 1)
    }


class NowcastingEngine:
    def __init__(self, fuzzy_engine, ml_model):
        self.fuzzy_engine = fuzzy_engine
        self.ml_model = ml_model

    def generate_nowcast(self, scenario: Dict[str, Any], station_info: Dict[str, Any]) -> Dict[str, Any]:
        cells = scenario.get("storm_cells", [])
        env_cape = scenario.get("env_cape", 1500.0)
        env_shear = scenario.get("env_shear_0_6km", 15.0)

        if cells:
            max_dbz = max(c["max_dbz"] for c in cells)
            max_vil = max(c["vil"] for c in cells)
            min_cloud_temp = min(c["cloud_top_temp_c"] for c in cells)
            total_flash_rate = sum(c.get("flash_rate_per_min", 0) for c in cells)
        else:
            max_dbz = 12.0
            max_vil = 2.0
            min_cloud_temp = 8.0
            total_flash_rate = 0

        current_fuzzy = self.fuzzy_engine.evaluate(
            cape=env_cape,
            dbz=max_dbz,
            flash_rate=total_flash_rate,
            shear=env_shear
        )

        ml_feats = {
            "radar_max_dbz": max_dbz,
            "radar_mean_dbz": max_dbz * 0.6,
            "radar_vil": max_vil,
            "cloud_top_temp_c": min_cloud_temp,
            "lightning_count_10m": total_flash_rate * 10,
            "cape_j_kg": env_cape,
            "cin_j_kg": scenario.get("env_cin", 30.0),
            "lifted_index": scenario.get("env_lifted_index", -3.5),
            "shear_0_6km_ms": env_shear,
            "precipitable_water_mm": scenario.get("env_pw", 45.0)
        }
        current_ml = self.ml_model.predict_risk(ml_feats)

        horizons = [
            {"key": "h_0_30", "label": "0–30 min", "minutes": 15, "category_desc": "Immediate Tactical Horizon"},
            {"key": "h_30_60", "label": "30–60 min", "minutes": 45, "category_desc": "Short-Term Extrapolation"},
            {"key": "h_60_120", "label": "60–120 min", "minutes": 90, "category_desc": "Thermodynamic Environment Trend"}
        ]

        projections = []
        for h in horizons:
            t = h["minutes"]
            projected_cells = []

            for cell in cells:
                proj_pos = project_cell_position(
                    lat=cell["center_lat"],
                    lon=cell["center_lon"],
                    speed_kmh=cell["speed_kmh"],
                    heading_deg=cell["heading_deg"],
                    minutes=t
                )

                growth_rate = cell.get("growth_rate_dbz_hr", 0.0)
                dbz_delta = (growth_rate * (t / 60.0))
                if t > 60:
                    dbz_delta -= 3.5 * ((t - 60) / 60.0)

                proj_dbz = np.clip(cell["max_dbz"] + dbz_delta, 10.0, 70.0)
                proj_flash = np.clip(cell.get("flash_rate_per_min", 0) * (proj_dbz / max(cell["max_dbz"], 1.0)), 0, 150)

                projected_cells.append({
                    "id": cell["id"],
                    "projected_lat": proj_pos["lat"],
                    "projected_lon": proj_pos["lon"],
                    "distance_km": proj_pos["distance_km"],
                    "uncertainty_km": proj_pos["uncertainty_radius_km"],
                    "projected_dbz": round(float(proj_dbz), 1),
                    "projected_flash_rate": round(float(proj_flash), 0)
                })

            if projected_cells:
                h_max_dbz = max(c["projected_dbz"] for c in projected_cells)
                h_flash = sum(c["projected_flash_rate"] for c in projected_cells)
            else:
                h_max_dbz = 10.0
                h_flash = 0

            confidence_pct = round(max(50.0, 95.0 - (t * 0.36)), 0)

            h_fuzzy = self.fuzzy_engine.evaluate(
                cape=env_cape * (0.95 if t > 60 else 1.0),
                dbz=h_max_dbz,
                flash_rate=h_flash,
                shear=env_shear
            )

            projections.append({
                "horizon": h["key"],
                "label": h["label"],
                "target_minutes": t,
                "description": h["category_desc"],
                "confidence_pct": confidence_pct,
                "risk_score": h_fuzzy["score"],
                "risk_category": h_fuzzy["category"],
                "risk_color": h_fuzzy["color"],
                "projected_max_dbz": round(float(h_max_dbz), 1),
                "cells": projected_cells
            })

        return {
            "current_state": {
                "fuzzy_risk": current_fuzzy,
                "ml_prediction": current_ml,
                "max_dbz": round(float(max_dbz), 1),
                "vil": round(float(max_vil), 1),
                "flash_rate": total_flash_rate,
                "env_cape": env_cape,
                "env_shear": env_shear
            },
            "projections": projections
        }
