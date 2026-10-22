"""
वज्रSense (VajraSense) — Production WSGI Server Entrypoint
Exposes the WSGI application callable `app` and `application` for production servers:
Gunicorn (Linux/Docker/Cloud), Waitress (Windows/Cross-platform), Render, Railway, AWS, etc.
"""

import os
import sys

# Ensure project root directory is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load environment variables if .env file exists
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

from app.server import app

# Standard WSGI aliases for diverse deployment orchestrators
application = app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    host = os.environ.get("HOST", "0.0.0.0")
    debug = os.environ.get("FLASK_DEBUG", "0").lower() in ("1", "true")

    # In production on Windows or when explicitly requested, use Waitress
    if os.environ.get("USE_WAITRESS", "0").lower() in ("1", "true"):
        try:
            from waitress import serve
            print(f"🚀 [WSGI] Serving via Waitress production server on http://{host}:{port}")
            serve(app, host=host, port=port)
        except ImportError:
            app.run(host=host, port=port, debug=debug)
    else:
        app.run(host=host, port=port, debug=debug)
