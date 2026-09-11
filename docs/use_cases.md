# Use cases

Each case is selected on the live dashboard. The API switches **01–08** through `POST /use_cases/{id}`. Quality (**05**) is inspection stills on the dashboard slideshow (not CCTV).

Runtime videos:

| Folder | Cases |
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
| **What you see** | Per-person PPE boxes; HUD alerts and Schedule A when an item is missing |
| **Engine** | `person.pt` + `ppe.pt` + `mask.pt` → `PPEDetector` + `PPEAlertTracker` + SQLite |
| **Video** | `test-videos/01_ppe/ppe_construction_site.mp4` |
| **Status** | Working |

---

## 02 — Person detection

| | |
|--|--|
| **Pain** | No count of who is on the floor |
| **What you see** | Person boxes and a live count |
| **Engine** | `person.pt` (COCO class 0 only) |
| **Video** | `test-videos/02_person/zone_multi_person.mp4` |
| **Status** | Working |

---

## 03 — Restricted zone

| | |
|--|--|
| **Pain** | People in areas they should not enter |
| **What you see** | Polygon overlay; alert when a person’s foot is inside |
| **Engine** | `person.pt` + `ZoneDetector` |
| **Video** | `test-videos/03_restricted_zone/worker_single_person.mp4` |
| **Status** | Working |

---

## 04 — Product counting

| | |
|--|--|
| **Pain** | No count of units on a conveyor |
| **What you see** | Vertical line; increment when a motion blob crosses it |
| **Engine** | Motion blobs today; trained CV model later |
| **Video** | `test-videos/04_product_counting/` |
| **Status** | Working |

---

## 05 — Quality defect

| | |
|--|--|
| **Pain** | Defective product vs good (still inspection images) |
| **What you see** | GOOD / DEFECT overlay on MVTec test images |
| **Engine** | YOLO-cls `models/quality.pt` trained on one MVTec category (default `bottle`) |
| **Data** | `data/quality/mvtec/<category>/test/` |
| **Status** | Train once, then run on the dashboard slideshow. |

```powershell
python tools/training/quality/train_mvtec.py
```

Not CCTV. Licence: CC BY-NC-SA 4.0 (non-commercial). See [data.md](data.md).

---

## 06 — Machine idle

| | |
|--|--|
| **Pain** | Line looks busy but the machine is stopped |
| **What you see** | Running vs idle HUD from optical flow in an ROI |
| **Engine** | Optical flow today; trained machine-state model later |
| **Video** | `test-videos/06_machine_idle/` |
| **Status** | Working |

---

## 07 — Worker idle

| | |
|--|--|
| **Pain** | Operator present but not working |
| **What you see** | **ACTIVE** / **IDLE** / **ABSENT** |
| **Engine** | `person.pt` + optical flow on the person box |
| **Video** | Same file as 03 (`worker_single_person.mp4`). Not duplicated. |
| **Status** | Working |

---

## 08 — Downtime analytics

| | |
|--|--|
| **Pain** | No shift-level picture of running vs idle |
| **What you see** | HUD on the same 06 clip: running vs idle share |
| **Engine** | Same motion signal as 06 today; trained downtime model later. CSV research data is in `data/manufacturing/downtime/`. |
| **Video** | Same file as 06. Not duplicated. |
| **Status** | Working |
