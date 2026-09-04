"""Simple logging helper."""
from __future__ import annotations

import logging

from app.core.config import LOG_LEVEL

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        logging.basicConfig(
            level=getattr(logging, LOG_LEVEL, logging.INFO),
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )
        _configured = True
    return logging.getLogger(name)
