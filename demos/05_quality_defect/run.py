#!/usr/bin/env python
"""CEO demo 05 — Quality defect (requires local sample images)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.use_cases.quality_defect import run

if __name__ == "__main__":
    raise SystemExit(run())
