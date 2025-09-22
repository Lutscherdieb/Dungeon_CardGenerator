# api/static_paths.py
import os
from pathlib import Path

# Project root = repo root (the folder containing generate_card.py)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# All API-rendered outputs go into outputs/api/
OUTPUTS_API_DIR = PROJECT_ROOT / "outputs" / "api"

# Background uploads
UPLOAD_BG_DIR = PROJECT_ROOT / "backgrounds" / "uploads"

# Ensure they exist at import time
os.makedirs(OUTPUTS_API_DIR, exist_ok=True)
os.makedirs(UPLOAD_BG_DIR, exist_ok=True)
