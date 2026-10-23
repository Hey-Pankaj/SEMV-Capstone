"""
वज्रSense (VajraSense) — Vercel Serverless Function Handler
Exposes the Flask WSGI application callable directly to Vercel's Python runtime.
"""

import os
import sys

# Ensure project root is in Python import search path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load environment variables if .env exists
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

from app.server import app

# Vercel entrypoint callable
application = app
app = app
