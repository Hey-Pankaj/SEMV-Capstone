"""
वज्रSense (VajraSense) — Core Application Server
Flask REST API and dashboard server coordinating data ingestion,
AI/ML risk classification, fuzzy logic inference, and geospatial rendering.
"""

import os
import sys
from flask import Flask, render_template, jsonify, request

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from pipeline.weather_data import (
    STATIONS, SCENARIOS,
    generate_grid_reflectivity, generate_lightning_strikes
)
from models.fuzzy_engine import FuzzyRiskEngine
from models.ml_classifier import ThunderstormMLModel
from models.storm_tracker import NowcastingEngine, project_cell_position
from models.evaluation import get_benchmark_evaluation

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT_DIR, "templates"),
    static_folder=os.path.join(ROOT_DIR, "static")
)

fuzzy_engine = FuzzyRiskEngine()
ml_model = ThunderstormMLModel()
nowcasting_engine = NowcastingEngine(fuzzy_engine, ml_model)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/stations", methods=["GET"])
def get_stations():
    return jsonify({"status": "success", "stations": STATIONS})


@app.route("/api/scenarios", methods=["GET"])
def get_scenarios():
    summary = {}
    for sid, sc in SCENARIOS.items():
        summary[sid] = {
            "id": sc["id"],
            "title": sc["title"],
            "station_key": sc["station_key"],
            "description": sc["description"],
            "severity_expected": sc["severity_expected"],
            "cell_count": len(sc.get("storm_cells", []))
        }
    return jsonify({"status": "success", "scenarios": summary})


@app.route("/api/nowcast", methods=["GET"])
def get_nowcast():
    scenario_id = request.args.get("scenario", "norwester")
    time_min = int(request.args.get("minutes", 0))

    if scenario_id not in SCENARIOS:
        scenario_id = "norwester"

    scenario = SCENARIOS[scenario_id]
    station_key = request.args.get("station", scenario["station_key"])
    if station_key not in STATIONS:
        station_key = scenario["station_key"]

    station = STATIONS[station_key]
    base_cells = scenario.get("storm_cells", [])

    projected_cells = []
    for cell in base_cells:
        proj = project_cell_position(
            lat=cell["center_lat"],
            lon=cell["center_lon"],
            speed_kmh=cell["speed_kmh"],
            heading_deg=cell["heading_deg"],
            minutes=time_min
        )
        
        growth = cell.get("growth_rate_dbz_hr", 0.0)
        delta_dbz = (growth * (time_min / 60.0))
        if time_min > 60:
            delta_dbz -= 3.0 * ((time_min - 60) / 60.0)
            
        p_dbz = max(10.0, min(70.0, cell["max_dbz"] + delta_dbz))
        p_flash = max(0, int(cell.get("flash_rate_per_min", 0) * (p_dbz / max(cell["max_dbz"], 1.0))))

        projected_cells.append({
            "id": cell["id"],
            "center_lat": proj["lat"],
            "center_lon": proj["lon"],
            "origin_lat": cell["center_lat"],
            "origin_lon": cell["center_lon"],
            "max_dbz": round(p_dbz, 1),
            "vil": max(1.0, round(cell["vil"] * (p_dbz / cell["max_dbz"]), 1)),
            "cloud_top_temp_c": cell["cloud_top_temp_c"],
            "radius_km": cell["radius_km"] + (time_min * 0.08),
            "speed_kmh": cell["speed_kmh"],
            "heading_deg": cell["heading_deg"],
            "flash_rate_per_min": p_flash,
            "uncertainty_radius_km": proj["uncertainty_radius_km"],
            "trajectory": [
                project_cell_position(cell["center_lat"], cell["center_lon"], cell["speed_kmh"], cell["heading_deg"], m)
                for m in [0, 15, 30, 45, 60, 90, 120]
            ]
        })

    grid_center_lat = station["lat"]
    grid_center_lon = station["lon"]
    radar_grid = generate_grid_reflectivity(grid_center_lat, grid_center_lon, projected_cells, radius_deg=1.2, resolution=32)

    lightning_scale = max(0.2, 1.0 - (time_min * 0.005))
    strikes = generate_lightning_strikes(projected_cells, count_scale=lightning_scale)

    nowcast_data = nowcasting_engine.generate_nowcast(scenario, station)

    if projected_cells:
        cur_max_dbz = max(c["max_dbz"] for c in projected_cells)
        cur_vil = max(c["vil"] for c in projected_cells)
        cur_flash_rate = sum(c["flash_rate_per_min"] for c in projected_cells)
    else:
        cur_max_dbz = 12.0
        cur_vil = 1.0
        cur_flash_rate = 0

    fuzzy_eval = fuzzy_engine.evaluate(
        cape=scenario.get("env_cape", 1200.0),
        dbz=cur_max_dbz,
        flash_rate=cur_flash_rate,
        shear=scenario.get("env_shear_0_6km", 14.0)
    )

    ml_eval = ml_model.predict_risk({
        "radar_max_dbz": cur_max_dbz,
        "radar_mean_dbz": cur_max_dbz * 0.6,
        "radar_vil": cur_vil,
        "cloud_top_temp_c": min([c["cloud_top_temp_c"] for c in projected_cells], default=5.0),
        "lightning_count_10m": cur_flash_rate * 10,
        "cape_j_kg": scenario.get("env_cape", 1200.0),
        "cin_j_kg": scenario.get("env_cin", 30.0),
        "lifted_index": scenario.get("env_lifted_index", -3.0),
        "shear_0_6km_ms": scenario.get("env_shear_0_6km", 14.0),
        "precipitable_water_mm": scenario.get("env_pw", 45.0)
    })

    return jsonify({
        "status": "success",
        "scenario_id": scenario_id,
        "station": station,
        "time_minutes": time_min,
        "radar_grid": radar_grid,
        "cells": projected_cells,
        "lightning_strikes": strikes,
        "fuzzy_risk": fuzzy_eval,
        "ml_risk": ml_eval,
        "environmental_params": {
            "cape_j_kg": scenario.get("env_cape", 1200.0),
            "cin_j_kg": scenario.get("env_cin", 30.0),
            "lifted_index": scenario.get("env_lifted_index", -3.0),
            "shear_0_6km_ms": scenario.get("env_shear_0_6km", 14.0),
            "precipitable_water_mm": scenario.get("env_pw", 45.0),
            "max_dbz": cur_max_dbz,
            "vil": cur_vil,
            "flash_rate": cur_flash_rate
        },
        "horizons": nowcast_data["projections"]
    })


@app.route("/api/fuzzy-explain", methods=["GET"])
def explain_fuzzy():
    cape = float(request.args.get("cape", 2500))
    dbz = float(request.args.get("dbz", 45))
    flash = float(request.args.get("flash", 20))
    shear = float(request.args.get("shear", 16))

    result = fuzzy_engine.evaluate(cape=cape, dbz=dbz, flash_rate=flash, shear=shear)
    return jsonify({"status": "success", "result": result})


@app.route("/api/evaluation", methods=["GET"])
def get_evaluation():
    eval_data = get_benchmark_evaluation()
    return jsonify({"status": "success", "data": eval_data})


@app.route("/api/model-info", methods=["GET"])
def get_model_info():
    return jsonify({
        "status": "success",
        "feature_importances": ml_model.feature_importances,
        "classes": ["Low", "Moderate", "Elevated", "Severe"]
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
