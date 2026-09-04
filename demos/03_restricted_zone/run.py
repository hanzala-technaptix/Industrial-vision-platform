#!/usr/bin/env python
"""CEO demo 03 — Restricted zone presence."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.use_cases.restricted_zone import run

if __name__ == "__main__":
    raise SystemExit(run())
