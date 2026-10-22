"""
वज्रSense (VajraSense) — Soft Computing: Fuzzy Logic Risk Inference System (FIS)
Implements a Mamdani Fuzzy Inference System for interpretable lightning and thunderstorm
hazard assessment combining thermodynamic instability, radar echoes, and lightning counts.
"""

from typing import Dict, List, Tuple, Any
import numpy as np


class FuzzySet:
    """Represents a trapezoidal / triangular fuzzy membership function."""
    def __init__(self, name: str, a: float, b: float, c: float, d: float):
        self.name = name
        self.a = float(a)
        self.b = float(b)
        self.c = float(c)
        self.d = float(d)

    def membership(self, x: float) -> float:
        """Evaluates degree of membership mu(x) in [0, 1]."""
        if x <= self.a or x >= self.d:
            return 0.0
        elif self.b <= x <= self.c:
            return 1.0
        elif self.a < x < self.b:
            if self.b == self.a:
                return 1.0
            return (x - self.a) / (self.b - self.a)
        elif self.c < x < self.d:
            if self.d == self.c:
                return 1.0
            return (self.d - x) / (self.d - self.c)
        return 0.0


class LinguisticVariable:
    """A collection of fuzzy sets spanning a continuous physical dimension."""
    def __init__(self, name: str, unit: str, sets: Dict[str, Tuple[float, float, float, float]]):
        self.name = name
        self.unit = unit
        self.fuzzy_sets = {sname: FuzzySet(sname, *coords) for sname, coords in sets.items()}

    def fuzzify(self, value: float) -> Dict[str, float]:
        """Returns membership degree for each fuzzy set."""
        return {sname: fset.membership(value) for sname, fset in self.fuzzy_sets.items()}


class FuzzyRiskEngine:
    """
    Mamdani Fuzzy Inference System for Thunderstorm & Lightning Risk.
    Inputs:
      - CAPE (J/kg): Low, Moderate, High, Extreme
      - Reflectivity (dBZ): Clear/Light, Moderate, Severe, Extreme
      - Flash Rate (flashes/10min): Rare, Frequent, Intense
      - Wind Shear (m/s): Weak, Moderate, Strong
    Output:
      - Lightning Hazard Index (0 to 100)
    """

    def __init__(self):
        self.cape_var = LinguisticVariable("CAPE", "J/kg", {
            "LOW": (0, 0, 600, 1200),
            "MODERATE": (800, 1400, 2000, 2600),
            "HIGH": (2200, 2800, 3600, 4200),
            "EXTREME": (3400, 4000, 6000, 6000)
        })

        self.dbz_var = LinguisticVariable("Reflectivity", "dBZ", {
            "LIGHT": (0, 0, 15, 28),
            "MODERATE": (24, 32, 40, 46),
            "SEVERE": (42, 48, 54, 60),
            "EXTREME": (52, 58, 80, 80)
        })

        self.flash_var = LinguisticVariable("FlashRate", "flashes/10min", {
            "NONE_RARE": (0, 0, 2, 8),
            "MODERATE": (5, 12, 25, 38),
            "INTENSE": (30, 45, 150, 150)
        })

        self.shear_var = LinguisticVariable("WindShear", "m/s", {
            "WEAK": (0, 0, 6, 12),
            "MODERATE": (8, 14, 18, 24),
            "STRONG": (18, 25, 45, 45)
        })

        self.risk_sets = {
            "LOW": FuzzySet("LOW", 0, 0, 15, 30),
            "MODERATE": FuzzySet("MODERATE", 20, 35, 45, 60),
            "ELEVATED": FuzzySet("ELEVATED", 50, 62, 75, 85),
            "SEVERE": FuzzySet("SEVERE", 75, 88, 100, 100)
        }

    def evaluate(self, cape: float, dbz: float, flash_rate: float, shear: float = 14.0) -> Dict[str, Any]:
        cape_m = self.cape_var.fuzzify(cape)
        dbz_m = self.dbz_var.fuzzify(dbz)
        flash_m = self.flash_var.fuzzify(flash_rate)
        shear_m = self.shear_var.fuzzify(shear)

        rules = []

        w1 = min(max(cape_m["HIGH"], cape_m["EXTREME"]), max(dbz_m["SEVERE"], dbz_m["EXTREME"]), flash_m["INTENSE"])
        rules.append({"id": 1, "rule": "CAPE (High/Ext) & dBZ (Sev/Ext) & Flashes (Intense)", "consequent": "SEVERE", "weight": w1})

        w2 = min(max(cape_m["HIGH"], cape_m["EXTREME"]), dbz_m["SEVERE"])
        rules.append({"id": 2, "rule": "CAPE (High/Ext) & dBZ (Severe)", "consequent": "ELEVATED", "weight": w2})

        w3 = flash_m["INTENSE"]
        rules.append({"id": 3, "rule": "Flash Rate is Intense (>30/10min)", "consequent": "SEVERE", "weight": w3})

        w4 = min(cape_m["MODERATE"], dbz_m["MODERATE"], max(flash_m["NONE_RARE"], flash_m["MODERATE"]))
        rules.append({"id": 4, "rule": "CAPE (Mod) & dBZ (Mod) & Flashes (Mod)", "consequent": "MODERATE", "weight": w4})

        w5 = min(max(cape_m["HIGH"], cape_m["EXTREME"]), dbz_m["LIGHT"])
        rules.append({"id": 5, "rule": "CAPE (High) & Low Radar Echo (Latent Initiation Risk)", "consequent": "MODERATE", "weight": w5 * 0.7})

        w6 = min(shear_m["STRONG"], max(dbz_m["SEVERE"], dbz_m["EXTREME"]))
        rules.append({"id": 6, "rule": "Deep Wind Shear (Strong) & Severe Echo", "consequent": "SEVERE", "weight": w6})

        w7 = min(cape_m["LOW"], dbz_m["LIGHT"], flash_m["NONE_RARE"])
        rules.append({"id": 7, "rule": "Low Instability & Light Echo & No Flashes", "consequent": "LOW", "weight": w7})

        w8 = cape_m["LOW"] * dbz_m["LIGHT"]
        rules.append({"id": 8, "rule": "Atmospheric Inversion / Stable Cap", "consequent": "LOW", "weight": w8})

        x_vals = np.linspace(0, 100, 201)
        aggregated_envelope = np.zeros_like(x_vals)

        for r in rules:
            weight = r["weight"]
            if weight > 0:
                c_set = self.risk_sets[r["consequent"]]
                for i, x in enumerate(x_vals):
                    mu = min(weight, c_set.membership(x))
                    if mu > aggregated_envelope[i]:
                        aggregated_envelope[i] = mu

        sum_mu = np.sum(aggregated_envelope)
        if sum_mu > 1e-6:
            crisp_score = float(np.sum(x_vals * aggregated_envelope) / sum_mu)
        else:
            crisp_score = 10.0

        if crisp_score >= 70.0:
            category = "Severe"
            color = "#ef4444"
            alert_code = "RED_WARNING"
        elif crisp_score >= 50.0:
            category = "Elevated"
            color = "#f97316"
            alert_code = "ORANGE_ALERT"
        elif crisp_score >= 30.0:
            category = "Moderate"
            color = "#eab308"
            alert_code = "YELLOW_WATCH"
        else:
            category = "Low"
            color = "#22c55e"
            alert_code = "GREEN_NORMAL"

        active_rules = [r for r in rules if r["weight"] >= 0.05]
        active_rules.sort(key=lambda item: item["weight"], reverse=True)

        return {
            "score": round(crisp_score, 1),
            "category": category,
            "color": color,
            "alert_code": alert_code,
            "active_rules": active_rules[:4],
            "memberships": {
                "cape": {k: round(v, 2) for k, v in cape_m.items() if v > 0},
                "dbz": {k: round(v, 2) for k, v in dbz_m.items() if v > 0},
                "flash": {k: round(v, 2) for k, v in flash_m.items() if v > 0}
            }
        }
