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

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment variables if .env file is present
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

from app.server import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "127.0.0.1" if sys.platform == "win32" and "PORT" not in os.environ else "0.0.0.0")
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")

    print("\n" + "=" * 65)
    print("⚡ वज्रSense (VajraSense) — Severe Weather Nowcasting System (0-2h)")
    print("=" * 65)
    print("Initializing Mamdani Fuzzy Inference Engine...")
    print("Loading Pre-trained Random Forest Convective Classifier...")
    print("Calibrating 0-30m, 30-60m, 60-120m Multi-Horizon Engine...")
    print(f"\n🌐 Dashboard running at: http://{host}:{port}")
    print("Press CTRL+C to terminate.")
    print("=" * 65 + "\n")

    if os.environ.get("USE_WAITRESS", "0").lower() in ("1", "true"):
        try:
            from waitress import serve
            print(f"🚀 Running under Waitress Production WSGI server...")
            serve(app, host=host, port=port)
        except ImportError:
            app.run(host=host, port=port, debug=debug)
    else:
        app.run(host=host, port=port, debug=debug)
