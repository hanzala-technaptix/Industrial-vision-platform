#!/usr/bin/env python
"""CEO demo 02 — Person / vehicle detection."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.use_cases.person_vehicle import run

if __name__ == "__main__":
    raise SystemExit(run())
