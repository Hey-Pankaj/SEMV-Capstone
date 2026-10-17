"""
वज्रSense (VajraSense) — Launcher Script
Run this script to launch the local nowcasting decision dashboard.
Usage: python run.py
"""

import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app.server import app

if __name__ == "__main__":
    print("\n" + "=" * 65)
    print("⚡ वज्रSense (VajraSense) — Severe Weather Nowcasting System (0-2h)")
    print("=" * 65)
    print("Initializing Mamdani Fuzzy Inference Engine...")
    print("Loading Pre-trained Random Forest Convective Classifier...")
    print("Calibrating 0-30m, 30-60m, 60-120m Multi-Horizon Engine...")
    print("\n🌐 Dashboard running live at: http://127.0.0.1:5000")
    print("Press CTRL+C to terminate.")
    print("=" * 65 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=True)
