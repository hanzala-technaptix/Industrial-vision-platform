# Industrial Safety Vision

Computer vision for factory floors. Detect people, check PPE, watch restricted zones, and measure idle time and downtime from existing CCTV or recorded video.

Demos and the live API share one engine (`FrameProcessor`). Scripts in `demos/` only call `app/pipelines/`.

**Docs:** [Use cases](docs/use_cases.md) · [Architecture](docs/architecture.md) · [Data](docs/data.md)

---

## Status

| # | Use case | Command | Video | Status |
|---|----------|---------|-------|--------|
| 01 | PPE compliance | `python demos/01_ppe/run.py --show` | `test-videos/01_ppe/` | Working |
| 02 | Person detection | `python demos/02_person/run.py` | `test-videos/02_person/` | Working |
| 03 | Restricted zone | `python demos/03_restricted_zone/run.py` | `test-videos/03_restricted_zone/` | Working |
| 04 | Product counting | `python demos/04_product_counting/run.py` | `test-videos/04_product_counting/` | Working |
| 05 | Quality defect | `python demos/05_quality_defect/run.py` | MVTec still images | Train then run |
| 06 | Machine idle | `python demos/06_machine_idle/run.py` | `test-videos/06_machine_idle/` | Working |
| 07 | Worker idle | `python demos/07_worker_idle/run.py` | Reuses 03 clip | Working |
| 08 | Downtime analytics | `python demos/08_downtime_analytics/run.py` | Reuses 06 clip | Working |

Press **q** or **ESC** to close a video window. Override a clip with `--source path`. PPE is different: pass the file as a positional argument (`python demos/01_ppe/run.py path.mp4 --show`). Quality (05) is still images on the dashboard (slideshow) and CLI (any key for next image).

---

## Setup

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Place these weights locally (not in Git):

- `models/person.pt`
- `models/ppe.pt`
- `models/mask.pt`

Place these videos locally (not in Git):

| Path | Used by |
|------|---------|
| `test-videos/01_ppe/ppe_construction_site.mp4` | 01 PPE |
| `test-videos/02_person/zone_multi_person.mp4` | 02 Person |
| `test-videos/03_restricted_zone/worker_single_person.mp4` | 03 Zone, 07 Worker idle |
| `test-videos/04_product_counting/` | 04 Counting (moving boxes) |
| `test-videos/06_machine_idle/` | 06 Machine idle, 08 Downtime (static belt) |

---

## Live showcase

The API and the dashboard are two processes. Keep both running.

**Terminal 1 — API** (video + detectors):

```powershell
.\venv\Scripts\Activate.ps1
python run.py
```

If you see `Errno 10048` / port 8001 already in use, the API is already running. Do not start a second copy. Open `http://127.0.0.1:8001/health` to confirm.

**Terminal 2 — frontend**:

```powershell
cd frontend
npm install
npm run dev
```

Then open **http://localhost:5173**. Click **01–08**. Each case has its own clip or stills and a HUD. **05 Quality** is inspection stills (not CCTV), but it is on the same switcher.

Optional start case for the API:

```powershell
$env:USE_CASE = "person"
python run.py
```

| Endpoint | Purpose |
|----------|---------|
| `/use_cases` | Catalog + which case is live |
| `POST /use_cases/{id}` | Switch demo (ppe, person, zone, worker_idle, product_counting, machine_idle, downtime) |
| `/health` | Pipeline, camera, and current use case |
| `/events` | Recent events (PPE) |
| `/events/stats` | Event counts |
| `/video_feed` | MJPEG stream of the active case |
| `/cameras` | Registered cameras |
| `/detectors` | Live detector state for the HUD |

Counting, machine idle, and downtime read `test-videos/04_product_counting/` and `test-videos/06_machine_idle/`.

---

## Architecture

```text
Camera / MP4
     │
     ▼
FrameProcessor          ← demos and live API
     │
     ├─ detection/      PPE, person
     ├─ analytics/      zone, idle, count, quality
     ├─ events/         SQLite + PPE alerts
     └─ rendering/      overlays
     │
     ├─ demos/*/run.py  CLI → app/pipelines/
     └─ run.py          FastAPI + POST /use_cases/{id}
```

| Path | Role |
|------|------|
| `app/` | Runtime: pipelines, detection, analytics, API |
| `app/pipeline/` | Shared frame engine (keep this name) |
| `app/pipelines/` | One module per use case |
| `demos/` | Thin CLI entry points |
| `models/` | Weights (`person.pt`, `ppe.pt`, `mask.pt`, `quality.pt`) |
| `test-videos/` | Runtime MP4s |
| `test-images/quality/` | Optional stills for demo 05 |
| `data/` | Training and R&D datasets |
| `tools/training/` | Mask rebuild + MVTec quality classifier |

---

## Data policy

`data/` is gitignored on purpose (~6 GB). **Do not delete it.** It holds training sets and future R&D datasets. Runtime demos read `test-videos/` and `models/` only. The API uses `data/factory.db`.

See [docs/data.md](docs/data.md) for paths, licences, and what is still missing.

Do not commit weights, MP4s, `.env`, or `data/`. Do not redistribute MVTec AD. Do not present research datasets as if the live camera already uses them.

---

## Next

Working today: 01–04, 06–08. Quality (05) after `python tools/training/quality/train_mvtec.py`.
