"""
वज्रSense (VajraSense) — Machine Learning Risk Classification Model
Trains and executes an ensemble Random Forest classifier on multi-sensor atmospheric features
to predict thunderstorm severity and probability of initiation across lead times.
"""

import os
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score
from typing import Dict, Any, Tuple


MODEL_PATH = os.path.join(os.path.dirname(__file__), "vajra_rf_model.joblib")

FEATURE_NAMES = [
    "radar_max_dbz",
    "radar_mean_dbz",
    "radar_vil",
    "cloud_top_temp_c",
    "lightning_count_10m",
    "cape_j_kg",
    "cin_j_kg",
    "lifted_index",
    "shear_0_6km_ms",
    "precipitable_water_mm"
]

SEVERITY_CLASSES = ["Low", "Moderate", "Elevated", "Severe"]


def generate_training_dataset(n_samples: int = 1800, random_seed: int = 42) -> Tuple[pd.DataFrame, pd.Series]:
    np.random.seed(random_seed)

    cape = np.random.uniform(200, 4800, n_samples)
    cin = np.random.uniform(5, 220, n_samples)
    shear = np.random.uniform(4, 32, n_samples)
    pw = np.random.uniform(20, 75, n_samples)
    lifted_index = 4.0 - (cape / 750.0) + np.random.normal(0, 1.0, n_samples)

    convective_potential = (cape / 4000.0) * 0.45 + (shear / 30.0) * 0.25 + (pw / 70.0) * 0.15 - (cin / 200.0) * 0.35
    convective_potential = np.clip(convective_potential + np.random.normal(0, 0.1, n_samples), 0, 1)

    radar_max_dbz = np.clip(10.0 + convective_potential * 55.0 + np.random.normal(0, 4.0, n_samples), 5, 68)
    radar_mean_dbz = np.clip(radar_max_dbz * 0.65 + np.random.normal(0, 3.0, n_samples), 0, 50)
    radar_vil = np.clip((radar_max_dbz - 25.0) * 1.3 + np.random.normal(0, 4.0, n_samples), 0, 65)
    cloud_top_temp_c = np.clip(10.0 - convective_potential * 85.0 + np.random.normal(0, 5.0, n_samples), -82, 15)

    flash_lambda = np.maximum(0, (radar_max_dbz - 35.0) * 1.8 + (cape / 1200.0) * 4.0)
    lightning_count = np.random.poisson(flash_lambda)

    df = pd.DataFrame({
        "radar_max_dbz": radar_max_dbz,
        "radar_mean_dbz": radar_mean_dbz,
        "radar_vil": radar_vil,
        "cloud_top_temp_c": cloud_top_temp_c,
        "lightning_count_10m": lightning_count,
        "cape_j_kg": cape,
        "cin_j_kg": cin,
        "lifted_index": lifted_index,
        "shear_0_6km_ms": shear,
        "precipitable_water_mm": pw
    })

    labels = []
    for idx, row in df.iterrows():
        if row["radar_max_dbz"] >= 52 or (row["cape_j_kg"] >= 3200 and row["lightning_count_10m"] >= 30):
            score = 3
        elif row["radar_max_dbz"] >= 42 or (row["cape_j_kg"] >= 2000 and row["lightning_count_10m"] >= 12):
            score = 2
        elif row["radar_max_dbz"] >= 28 or row["cape_j_kg"] >= 1200 or row["lightning_count_10m"] >= 3:
            score = 1
        else:
            score = 0
        labels.append(score)

    y = pd.Series(labels, name="severity_class")
    return df, y


class ThunderstormMLModel:
    def __init__(self):
        self.model: RandomForestClassifier = None
        self.feature_names = FEATURE_NAMES
        self.feature_importances: Dict[str, float] = {}
        self._load_or_train()

    def _load_or_train(self):
        if os.path.exists(MODEL_PATH):
            try:
                data = joblib.load(MODEL_PATH)
                self.model = data["model"]
                self.feature_importances = data["feature_importances"]
                return
            except Exception:
                pass
        self.train_and_save()

    def train_and_save(self) -> Dict[str, Any]:
        X, y = generate_training_dataset(n_samples=2200)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42, stratify=y)

        clf = RandomForestClassifier(
            n_estimators=100,
            max_depth=12,
            min_samples_split=4,
            random_state=42,
            n_jobs=-1
        )
        clf.fit(X_train, y_train)

        y_pred = clf.predict(X_test)
        acc = accuracy_score(y_test, y_pred)

        importances = dict(zip(FEATURE_NAMES, [round(float(v), 4) for v in clf.feature_importances_]))
        sorted_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

        self.model = clf
        self.feature_importances = sorted_importances

        try:
            joblib.dump({
                "model": self.model,
                "feature_importances": self.feature_importances,
                "accuracy": acc
            }, MODEL_PATH)
        except Exception:
            pass

        return {
            "accuracy": round(acc, 4),
            "feature_importances": sorted_importances,
            "samples_trained": len(X_train),
            "samples_tested": len(X_test)
        }

    def predict_risk(self, feature_dict: Dict[str, float]) -> Dict[str, Any]:
        row = [feature_dict.get(feat, 0.0) for feat in FEATURE_NAMES]
        X_df = pd.DataFrame([row], columns=FEATURE_NAMES)
        probs = self.model.predict_proba(X_df)[0]
        class_idx = int(np.argmax(probs))
        pred_label = SEVERITY_CLASSES[class_idx]

        class_weights = [10.0, 40.0, 70.0, 95.0]
        ml_score = float(np.sum(probs * class_weights))

        return {
            "predicted_class": pred_label,
            "class_index": class_idx,
            "probabilities": {SEVERITY_CLASSES[i]: round(float(probs[i]), 3) for i in range(len(probs))},
            "ml_risk_score": round(ml_score, 1),
            "top_features": list(self.feature_importances.keys())[:5]
        }
