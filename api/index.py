import os
import sys

# Ensure root directory is on Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app

# Vercel serverless ASGI entrypoint
app = app

