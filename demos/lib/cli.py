"""CLI helpers for CEO demos."""
from __future__ import annotations

_gui_ok: bool | None = None


def gui_available() -> bool:
    global _gui_ok
    if _gui_ok is not None:
        return _gui_ok
    try:
        import cv2

        cv2.namedWindow("__gui_probe__", cv2.WINDOW_NORMAL)
        cv2.destroyWindow("__gui_probe__")
        _gui_ok = True
    except Exception:
        _gui_ok = False
    return _gui_ok


def show_frame(window: str, frame, *, enabled: bool) -> bool:
    if not enabled:
        return False
    if not gui_available():
        print(
            "[demo] No OpenCV GUI. Use --out path.mp4 or: pip uninstall opencv-python-headless"
        )
        return False
    import cv2

    cv2.imshow(window, frame)
    return True


def show_alert_window(window: str, messages: list[str], *, enabled: bool) -> bool:
    if not enabled or not gui_available():
        return False
    import cv2

    from app.rendering.overlays import render_alert_panel

    panel = render_alert_panel(messages)
    if panel is None:
        try:
            cv2.destroyWindow(window)
        except cv2.error:
            pass
        return False
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.imshow(window, panel)
    return True


def wait_key(delay_ms: int = 1) -> int:
    import cv2

    return cv2.waitKey(delay_ms) & 0xFF


def destroy_windows(*, enabled: bool) -> None:
    if enabled and gui_available():
        import cv2

        cv2.destroyAllWindows()
