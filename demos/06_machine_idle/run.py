#!/usr/bin/env python
"""CEO demo 06 — Machine idle detection."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.use_cases.machine_idle import run

if __name__ == "__main__":
    raise SystemExit(run())
