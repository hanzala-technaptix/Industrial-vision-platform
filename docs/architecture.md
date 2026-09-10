# Architecture

Industrial Safety Vision is a factory CV POC: existing CCTV or MP4 in, detections and events out. Demos and the live API share one frame engine. Folder roles live in the [README](../README.md#architecture).

## Runtime path

```text
Camera / MP4
    → camera.VideoStream
    → FrameProcessor
         → detection / analytics
         → events (PPE)
         → rendering
    → demos/*/run.py    or    run.py FastAPI (/video_feed, /use_cases)
```

Weights on disk live in `models/`, not under `app/`. `app/models/` only loads them.

Live dashboard switches **01–08**. Quality (05) is inspection stills (MVTec AD, CC BY-NC-SA 4.0), shown as a slideshow on the same feed — not a live camera.

07 worker idle reuses the 03 clip. 08 downtime reuses the 06 clip. Do not copy those files.

Ignore leftover `app/detectors/`, `app/use_cases/`, and `app/alerts/`. Runtime uses `detection/`, `analytics/`, `pipelines/`, and `events/`.
