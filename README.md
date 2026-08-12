# Industrial Vision AI

Merged industrial computer-vision project (base: `industrial-vision-ai` + idle demos from `industrial-vision-idle`).

Capabilities in this repo:

- **PPE / mask detection** — live worker with tracking and events
- **FastAPI backend** + **React dashboard**
- **Machine idle** — optical flow demo (`scripts/demos/detect_machine_idle.py`)
- **Worker idle** — YOLO person + motion demo (`scripts/demos/detect_worker_idle.py`)
- **Zone presence** — polygon + person demo (`scripts/demos/detect_zone_presence.py`)

Food-industry PPE class labels from the legacy CV_bot project are kept at `data/ppe_food/classes.txt` (reference only; the old Flask/YOLOv5 app was not merged).

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies from the repo root:
   ```bash
   pip install -r requirements.txt
   ```
3. For the frontend:
   ```bash
   cd frontend && npm install
   ```

## Run — PPE detection (primary)

From `Cv_Pipeline/`:

```bash
cd Cv_Pipeline
python main.py
```

Events are written to `storage_data/events.json`.

## Run — Backend API + dashboard

```bash
# Terminal 1 — API (port 8001)
cd backend
uvicorn main:app --reload --port 8001

# Terminal 2 — React UI
cd frontend
npm run dev
```

## Run — Idle & presence demos

From the repo root (see `scripts/demos/README.md`):

```bash
python scripts/demos/detect_machine_idle.py --source 0
python scripts/demos/detect_worker_idle.py --source 0 --model models/yolo/yolov8n.pt
python scripts/demos/detect_zone_presence.py --source 0 --model models/yolo/yolov8n.pt
```

Press `q` or ESC to quit each demo.

## Docs

- `docs/OmniVision_Architecture.md` — product/architecture notes from the idle project

## Phase 1 merge note

This merge intentionally does **not** unify camera loops, event schemas, or backend inference yet. Those are stabilization tasks after all four flows are verified working in one folder.
