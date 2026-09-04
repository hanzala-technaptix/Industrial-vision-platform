# CEO demo cheat sheet

Run from repo root with venv activated:

```powershell
python demos/01_ppe/run.py --show
python demos/02_person_vehicle/run.py
python demos/03_restricted_zone/run.py
python demos/06_machine_idle/run.py
python demos/07_worker_idle/run.py

# Machine / analytics — need test-videos/machine/*.mp4
python demos/04_product_counting/run.py
python demos/08_downtime_analytics/run.py
```

Press **q** or **ESC** to quit.

## How demos connect to app/

| Demo | App detector | Runner |
|------|--------------|--------|
| 01 PPE | `app/detectors/ppe.py` | `video_runner.run_ppe_demo` |
| 02 Person | `app/detectors/person.py` | `video_runner.run_person_demo` |
| 03 Zone | `app/detectors/zone.py` | `video_runner.run_zone_demo` |
| 06 Machine idle | `app/detectors/machine_idle.py` | `video_runner.run_machine_idle_demo` |
| 04–08 | demo-specific lib | standalone (motion/analytics) |

Demos **01–03** and **06** use the same `FrameProcessor` as `python run.py`.

## Bundled videos

| Demo | Video |
|------|-------|
| 01 PPE | `ppe_construction_site.mp4` |
| 02 Person/vehicle | `zone_multi_person.mp4` |
| 03 Zone / 07 Worker idle | `worker_single_person.mp4` |
| 04 / 06 / 08 Machine | `test-videos/machine/*.mp4` (you provide) |

## Options

PPE: `--report`, `--out`, `--max-frames`, `--conf`  
All video demos: `--show`, `--source path`
