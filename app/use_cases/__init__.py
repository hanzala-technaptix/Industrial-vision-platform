"""Factory AI production use cases.

Each module exposes `run(argv: list[str] | None = None) -> int`.

The demos/ folder and the main FastAPI app both import from here — this is
the single source of truth for use-case wiring. No business logic lives in
demos/ anymore; only thin entry-point scripts.
"""
