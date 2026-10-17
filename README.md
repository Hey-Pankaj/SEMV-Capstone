# वज्रSense (VajraSense) — AI/ML Thunderstorm & Lightning Nowcasting System (0–2h)

**वज्रSense** is an academic capstone AI/ML and soft-computing atmospheric nowcasting system engineered to estimate localized thunderstorm initiation, convective severity, and lightning strike hazards across the critical **0–2 hour tactical window** ($0–30\text{ min}$, $30–60\text{ min}$, and $60–120\text{ min}$ horizons) and visualize actionable emergency risk through a modern geospatial decision dashboard.

---

## ⚡ Core Highlights & Capabilities

1. **Multi-Source Atmospheric Data Integration**:
   - **Doppler Weather Radar**: Reflectivity ($Z$ in dBZ) and Vertically Integrated Liquid (VIL in $\text{kg/m}^2$).
   - **Geostationary Satellite**: Cloud-Top Brightness Temperature (IR $10.8\ \mu\text{m}$ in $^\circ\text{C}$).
   - **Ground Lightning Detection**: Discrete strike coordinates, stroke polarity ($\text{CG}^-$, $\text{CG}^+$, $\text{IC}$), and flash rates.
   - **NWP / Thermodynamic Soundings**: CAPE ($\text{J/kg}$), Lifted Index ($^\circ\text{C}$), 0–6 km Bulk Wind Shear ($\text{m/s}$), and Precipitable Water ($\text{mm}$).

2. **Interpretable Soft Computing (Mamdani Fuzzy Logic)**:
   - Evaluates multi-dimensional atmospheric uncertainty into a **0–100 Lightning Hazard Index** using transparent linguistic rules and Centroid defuzzification.
   - Provides explainable rule firing traces (e.g., *Rule 1: High CAPE + Severe Echo + Intense Flashes $\rightarrow$ Severe*).

3. **Machine Learning Convective Classifier**:
   - Supervised Random Forest ensemble model predicting thunderstorm initiation and categorical severity (*Low*, *Moderate*, *Elevated*, *Severe*).
   - Generates probabilistic confidence distributions and feature importance metrics.

4. **Multi-Horizon Extrapolation & Centroid Tracking**:
   - Kinematic storm cell velocity ($v_{\text{km/h}}$) and heading ($\theta_{\text{deg}}$) nowcaster projecting future cell positions and expanding cones of spatial uncertainty for:
     - **0–30 min**: Immediate Tactical Hazard
     - **30–60 min**: Short-Term Extrapolation
     - **60–120 min**: Strategic Convective Trend

5. **Meteorological Skill Verification**:
   - Quantitative evaluation based on standard $2\times2$ contingency tables: Probability of Detection (POD), False Alarm Ratio (FAR), Critical Success Index (CSI), and Heidke Skill Score (HSS) benchmarked against a classical persistence baseline.

6. **Modern Decision Dashboard**:
   - Dark-mode interface with CartoDB Leaflet GIS mapping.
   - Interactive timeline scrubber and auto-play animation ($0\text{m} \rightarrow 30\text{m} \rightarrow 60\text{m} \rightarrow 120\text{m}$).
   - Four pre-configured convective scenarios (*Kalbaishakhi Supercell*, *Afternoon Pulse Storm*, *Monsoon Convective Band*, *Fair Weather*).
   - Six major Indian radar monitoring stations (*Kolkata, Delhi-NCR, Mumbai, Bengaluru, Bhubaneswar, Guwahati*).
   - Built-in Fuzzy Logic What-If Simulator and Verification metrics modal.

---

## 📂 Project Structure

```text
SEMV-Capstone/
├── app/
│   ├── __init__.py
│   └── server.py                 # Flask REST API & Web Server
├── models/
│   ├── __init__.py
│   ├── fuzzy_engine.py           # Mamdani Fuzzy Inference System (FIS)
│   ├── ml_classifier.py          # Random Forest severity model & training
│   ├── storm_tracker.py          # Kinematic nowcasting & centroid tracking
│   ├── evaluation.py             # Meteorological verification (POD, FAR, CSI)
│   └── vajra_rf_model.joblib     # Serialized trained model & feature weights
├── pipeline/
│   ├── __init__.py
│   └── weather_data.py           # Atmospheric data generator & realistic scenarios
├── static/
│   ├── css/
│   │   └── styles.css            # Dark glassmorphic design system
│   └── js/
│       ├── map.js                # Leaflet GIS layer engine & radar color scales
│       └── app.js                # Dashboard controller, scrubbing, and audio alerts
├── templates/
│   └── index.html                # Main semantic decision dashboard
├── styles.css                    # Root stylesheet copy for direct IDE inspection
├── requirements.txt              # Core Python dependencies
├── run.py                        # One-command server startup
├── test_system.py                # Automated verification test suite
└── README.md                     # Technical project documentation
```

---

## 🚀 Quick Start Guide

### 1. Install Dependencies (if not already installed)
```bash
pip install -r requirements.txt
```
*(Flask, NumPy, Pandas, Scikit-Learn, Joblib, and SciPy)*

### 2. Run the Verification Suite
To verify that all modules (pipeline, fuzzy FIS, ML classifier, nowcaster, and Flask endpoints) are operational:
```bash
python test_system.py
```

### 3. Launch the Dashboard
Start the local server:
```bash
python run.py
```
Open your web browser and navigate to:
```text
http://127.0.0.1:5000
```

---

## 🧮 Mathematical & Scientific Formulation

### 1. Mamdani Fuzzy Logic Risk Inference
The Lightning Hazard Index ($I_L \in [0, 100]$) is computed through centroid defuzzification:

$$I_L = \frac{\int_0^{100} x \cdot \mu_{\text{agg}}(x)\,dx}{\int_0^{100} \mu_{\text{agg}}(x)\,dx}$$

Where:
- $\mu_{\text{agg}}(x) = \max_{r} \left[ \min\left(w_r, \mu_{C_r}(x)\right) \right]$
- $w_r$ is the degree of fulfillment of rule $r$.

### 2. Meteorological Contingency Metrics
Given Hits ($A$), False Alarms ($B$), Misses ($C$), and Correct Negatives ($D$):

$$\text{POD (Probability of Detection)} = \frac{A}{A + C}$$

$$\text{FAR (False Alarm Ratio)} = \frac{B}{A + B}$$

$$\text{CSI (Critical Success Index)} = \frac{A}{A + B + C}$$

$$\text{HSS (Heidke Skill Score)} = \frac{2(AD - BC)}{(A + C)(C + D) + (A + B)(B + D)}$$

---

## ⚠️ Official Advisory Notice
**वज्रSense** is an academic research prototype designed to explore multi-sensor data fusion, soft computing, and machine learning for localized nowcasting. It is intended to **complement**—not replace—official weather advisories and warnings issued by the India Meteorological Department (IMD) and Damini Lightning Services.
