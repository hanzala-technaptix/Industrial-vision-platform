#!/usr/bin/env python
"""CEO demo 04 — Product counting."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from app.pipelines.product_counting import run

if __name__ == "__main__":
    raise SystemExit(run())
