"""Train a small good/defect classifier on one MVTec AD category.

Uses Ultralytics YOLO-cls (already in requirements). Not the official
unsupervised MVTec protocol — a POC classifier for the CEO still-image demo.

Licence: MVTec AD is CC BY-NC-SA 4.0. Internal R&D only. Do not ship this
weight as a commercial factory model.

    python tools/training/quality/train_mvtec.py
    python tools/training/quality/train_mvtec.py --category hazelnut --epochs 20
"""
from __future__ import annotations

import argparse
import random
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.core.config import DEVICE, LOG_DIR, MODEL_DIR, MVTEC_ROOT, QUALITY_MODEL_PATH

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp"}


def _images(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_EXTS)


def collect(category_dir: Path) -> tuple[list[Path], list[Path]]:
    good = _images(category_dir / "train" / "good")
    test = category_dir / "test"
    if not test.is_dir():
        raise FileNotFoundError(f"No MVTec test split: {test}")
    defect: list[Path] = []
    for sub in sorted(test.iterdir()):
        if not sub.is_dir():
            continue
        if sub.name.lower() == "good":
            good.extend(_images(sub))
        else:
            defect.extend(_images(sub))
    if not good or not defect:
        raise SystemExit(f"Need both good and defect images in {category_dir}")
    return good, defect


def split_copy(files: list[Path], train_dir: Path, val_dir: Path, val_ratio: float, rng: random.Random) -> None:
    files = list(files)
    rng.shuffle(files)
    n_val = max(1, int(len(files) * val_ratio))
    val, train = files[:n_val], files[n_val:]
    train_dir.mkdir(parents=True, exist_ok=True)
    val_dir.mkdir(parents=True, exist_ok=True)
    for src in train:
        _copy_image(src, train_dir / f"{src.parent.name}_{src.name}")
    for src in val:
        _copy_image(src, val_dir / f"{src.parent.name}_{src.name}")


def _copy_image(src: Path, dst: Path) -> None:
    if dst.exists():
        try:
            dst.chmod(0o666)
        except OSError:
            pass
        dst.unlink()
    shutil.copyfile(src, dst)


def build_cls_set(category: str, out_root: Path, val_ratio: float, seed: int) -> Path:
    src = MVTEC_ROOT / category
    if not src.is_dir():
        raise SystemExit(f"MVTec category not found: {src}")
    good, defect = collect(src)
    if out_root.exists():
        shutil.rmtree(out_root, ignore_errors=True)
    rng = random.Random(seed)
    split_copy(good, out_root / "train" / "good", out_root / "val" / "good", val_ratio, rng)
    split_copy(defect, out_root / "train" / "defect", out_root / "val" / "defect", val_ratio, rng)
    print(f"[mvtec] {category}: train/val written to {out_root}")
    return out_root


def train(cls_root: Path, epochs: int, imgsz: int, out_pt: Path) -> Path:
    from ultralytics import YOLO

    pretrained = MODEL_DIR / "yolov8n-cls.pt"
    model = YOLO(str(pretrained) if pretrained.exists() else "yolov8n-cls.pt")
    run_dir = MODEL_DIR / "experiments" / "mvtec"
    results = model.train(
        data=str(cls_root),
        epochs=epochs,
        imgsz=imgsz,
        device=DEVICE,
        project=str(run_dir.parent),
        name=run_dir.name,
        exist_ok=True,
        verbose=True,
    )
    best = Path(results.save_dir) / "weights" / "best.pt"
    if not best.exists():
        raise SystemExit(f"Training finished but best.pt missing: {best}")
    out_pt.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best, out_pt)
    print(f"[mvtec] copied {best} -> {out_pt}")
    last = Path(results.save_dir) / "weights" / "last.pt"
    if last.exists():
        last_out = MODEL_DIR / "quality_last.pt"
        shutil.copy2(last, last_out)
        last.unlink()
        print(f"[mvtec] copied {last} -> {last_out}")
    best.unlink()
    return out_pt


def main() -> int:
    ap = argparse.ArgumentParser(description="Train MVTec good/defect YOLO-cls")
    ap.add_argument("--category", default="bottle", help="MVTec category folder name")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--imgsz", type=int, default=224)
    ap.add_argument("--val-ratio", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    print("MVTec AD is CC BY-NC-SA 4.0 — internal R&D only.")
    cls_root = LOG_DIR / "mvtec_cls" / args.category
    build_cls_set(args.category, cls_root, args.val_ratio, args.seed)
    train(cls_root, args.epochs, args.imgsz, QUALITY_MODEL_PATH)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
