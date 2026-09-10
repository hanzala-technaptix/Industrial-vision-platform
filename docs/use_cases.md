# Use cases

Each case is one module in `app/pipelines/` and a thin script in `demos/<nn>_<name>/run.py`. The live API switches **01–08** through `POST /use_cases/{id}`. Quality (**05**) is inspection stills on the dashboard slideshow (not CCTV).

Press **q** or **ESC** to close a video window. Override the default clip with `--source path`. PPE takes a positional path instead (`python demos/01_ppe/run.py path.mp4 --show`).

Runtime videos:

| Folder | Demos |
|--------|-------|
| `test-videos/01_ppe/` | 01 |
| `test-videos/02_person/` | 02 |
| `test-videos/03_restricted_zone/` | 03, 07 |
| `test-videos/04_product_counting/` | 04 |
| `test-videos/06_machine_idle/` | 06, 08 |
| `test-videos/07_worker_idle/` | layout only — clip stays in 03 |
| `test-videos/08_downtime_analytics/` | layout only — clip stays in 06 |

---

## 01 — PPE compliance

| | |
|--|--|
| **Pain** | Helmet, mask, vest, or gloves not worn or removed |
| **What you see** | Per-person PPE boxes; a second window when an item is removed |
| **Engine** | `person.pt` + `ppe.pt` + `mask.pt` → `PPEDetector` + `PPEAlertTracker` + SQLite |
| **Video** | `test-videos/01_ppe/ppe_construction_site.mp4` |
| **Status** | Working |

```powershell
python demos/01_ppe/run.py --show
```

Optional flags: `--report`, `--out path.mp4`, `--max-frames N`, `--conf 0.18`, `--stride 2`. Video path is positional, not `--source`.

---

## 02 — Person detection

| | |
|--|--|
| **Pain** | No count of who is on the floor |
| **What you see** | Person boxes and a live count |
| **Engine** | `person.pt` (COCO class 0 only) |
| **Video** | `test-videos/02_person/zone_multi_person.mp4` |
| **Status** | Working |

```powershell
python demos/02_person/run.py
```

---

## 03 — Restricted zone

| | |
|--|--|
| **Pain** | People in areas they should not enter |
| **What you see** | Polygon overlay; alert when a person’s foot is inside |
| **Engine** | `person.pt` + `ZoneDetector` |
| **Video** | `test-videos/03_restricted_zone/worker_single_person.mp4` |
| **Status** | Working |

```powershell
python demos/03_restricted_zone/run.py
```

Override the polygon: `--zone "x1,y1 x2,y2 x3,y3 ..."`

---

## 04 — Product counting

| | |
|--|--|
| **Pain** | No count of units on a conveyor |
| **What you see** | Vertical line; increment when a motion blob crosses it |
| **Engine** | Motion blobs today; trained CV model later |
| **Video** | `test-videos/04_product_counting/` |
| **Status** | Working |

```powershell
python demos/04_product_counting/run.py
```

---

## 05 — Quality defect

| | |
|--|--|
| **Pain** | Defective product vs good (still inspection images) |
| **What you see** | GOOD / DEFECT overlay on MVTec test images |
| **Engine** | YOLO-cls `models/quality.pt` trained on one MVTec category (default `bottle`) |
| **Data** | `data/quality/mvtec/<category>/test/` |
| **Status** | Train once, then run. Dashboard slideshow + CLI. |

```powershell
python tools/training/quality/train_mvtec.py
python demos/05_quality_defect/run.py
```

Optional flags: `--category bottle`, `--max-images N`. Not CCTV. Licence: CC BY-NC-SA 4.0 (non-commercial). See [data.md](data.md).

---

## 06 — Machine idle

| | |
|--|--|
| **Pain** | Line looks busy but the machine is stopped |
| **What you see** | Running vs idle HUD from optical flow in an ROI |
| **Engine** | Optical flow today; trained machine-state model later |
| **Video** | `test-videos/06_machine_idle/` |
| **Status** | Working |

```powershell
python demos/06_machine_idle/run.py
```

---

## 07 — Worker idle

| | |
|--|--|
| **Pain** | Operator present but not working |
| **What you see** | **ACTIVE** / **IDLE** / **ABSENT** |
| **Engine** | `person.pt` + optical flow on the person box |
| **Video** | Same file as 03 (`worker_single_person.mp4`). Not duplicated. |
| **Status** | Working |

```powershell
python demos/07_worker_idle/run.py
```

---

## 08 — Downtime analytics

| | |
|--|--|
| **Pain** | No shift-level picture of running vs idle |
| **What you see** | CLI: console timeline (no video window) — segments, running %, idle %. Live dashboard: HUD on the same 06 clip. |
| **Engine** | Same motion signal as 06 today; trained downtime model later. CSV research data is in `data/manufacturing/downtime/`. |
| **Video** | Same file as 06. Not duplicated. |
| **Status** | Working |

```powershell
python demos/08_downtime_analytics/run.py
```
