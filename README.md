# Industrial Vision AI

Factory computer-vision POC — **CEO demos first**, unified modular `app/` core.

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Place YOLO weights under `models/yolo/`. Test videos under `test-videos/`.

## Run CEO demos

```powershell
python demos/01_ppe/run.py --show
python demos/02_person_vehicle/run.py
python demos/03_restricted_zone/run.py
python demos/06_machine_idle/run.py
python demos/07_worker_idle/run.py
```

See [`demos/README.md`](demos/README.md) for the full list.

## Architecture

```text
app/
├── core/           config, logging, bbox, dependencies
├── camera/         stream, manager, source
├── detectors/      base, ppe, person, zone, machine_idle
├── events/         models, engine, repository
├── alerts/         ppe alerts, manager
├── pipeline/       frame_processor, runner, result
├── rendering/      detections, overlays, renderer
└── api/            routes, video, events

demos/
├── 01_ppe/run.py   thin CLI → demos/lib/video_runner.py → app/
└── lib/            cli.py, video_runner.py (shared demo runner)
```

Demos and the API server share **`FrameProcessor`** — same detectors, events, and alerts.

## API (optional)

```powershell
$env:VIDEO_SOURCE = "test-videos/ppe_construction_site.mp4"
python run.py
```

Endpoints: `/health`, `/events`, `/video_feed`

## Training

Offline scripts: `tools/training/`
