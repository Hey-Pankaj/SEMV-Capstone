"""
वज्रSense (VajraSense) — Comprehensive System Test Suite
Validates the data pipeline, Fuzzy Inference System, Machine Learning classifier,
nowcasting extrapolation, and Flask API endpoints.
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from pipeline.weather_data import SCENARIOS, STATIONS, generate_grid_reflectivity, generate_lightning_strikes
from models.fuzzy_engine import FuzzyRiskEngine
from models.ml_classifier import ThunderstormMLModel
from models.storm_tracker import NowcastingEngine
from models.evaluation import get_benchmark_evaluation
from app.server import app


def test_weather_data():
    print("[1/5] Testing Weather Data & Scenario Generation...")
    assert "norwester" in SCENARIOS, "norwester scenario missing"
    assert "VECC_KOLKATA" in STATIONS, "Kolkata station missing"

    sc = SCENARIOS["norwester"]
    grid = generate_grid_reflectivity(22.57, 88.36, sc["storm_cells"], resolution=20)
    assert len(grid["points"]) == 400, "Grid points count mismatch"

    strikes = generate_lightning_strikes(sc["storm_cells"])
    assert isinstance(strikes, list), "Lightning strikes should be a list"
    print("  -> Weather data generation: PASSED")


def test_fuzzy_engine():
    print("[2/5] Testing Mamdani Fuzzy Risk Engine...")
    engine = FuzzyRiskEngine()
    res_severe = engine.evaluate(cape=3500, dbz=55, flash_rate=60, shear=22)
    assert res_severe["category"] in ["Elevated", "Severe"], f"Expected Severe, got {res_severe['category']}"
    assert res_severe["score"] > 60.0, f"Expected high score, got {res_severe['score']}"

    res_low = engine.evaluate(cape=300, dbz=10, flash_rate=0, shear=4)
    assert res_low["category"] == "Low", f"Expected Low, got {res_low['category']}"
    print(f"  -> Severe score: {res_severe['score']} ({res_severe['category']})")
    print(f"  -> Calm score: {res_low['score']} ({res_low['category']})")
    print("  -> Fuzzy inference engine: PASSED")


def test_ml_model():
    print("[3/5] Testing Machine Learning Model...")
    ml = ThunderstormMLModel()
    pred = ml.predict_risk({
        "radar_max_dbz": 58.0,
        "radar_mean_dbz": 38.0,
        "radar_vil": 42.0,
        "cloud_top_temp_c": -68.0,
        "lightning_count_10m": 45,
        "cape_j_kg": 3400.0,
        "cin_j_kg": 15.0,
        "lifted_index": -6.5,
        "shear_0_6km_ms": 22.0,
        "precipitable_water_mm": 54.0
    })
    assert pred["predicted_class"] in ["Elevated", "Severe"], f"Unexpected ML class: {pred['predicted_class']}"
    print(f"  -> ML Predicted Class: {pred['predicted_class']}, Risk Score: {pred['ml_risk_score']}")
    print("  -> ML model inference: PASSED")


def test_nowcaster():
    print("[4/5] Testing 0-2h Nowcasting Extrapolation Engine...")
    fuzzy = FuzzyRiskEngine()
    ml = ThunderstormMLModel()
    engine = NowcastingEngine(fuzzy, ml)
    nowcast = engine.generate_nowcast(SCENARIOS["norwester"], STATIONS["VECC_KOLKATA"])
    assert len(nowcast["projections"]) == 3, "Expected 3 horizons (0-30m, 30-60m, 60-120m)"
    print(f"  -> Horizons verified: {[h['label'] for h in nowcast['projections']]}")
    print("  -> Nowcasting engine: PASSED")


def test_flask_endpoints():
    print("[5/5] Testing Flask API Endpoints...")
    client = app.test_client()

    res_index = client.get("/")
    assert res_index.status_code == 200, "Index page returned non-200"

    res_stations = client.get("/api/stations")
    assert res_stations.status_code == 200 and res_stations.json["status"] == "success"

    res_scenarios = client.get("/api/scenarios")
    assert res_scenarios.status_code == 200 and res_scenarios.json["status"] == "success"

    res_nowcast = client.get("/api/nowcast?scenario=norwester&minutes=30")
    assert res_nowcast.status_code == 200 and res_nowcast.json["status"] == "success"

    res_eval = client.get("/api/evaluation")
    assert res_eval.status_code == 200 and res_eval.json["status"] == "success"

    res_weather = client.get("/api/real-weather?station=VABB_MUMBAI")
    assert res_weather.status_code == 200 and res_weather.json["status"] == "success"
    assert "weather" in res_weather.json and "temperature_c" in res_weather.json["weather"]

    print("  -> Flask endpoints: ALL PASSED")


if __name__ == "__main__":
    print("⚡ Starting वज्रSense Verification Suite...\n")
    test_weather_data()
    test_fuzzy_engine()
    test_ml_model()
    test_nowcaster()
    test_flask_endpoints()
    print("\n🎉 ALL TESTS PASSED SUCCESSFULLY! वज्रSense is fully functional.")
