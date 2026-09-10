"""Development entry point. Runs FastAPI via uvicorn."""
from __future__ import annotations

import uvicorn

from app.core.config import API_HOST, API_PORT, LOG_LEVEL


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=API_HOST,
        port=API_PORT,
        log_level=LOG_LEVEL.lower(),
        reload=False,
    )
