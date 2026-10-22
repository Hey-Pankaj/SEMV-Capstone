"""
वज्रSense (VajraSense) — Core Application Server
Flask REST API and dashboard server coordinating data ingestion,
AI/ML risk classification, fuzzy logic inference, and geospatial rendering.
"""

import os
import sys
import json
import urllib.request
import datetime
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
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

from vajrasense.config import CARTO_API_KEY

fuzzy_engine = FuzzyRiskEngine()
ml_model = ThunderstormMLModel()
nowcasting_engine = NowcastingEngine(fuzzy_engine, ml_model)


@app.route("/health", methods=["GET"])
@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "healthy",
        "service": "vajrasense-nowcaster",
        "version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    }), 200


@app.route("/")
def index():
    return render_template("index.html", carto_api_key=CARTO_API_KEY)


@app.route("/api/config", methods=["GET"])
def get_config():
    return jsonify({"carto_api_key": CARTO_API_KEY})


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
    scenario_id = request.args.get("scenario", "mumbai_severe")
    time_min = int(request.args.get("minutes", 0))

    if scenario_id not in SCENARIOS:
        scenario_id = "mumbai_severe"

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
        "station_key": station_key,
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


WMO_DESCRIPTIONS = {
    0: ("Clear Sky", "☀️"),
    1: ("Mainly Clear", "🌤️"),
    2: ("Partly Cloudy", "⛅"),
    3: ("Overcast", "☁️"),
    45: ("Foggy", "🌫️"),
    48: ("Depositing Rime Fog", "🌫️"),
    51: ("Light Drizzle", "🌦️"),
    53: ("Moderate Drizzle", "🌦️"),
    55: ("Dense Drizzle", "🌧️"),
    61: ("Slight Rain", "🌦️"),
    63: ("Moderate Rain", "🌧️"),
    65: ("Heavy Rain", "🌧️"),
    71: ("Slight Snow", "🌨️"),
    73: ("Moderate Snow", "🌨️"),
    75: ("Heavy Snow", "❄️"),
    80: ("Slight Rain Showers", "🌦️"),
    81: ("Moderate Rain Showers", "🌧️"),
    82: ("Violent Rain Showers", "⛈️"),
    95: ("Thunderstorm", "⛈️"),
    96: ("Thunderstorm with Slight Hail", "⛈️"),
    99: ("Thunderstorm with Heavy Hail", "⛈️")
}


def deg_to_compass(deg):
    val = int((deg / 22.5) + .5)
    arr = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE", "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return arr[(val % 16)]


def fetch_real_weather(station_key, lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,"
        "precipitation,rain,weather_code,surface_pressure,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m"
        "&hourly=cape,lifted_index&forecast_days=1&timezone=auto"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VajraSense/1.0"})
        with urllib.request.urlopen(req, timeout=4) as response:
            data = json.loads(response.read().decode("utf-8"))
            curr = data.get("current", {})
            hourly = data.get("hourly", {})

            code = curr.get("weather_code", 0)
            cond_desc, cond_icon = WMO_DESCRIPTIONS.get(code, ("Clear Sky", "☀️"))

            cur_time = curr.get("time", "")
            cape_val = 0.0
            li_val = 0.0
            if "time" in hourly and cur_time:
                cur_hour = cur_time[:13]
                times = hourly.get("time", [])
                match_idx = next((i for i, t in enumerate(times) if t.startswith(cur_hour)), 0)
                capes = hourly.get("cape", [])
                lis = hourly.get("lifted_index", [])
                if match_idx < len(capes) and capes[match_idx] is not None:
                    cape_val = float(capes[match_idx])
                if match_idx < len(lis) and lis[match_idx] is not None:
                    li_val = float(lis[match_idx])

            wind_deg = curr.get("wind_direction_10m", 0)
            wind_dir_card = deg_to_compass(wind_deg)

            if cape_val >= 2500 or li_val <= -5:
                stability_label = "Severe Convective Instability"
                stability_badge = "severe"
                stability_desc = "Extreme atmospheric buoyancy. High risk for rapid thunderstorm updrafts and lightning activity."
            elif cape_val >= 1500 or li_val <= -3:
                stability_label = "Moderate Convective Instability"
                stability_badge = "elevated"
                stability_desc = "Favorable atmospheric buoyancy for convective cloud growth and isolated storm cells."
            elif cape_val >= 600 or li_val < 0:
                stability_label = "Marginal Instability"
                stability_badge = "moderate"
                stability_desc = "Weak convective potential; shallow showers or localized cumulus development possible."
            else:
                stability_label = "Stable Atmosphere"
                stability_badge = "low"
                stability_desc = "Boundary layer is stable and capped; very low probability of deep moist convection."

            return {
                "source": "Open-Meteo Live NWP/WMO Observation",
                "is_live": True,
                "timestamp": cur_time,
                "temperature_c": round(curr.get("temperature_2m", 25.0), 1),
                "apparent_temperature_c": round(curr.get("apparent_temperature", curr.get("temperature_2m", 25.0)), 1),
                "relative_humidity_pct": int(curr.get("relative_humidity_2m", 50)),
                "dew_point_c": round(curr.get("dew_point_2m", 18.0), 1),
                "weather_code": code,
                "condition": cond_desc,
                "icon": cond_icon,
                "surface_pressure_hpa": round(curr.get("surface_pressure", 1012.0), 1),
                "cloud_cover_pct": int(curr.get("cloud_cover", 0)),
                "precipitation_mm": round(curr.get("precipitation", 0.0), 1),
                "rain_mm": round(curr.get("rain", 0.0), 1),
                "wind_speed_kmh": round(curr.get("wind_speed_10m", 0.0), 1),
                "wind_direction_deg": int(wind_deg),
                "wind_direction_compass": wind_dir_card,
                "wind_gusts_kmh": round(curr.get("wind_gusts_10m", 0.0), 1),
                "cape_j_kg": round(cape_val, 1),
                "lifted_index": round(li_val, 1),
                "stability": {
                    "label": stability_label,
                    "badge": stability_badge,
                    "description": stability_desc
                }
            }
    except Exception:
        # Graceful fallback to local raw Mumbai dataset if available
        csv_path = os.path.join(ROOT_DIR, "data", "raw", "mumbai_hourly_weather.csv")
        if station_key == "VABB_MUMBAI" and os.path.exists(csv_path):
            try:
                import pandas as pd
                df = pd.read_csv(csv_path)
                last_row = df.iloc[-1]
                t_col = [c for c in df.columns if "temperature_2m" in c][0]
                rh_col = [c for c in df.columns if "relative_humidity_2m" in c][0]
                dp_col = [c for c in df.columns if "dew_point_2m" in c][0]
                pr_col = [c for c in df.columns if "surface_pressure" in c][0]
                cc_col = [c for c in df.columns if "cloud_cover" in c and "low" not in c and "mid" not in c and "high" not in c][0]
                ws_col = [c for c in df.columns if "wind_speed_10m" in c][0]
                wd_col = [c for c in df.columns if "wind_direction_10m" in c][0]
                wg_col = [c for c in df.columns if "wind_gusts_10m" in c][0]
                cape_col = [c for c in df.columns if "cape" in c][0]
                li_col = [c for c in df.columns if "lifted_index" in c][0]
                precip_col = [c for c in df.columns if "precipitation (" in c or c == "precipitation (mm)"][0]
                wc_col = [c for c in df.columns if "weather_code" in c][0]

                code = int(last_row[wc_col])
                cond_desc, cond_icon = WMO_DESCRIPTIONS.get(code, ("Clear Sky", "☀️"))
                cape_val = float(last_row[cape_col])
                li_val = float(last_row[li_col])
                wind_deg = float(last_row[wd_col])

                return {
                    "source": "Local Observation Archive (mumbai_hourly_weather.csv)",
                    "is_live": False,
                    "timestamp": str(last_row["time"]),
                    "temperature_c": round(float(last_row[t_col]), 1),
                    "apparent_temperature_c": round(float(last_row[t_col]) + 1.5, 1),
                    "relative_humidity_pct": int(last_row[rh_col]),
                    "dew_point_c": round(float(last_row[dp_col]), 1),
                    "weather_code": code,
                    "condition": cond_desc,
                    "icon": cond_icon,
                    "surface_pressure_hpa": round(float(last_row[pr_col]), 1),
                    "cloud_cover_pct": int(last_row[cc_col]),
                    "precipitation_mm": round(float(last_row[precip_col]), 1),
                    "rain_mm": round(float(last_row[precip_col]), 1),
                    "wind_speed_kmh": round(float(last_row[ws_col]), 1),
                    "wind_direction_deg": int(wind_deg),
                    "wind_direction_compass": deg_to_compass(wind_deg),
                    "wind_gusts_kmh": round(float(last_row[wg_col]), 1),
                    "cape_j_kg": round(cape_val, 1),
                    "lifted_index": round(li_val, 1),
                    "stability": {
                        "label": "Moderate Convective Instability",
                        "badge": "elevated",
                        "description": "Historical convective baseline from Mumbai observatory archive."
                    }
                }
            except Exception:
                pass

        return {
            "source": "Atmospheric Climatological Baseline",
            "is_live": False,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%dT%H:%M"),
            "temperature_c": 28.5,
            "apparent_temperature_c": 31.0,
            "relative_humidity_pct": 65,
            "dew_point_c": 21.0,
            "weather_code": 1,
            "condition": "Mainly Clear",
            "icon": "🌤️",
            "surface_pressure_hpa": 1011.0,
            "cloud_cover_pct": 25,
            "precipitation_mm": 0.0,
            "rain_mm": 0.0,
            "wind_speed_kmh": 8.5,
            "wind_direction_deg": 45,
            "wind_direction_compass": "NE",
            "wind_gusts_kmh": 14.0,
            "cape_j_kg": 1200.0,
            "lifted_index": -2.5,
            "stability": {
                "label": "Marginal Instability",
                "badge": "moderate",
                "description": "Climatological baseline estimate."
            }
        }


@app.route("/api/real-weather", methods=["GET"])
def get_real_weather():
    station_key = request.args.get("station", "VABB_MUMBAI")
    if station_key not in STATIONS:
        station_key = "VABB_MUMBAI"

    station_info = STATIONS[station_key]
    weather_data = fetch_real_weather(station_key, station_info["lat"], station_info["lon"])
    return jsonify({
        "status": "success",
        "station_key": station_key,
        "station": station_info,
        "weather": weather_data
    })


@app.route("/api/model-info", methods=["GET"])
def get_model_info():
    return jsonify({
        "status": "success",
        "feature_importances": ml_model.feature_importances,
        "classes": ["Low", "Moderate", "Elevated", "Severe"]
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")
    app.run(host=host, port=port, debug=debug)
