"""Resolve camera / file sources."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Union


Source = Union[int, str, Path]


def normalize_source(source: Source) -> Source:
    s = str(source)
    if s.isdigit():
        return int(s)
    return str(Path(s).expanduser().resolve())


def open_capture(source: Source):
    import cv2

    src = normalize_source(source)
    return cv2.VideoCapture(src)
