# Data

Large files under `data/`, `models/`, and `test-videos/*.mp4` stay on disk and stay out of Git. **Do not delete `data/` because a demo does not read it.** Those folders are the training and R&D foundation for later models.

---

## Runtime

Used when running demos or the API.

| Path | Role |
|------|------|
| `test-videos/01_ppe/ppe_construction_site.mp4` | PPE demo 01 |
| `test-videos/02_person/zone_multi_person.mp4` | Person demo 02 |
| `test-videos/03_restricted_zone/worker_single_person.mp4` | Zone demo 03 and worker-idle demo 07 |
| `test-videos/04_product_counting/` | Product counting (04) — moving-box clips |
| `test-videos/06_machine_idle/` | Machine idle (06) and downtime (08) — static belt |
| `models/person.pt` | People (01–03, 07) |
| `models/ppe.pt` | Hardhat, vest, gloves |
| `models/mask.pt` | Face mask |
| `models/quality.pt` | MVTec good/defect classifier (demo 05, after training) |
| `test-images/quality/` | Optional stills for demo 05 (`good/` + `defect/`). Falls back to MVTec. |
| `data/factory.db` | SQLite event store for the API (`DB_PATH`) |

`models/experiments/` is disposable training output. Runtime camera demos need the three PPE/person `.pt` files. Demo 05 also needs `quality.pt`. `logs/` is scratch for demo DB/MP4 output and can be emptied anytime.

`data/_scenario_test.db` is a local test SQLite file, not a training set.

Worker idle reuses the 03 video on purpose. Downtime reuses the 06 static-belt clip — do not copy it into another folder.

---

## Current training

Used to build or rebuild the weights that runtime already loads. Scripts: `tools/training/mask/` and `tools/training/quality/`.

| Path | Role | Runtime? |
|------|------|----------|
| `data/safety/mask/` | YOLO mask set (`no_mask` / `mask`), images + labels | No — trains `mask.pt` |
| `data/face_mask_rebuilt/` | Clean rebuild of the mask set (hashed names, train/val/test). Same classes and image count as `safety/mask/`. Keep both. | No — trains `mask.pt` |
| `data/safety/ppe_food_raw/` | PPE / food-safety source images (hairnet, kitchen, apron) | No — source for PPE retraining |
| `data/quality/mvtec/` | [MVTec AD](https://www.mvtec.com/company/research/datasets/mvtec-ad) — trains `quality.pt` (still-image demo 05) | No — trains `quality.pt` |
| `logs/mvtec_cls/` | YOLO-cls rebuild (good / defect) from the train script | No — trains `quality.pt` |

`mask.pt` is the runtime artifact of the mask sets. `ppe.pt` is the runtime PPE artifact; `ppe_food_raw/` is source imagery for retraining. `quality.pt` is the runtime artifact of the MVTec classifier (internal R&D, **CC BY-NC-SA 4.0**).

---

## Future training / R&D

Kept on purpose. Camera demos do not read these folders.

| Path | Dataset | Intended use | Status |
|------|---------|--------------|--------|
| `data/manufacturing/secom/` | [UCI SECOM](https://archive.ics.uci.edu/dataset/179/secom) | Process / yield research | Not integrated (sensors, not video) |
| `data/manufacturing/downtime/` | Bottling-line CSVs (batch, operator, downtime reasons) | Downtime analytics / model development | Not integrated (tables, not camera) |

Hitachi **MIMII** (machine sound) has not been downloaded. Do not fetch it unless that work is scheduled.

These sets are how counting, machine-state, downtime, and quality inspection should grow beyond motion heuristics. They are not replacements for CCTV in the current POC.

---

## Git

`.gitignore` excludes `data/`, `models/`, and `*.mp4`. Video folder layout is tracked via `.gitkeep` files under `test-videos/`.

Clone the repo, then copy local weights and clips into place.
