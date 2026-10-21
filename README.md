# वज्रSense (VajraSense) ⚡
### Meteorological Nowcasting and Atmospheric Diagnostic Pipeline for Mumbai Thunderstorms & Lightning Risk

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Hardware](https://img.shields.io/badge/Hardware-100%25%20CPU%20Friendly%20(No%20GPU%20Required)-success.svg)](#hardware-requirements)
[![Data Source](https://img.shields.io/badge/Data-Open--Meteo%20(ERA5%20%2B%20GFS)-orange.svg)](https://open-meteo.com/)
[![Scientific Rigor](https://img.shields.io/badge/Ground--Truth-Validated%20Atmospheric%20Physics-brightgreen.svg)](#scientific-integrity--ground-truth-handling)

---

## 1. Project Overview

**वज्रSense (VajraSense)** is a domain-specific meteorological nowcasting and atmospheric diagnostic framework designed specifically for the unique convective dynamics of the **Mumbai metropolitan region** (19.0760° N, 72.8777° E).

### Mumbai Coastal Convective Regime
Thunderstorm nowcasting in Mumbai presents distinctive meteorological challenges:
- **Sea-Breeze Front & Western Ghats Interaction:** During the pre-monsoon (May–June) and post-monsoon (October–November) transition windows, strong solar insolation destabilizes the marine boundary layer. Afternoon sea-breeze fronts collide with inland topography, triggering explosive vertical updrafts.
- **High Convective Available Potential Energy (CAPE):** Mumbai pre-monsoon convective outbreaks frequently record CAPE exceeding $2,000 \text{ J/kg}$ and Lifted Index below $-5^\circ\text{C}$, producing severe squall lines, high cloud-to-ground (CG) lightning discharge rates, and localized microbursts.
- **Monsoon vs Convective Showers:** While the Southwest Monsoon (late June–September) delivers large cumulative precipitation, convective lightning density is significantly higher during the pre-monsoon and post-monsoon months.

**वज्रSense** establishes an end-to-end, reproducible pipeline to acquire historical observations, validate physical boundaries, compute derived thermodynamic proxies, render exploratory meteorological visual diagnostics, and prepare leak-free machine learning nowcasting models.

---

## 2. Scientific Integrity & Ground-Truth Handling

> [!IMPORTANT]
> **No Synthetic or Fabricated Lightning Labels:**
> In rigorous meteorological research, generating random synthetic binary labels or claiming artificial 99% accuracy undermines real-world safety.
> **वज्रSense strictly avoids fake labels.**

Instead, ground-truth convective storm regimes are established using validated meteorological standards:
1. **WMO Weather Interpretation Standards:** Recorded observations matching WMO codes `80–82` (convective rain showers) and `95–99` (thunderstorms with or without hail).
2. **Thermodynamic Instability Criteria:** Validated atmospheric sounding thresholds from numerical reanalysis:
   $$\text{CAPE} \ge 1,000 \text{ J/kg} \quad \text{AND} \quad \text{Lifted Index (LI)} \le -2.0^\circ\text{C}$$
3. **Kinematic Squall Thresholds:** Heavy precipitation ($\ge 5.0 \text{ mm/h}$) coinciding with sudden wind gusts ($\ge 35 \text{ km/h}$).

### Ground-Truth Ingestion Roadmap
For institutions with access to ground-based lightning sensor data (such as the **Indian Institute of Tropical Meteorology (IITM) Lightning Detection Network** or the **IMD DAMINI** system), वज्रSense provides a direct plug-in interface in `vajrasense/feature_engineering.py` to ingest timestamped lightning flash logs without altering downstream ML pipelines.

---

## 3. Architecture & Modular Structure

```
SEMV-Capstone/
├── data/
│   ├── raw/                  # Downloaded raw CSV data from Open-Meteo API
│   │   └── mumbai_weather_raw_2022_2024.csv
│   └── processed/            # Cleaned & feature-engineered datasets
│       ├── mumbai_weather_clean.csv
│       └── mumbai_weather_features.csv
├── models_saved/             # Serialized scikit-learn nowcasting pipelines (.joblib)
├── reports/
│   └── figures/              # Generated high-resolution atmospheric EDA figures
│       ├── diurnal_convective_cycle.png
│       ├── seasonal_monsoon_profile.png
│       ├── thermodynamic_phase_space.png
│       ├── pressure_wind_storm_signature.png
│       └── feature_correlation_heatmap.png
├── vajrasense/               # Core Python Package
│   ├── __init__.py           # Package initialization
│   ├── config.py             # Spatial coordinates, API endpoints, physical bounds, thresholds
│   ├── ingestion.py          # Resilient Open-Meteo client (retry, rate-limiting, yearly chunking)
│   ├── preprocessing.py      # Quality assurance, continuous hourly grid, physical anomaly clamping
│   ├── feature_engineering.py# Meteorological features (Theta-e proxy, Dew Point Depression, Shear)
│   ├── visualization.py      # Publication-ready Matplotlib atmospheric diagnostic plots
│   └── pipeline.py           # Scikit-learn CPU-optimized nowcasting pipeline & metrics
├── tests/
│   ├── __init__.py
│   └── test_pipeline.py      # Automated unit & integration test suite
├── main.py                   # Unified CLI orchestrator
├── requirements.txt          # Python dependencies (CPU-only optimized)
├── .gitignore                # Git ignore for data cache, pycache, and logs
└── README.md                 # Complete documentation & usage guide
```

---

## 4. Hardware & Dependencies

**100% CPU Friendly — No GPU Required.**
All calculations, feature transformations, and scikit-learn models run within seconds on any standard multi-core laptop CPU.

### Core Stack
- **Python:** 3.10+
- **Pandas (>=2.0.0):** Time-series alignment, rolling statistics, and vectorized manipulation.
- **NumPy (>=1.24.0):** Trigonometric seasonal/diurnal encoding and mathematical operations.
- **Scikit-Learn (>=1.3.0):** Preprocessing transformers (`RobustScaler`, `SimpleImputer`) and CPU classifier (`HistGradientBoostingClassifier`).
- **Matplotlib (>=3.7.0):** Non-interactive (`Agg`) high-resolution atmospheric plotting.
- **Requests (>=2.28.0):** Resilient HTTP ingestion client with exponential backoff.

---

## 5. Quickstart & Installation

### Step 1: Clone the Repository & Enter Workspace
```bash
cd SEMV-Capstone
```

### Step 2: Set Up Virtual Environment (Optional but Recommended)
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Run the Test Suite
Verify that all configurations, cleaning modules, and feature transformations are functioning properly:
```bash
python -m unittest tests/test_pipeline.py
```

---

## 6. Usage Guide (CLI Execution)

Run the full end-to-end pipeline (downloads data, cleans, engineers features, generates visual reports, and trains the CPU nowcasting baseline):
```bash
python main.py --run-all
```

### Modular Step-by-Step Commands

1. **Download Historical Weather Data (Open-Meteo API):**
   ```bash
   python main.py --download --start-date 2023-01-01 --end-date 2024-12-31
   ```

2. **Clean & Validate Physical Boundaries:**
   ```bash
   python main.py --clean
   ```

3. **Compute Meteorological Indices & Tendencies:**
   ```bash
   python main.py --features
   ```

4. **Generate Exploratory Visualizations:**
   ```bash
   python main.py --visualize
   ```

5. **Train Baseline Nowcasting Model on CPU:**
   ```bash
   python main.py --train --model-type hist_gb --target target_nowcast_1h
   ```

---

## 7. Derived Meteorological Features

| Feature Name | Formulation / Source | Physical Significance in Nowcasting |
| :--- | :--- | :--- |
| `dew_point_depression` | $T_{2m} - T_{dew}$ | Near-surface saturation deficit; low depression + high heat indicates high buoyancy. |
| `theta_e_proxy` | $\theta \exp\left(\frac{L_v q}{c_p T_K}\right)$ | Equivalent potential temperature; tracks moist static energy fueling deep updrafts. |
| `vertical_wind_shear` | $V_{100m} - V_{10m}$ | Kinematic shear; separates storm updrafts from downdrafts to maintain organized squalls. |
| `pressure_tendency_1h` | $\Delta P_{1h} = P_t - P_{t-1}$ | Rapid barometric drops precede squall line arrival; sudden surge indicates mesohigh. |
| `temp_drop_1h` | $\Delta T_{1h} = T_t - T_{t-1}$ | Cold pool / thunderstorm outflow boundary detection from active downdrafts. |
| `rolling_max_gust_3h` | $\max(V_{gust}, 3h)$ | Tracks antecedent turbulent kinetic energy in the boundary layer. |
| `hour_sin` / `hour_cos` | $\sin / \cos (2\pi \cdot \text{hour} / 24)$ | Captures Mumbai afternoon heating peak (14:00–19:00 IST). |
| `doy_sin` / `doy_cos` | $\sin / \cos (2\pi \cdot \text{doy} / 365.25)$ | Encodes seasonal progression (Pre-monsoon vs Monsoon vs Winter). |

---

## 8. Atmospheric Visual Diagnostics

All plots are generated automatically into `reports/figures/`:

1. **`diurnal_convective_cycle.png`**: Hourly mean CAPE with $\pm 0.5\sigma$ uncertainty envelope plotted against convective event frequency, showing peak destabilization in the late afternoon.
2. **`seasonal_monsoon_profile.png`**: Dual-panel monthly breakdown showing surface temperature, dew point, rainfall accumulation, and convective hours.
3. **`thermodynamic_phase_space.png`**: CAPE vs Lifted Index scatter plot color-coded by Dew Point Depression, delineating the severe convective risk envelope.
4. **`pressure_wind_storm_signature.png`**: 72-hour case study of a major Mumbai severe convective storm showing the barometric dip, gust surge, and cold-pool plunge.
5. **`feature_correlation_heatmap.png`**: Correlation matrix evaluating multi-parameter coupling with the 1-hour nowcast target.

---

## 9. Evaluation Metrics for Rare Convective Events

Standard classification accuracy can be misleading in severe weather prediction due to class imbalance (~5–15% event frequency). **वज्रSense** evaluates models using meteorological verification metrics:

- **Probability of Detection (POD / Recall):** $\frac{\text{TP}}{\text{TP} + \text{FN}}$ (fraction of actual storms warned in advance).
- **Critical Success Index (CSI / Threat Score):** $\frac{\text{TP}}{\text{TP} + \text{FP} + \text{FN}}$ (operational verification score balancing hits, misses, and false alarms).
- **False Alarm Ratio (FAR):** $\frac{\text{FP}}{\text{TP} + \text{FP}}$ (proportion of false warnings issued).
- **Precision-Recall AUC (PR-AUC):** Area under the Precision-Recall curve, reflecting performance on the minority convective class.
- **Brier Score:** Mean squared error of predicted probabilities against binary outcomes (lower is better; assesses calibration).

---

## 10. Future Roadmap

- [ ] **Doppler Weather Radar (DWR) Integration:** Ingest radial velocity and reflectivity ($Z$) scans from IMD Mumbai radar stations (Colaba & Veravali).
- [ ] **INSAT-3D / 3DR Satellite Feeds:** Ingest Brightness Temperature Difference (BTD) channels ($10.8\mu m - 12.0\mu m$) to detect rapidly growing cloud tops.
- [ ] **Ground Lightning Network:** Direct integration with IITM Pune lightning location network real-time flash CSV feeds.
- [ ] **Real-time SMS / Webhook Alerts:** Connect nowcasting pipeline to FastAPI / Flask endpoints to trigger automated civic alerts for Mumbai municipal wards.

---

## License & Attribution
Developed for educational, research, and meteorological capstone demonstration. Weather data provided through Open-Meteo under the Creative Commons Attribution 4.0 International License (CC BY 4.0).
