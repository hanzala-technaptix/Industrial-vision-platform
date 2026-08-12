# Idle & presence demos

Standalone CLI scripts merged from `industrial-vision-idle`. Each script is self-contained and unchanged in behavior.

Run from the repository root:

```bash
# Machine running / idle (optical flow, optional ROI)
python scripts/demos/detect_machine_idle.py --source 0

# Worker active / idle / absent (YOLO person + optical flow)
python scripts/demos/detect_worker_idle.py --source 0 --model models/yolo/yolov8n.pt

# Zone presence (YOLO person + polygon)
python scripts/demos/detect_zone_presence.py --source 0 --model models/yolo/yolov8n.pt
```

Press `q` or ESC to quit. Use `--help` on any script for options.
