import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def log(msg: str) -> None:
    print(f"[PIPELINE] {msg}")


def guess_data_yaml(dataset_dir: Path) -> Path | None:
    candidates = list(dataset_dir.rglob("data.yaml")) + list(dataset_dir.rglob("dataset.yaml"))
    return candidates[0] if candidates else None


def _resolve_data_path(base_dir: Path, rel_or_abs: str) -> Path:
    candidate = Path(rel_or_abs)
    return candidate if candidate.is_absolute() else (base_dir / candidate).resolve()


def _labels_dir_for_images_dir(images_dir: Path) -> Path:
    images_dir_str = str(images_dir)
    if "images" in images_dir_str:
        return Path(images_dir_str.replace("images", "labels"))
    return images_dir.parent / "labels"


def _iter_images(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return [p for p in path.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]


def _md5_key(value: str) -> str:
    return hashlib.md5(value.encode("utf-8")).hexdigest()


def load_dataset_config(data_yaml_path: Path) -> dict[str, Any]:
    with open(data_yaml_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def rebuild_dataset(data_yaml_path: Path, rebuilt_root: Path) -> Path:
    """
    Build a strict YOLO dataset with deterministic names and valid image/label pairs only.
    """
    cfg = load_dataset_config(data_yaml_path)
    base_dir = data_yaml_path.parent

    split_keys = ["train", "val", "test"]
    split_to_pairs_copied: dict[str, int] = {k: 0 for k in split_keys}
    split_to_pairs_skipped: dict[str, int] = {k: 0 for k in split_keys}

    if rebuilt_root.exists():
        shutil.rmtree(rebuilt_root)
    rebuilt_root.mkdir(parents=True, exist_ok=True)

    images_root = rebuilt_root / "images"
    labels_root = rebuilt_root / "labels"
    images_root.mkdir(parents=True, exist_ok=True)
    labels_root.mkdir(parents=True, exist_ok=True)

    names = cfg.get("names", {})
    for split in split_keys:
        split_ref = cfg.get(split)
        if not split_ref:
            continue

        src_images_dir = _resolve_data_path(base_dir, str(split_ref))
        src_labels_dir = _labels_dir_for_images_dir(src_images_dir)
        if not src_images_dir.exists():
            raise FileNotFoundError(f"Split '{split}' images path not found: {src_images_dir}")
        if not src_labels_dir.exists():
            raise FileNotFoundError(f"Split '{split}' labels path not found: {src_labels_dir}")

        dst_images_dir = images_root / split
        dst_labels_dir = labels_root / split
        dst_images_dir.mkdir(parents=True, exist_ok=True)
        dst_labels_dir.mkdir(parents=True, exist_ok=True)

        for img_path in _iter_images(src_images_dir):
            rel_img = img_path.relative_to(src_images_dir).as_posix()
            label_path = src_labels_dir / f"{img_path.stem}.txt"

            if not label_path.exists():
                split_to_pairs_skipped[split] += 1
                continue

            deterministic_stem = _md5_key(f"{split}:{rel_img}")
            out_img = dst_images_dir / f"{deterministic_stem}{img_path.suffix.lower()}"
            out_lbl = dst_labels_dir / f"{deterministic_stem}.txt"

            shutil.copy2(img_path, out_img)
            shutil.copy2(label_path, out_lbl)
            split_to_pairs_copied[split] += 1

    rebuilt_data_yaml = rebuilt_root / "data.yaml"
    rebuilt_cfg: dict[str, Any] = {
        "path": str(rebuilt_root.resolve()),
        "train": "images/train",
        "val": "images/val",
        "nc": int(cfg.get("nc", 0)),
        "names": names,
    }
    if (images_root / "test").exists():
        rebuilt_cfg["test"] = "images/test"

    with open(rebuilt_data_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(rebuilt_cfg, f, sort_keys=False)

    log(f"Rebuild complete: copied={split_to_pairs_copied}, skipped_missing_labels={split_to_pairs_skipped}")
    return rebuilt_data_yaml


def validate_dataset(data_yaml_path: Path) -> dict[str, dict[str, int]]:
    """
    Strict validation gate:
    - image count == label count for each split
    - 100% stem matching
    """
    cfg = load_dataset_config(data_yaml_path)
    base_dir = data_yaml_path.parent
    stats: dict[str, dict[str, int]] = {}

    for split in ["train", "val", "test"]:
        if split not in cfg:
            continue

        images_dir = _resolve_data_path(base_dir, str(cfg[split]))
        labels_dir = _labels_dir_for_images_dir(images_dir)

        images = _iter_images(images_dir)
        labels = list(labels_dir.glob("*.txt")) if labels_dir.exists() else []

        image_stems = {p.stem for p in images}
        label_stems = {p.stem for p in labels}
        missing_labels = image_stems - label_stems
        missing_images = label_stems - image_stems

        stats[split] = {
            "images": len(images),
            "labels": len(labels),
            "missing_labels": len(missing_labels),
            "missing_images": len(missing_images),
        }

        if len(images) != len(labels) or missing_labels or missing_images:
            raise ValueError(
                f"Validation failed for split='{split}': "
                f"images={len(images)}, labels={len(labels)}, "
                f"missing_labels={len(missing_labels)}, missing_images={len(missing_images)}"
            )

    log("Validation passed: all splits have perfect image-label stem matching.")
    return stats


def compute_dataset_stats(data_yaml_path: Path) -> dict[str, Any]:
    cfg = load_dataset_config(data_yaml_path)
    base_dir = data_yaml_path.parent

    per_split_counts: dict[str, int] = {}
    class_distribution: dict[str, int] = {}
    file_names_for_hash: list[str] = []

    for split in ["train", "val", "test"]:
        if split not in cfg:
            continue

        images_dir = _resolve_data_path(base_dir, str(cfg[split]))
        labels_dir = _labels_dir_for_images_dir(images_dir)
        images = _iter_images(images_dir)
        label_files = list(labels_dir.glob("*.txt")) if labels_dir.exists() else []
        per_split_counts[split] = len(images)

        for img in images:
            file_names_for_hash.append(str(img.relative_to(base_dir)).replace("\\", "/"))
        for lbl in label_files:
            file_names_for_hash.append(str(lbl.relative_to(base_dir)).replace("\\", "/"))

        for lbl in label_files:
            lines = lbl.read_text(encoding="utf-8", errors="ignore").splitlines()
            for line in lines:
                parts = line.strip().split()
                if not parts:
                    continue
                class_id = parts[0]
                class_distribution[class_id] = class_distribution.get(class_id, 0) + 1

    dataset_hash_input = "\n".join(sorted(file_names_for_hash))
    dataset_hash = hashlib.sha256(dataset_hash_input.encode("utf-8")).hexdigest()
    total_images = sum(per_split_counts.values())

    warning = None
    if class_distribution:
        counts = sorted(class_distribution.values())
        if counts[0] > 0 and counts[-1] / counts[0] >= 3:
            warning = "Class imbalance warning: max/min class frequency ratio >= 3."

    stats = {
        "total_images": total_images,
        "images_per_split": per_split_counts,
        "class_distribution": class_distribution,
        "dataset_hash": dataset_hash,
        "imbalance_warning": warning,
    }
    return stats


def save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        shutil.copy2(src, dst)
    else:
        raise FileNotFoundError(f"Expected artifact not found: {src}")


def run_training(
    data_yaml_path: Path,
    run_id: str,
    experiment_dir: Path,
    model_name: str,
    epochs: int,
    batch: int,
    imgsz: int,
    device: str | None,
    workers: int,
    enable_tensorboard: bool,
    log_per_class_metrics: bool,
    deployed_model_path: Path,
) -> None:
    from ultralytics import YOLO

    model = YOLO(model_name)
    log("Starting YOLO training...")
    results = model.train(
        data=str(data_yaml_path),
        epochs=epochs,
        batch=batch,
        imgsz=imgsz,
        device=device,
        workers=workers,
        project="models/experiments/runs",
        name=run_id,
        exist_ok=False,
        plots=True,
    )

    save_dir = Path(getattr(results, "save_dir", "")).resolve()
    if not save_dir.exists():
        raise FileNotFoundError(f"YOLO save_dir not found: {save_dir}")

    weights_dir = save_dir / "weights"
    best_pt = weights_dir / "best.pt"
    last_pt = weights_dir / "last.pt"
    results_csv = save_dir / "results.csv"
    confusion_png = save_dir / "confusion_matrix.png"

    copy_if_exists(best_pt, experiment_dir / "best.pt")
    copy_if_exists(last_pt, experiment_dir / "last.pt")
    copy_if_exists(results_csv, experiment_dir / "results.csv")
    copy_if_exists(confusion_png, experiment_dir / "confusion_matrix.png")
    deployed_model_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_pt, deployed_model_path)

    if enable_tensorboard:
        # Ultralytics writes TensorBoard events in run save_dir when supported.
        tb_events = list(save_dir.glob("events.out.tfevents.*"))
        for event_file in tb_events:
            shutil.copy2(event_file, experiment_dir / event_file.name)

    if log_per_class_metrics:
        val_metrics = model.val(data=str(data_yaml_path), split="val")
        per_class = {}
        names = getattr(model, "names", {})
        maps = getattr(getattr(val_metrics, "box", None), "maps", None)
        if maps is not None:
            for class_id, ap in enumerate(maps):
                per_class[str(class_id)] = {
                    "class_name": str(names.get(class_id, class_id)),
                    "ap50_95": float(ap),
                }
        save_json(experiment_dir / "per_class_metrics.json", per_class)

    save_json(
        experiment_dir / "artifacts.json",
        {
            "run_id": run_id,
            "save_dir": str(save_dir),
            "best_pt": str(best_pt),
            "last_pt": str(last_pt),
            "results_csv": str(results_csv),
            "confusion_matrix": str(confusion_png),
            "deployed_model_path": str(deployed_model_path),
        },
    )
    log(f"Training finished. Artifacts captured from: {save_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Production YOLO training pipeline with strict data QA.")
    parser.add_argument("--dataset-dir", required=True, help="Raw dataset directory containing data.yaml.")
    parser.add_argument("--data-yaml", default=None, help="Optional path to data.yaml if not in dataset-dir.")
    parser.add_argument("--model", default="yolov8s.pt", help="Ultralytics model checkpoint (e.g., yolov8s.pt).")
    parser.add_argument("--epochs", type=int, default=50)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default=None, help="Device for training, e.g. 0 or cpu.")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--force-retrain", action="store_true", help="Allow overwrite of existing run_id directory.")
    parser.add_argument(
        "--rebuilt-dataset-dir",
        default="data/face_mask_rebuilt",
        help="Output folder for clean rebuilt dataset.",
    )
    parser.add_argument(
        "--experiments-root",
        default="models/experiments",
        help="Root path for reproducible experiment logging.",
    )
    parser.add_argument("--enable-tensorboard", action="store_true", help="Copy TensorBoard event files if present.")
    parser.add_argument("--log-per-class-metrics", action="store_true", help="Run validation for per-class AP.")
    parser.add_argument(
        "--deployed-model-path",
        default="models/yolo/mask_yolov8_best.pt",
        help="Stable path where current run best.pt is copied for inference.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dataset_dir = Path(args.dataset_dir).expanduser().resolve()
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset dir not found: {dataset_dir}")

    source_data_yaml = (
        Path(args.data_yaml).expanduser().resolve() if args.data_yaml else guess_data_yaml(dataset_dir)
    )
    if not source_data_yaml or not source_data_yaml.exists():
        raise FileNotFoundError("Could not locate data.yaml. Use --data-yaml to provide an explicit path.")

    rebuilt_root = Path(args.rebuilt_dataset_dir).expanduser().resolve()
    rebuilt_data_yaml = rebuild_dataset(source_data_yaml, rebuilt_root)

    validation_summary = validate_dataset(rebuilt_data_yaml)
    dataset_stats = compute_dataset_stats(rebuilt_data_yaml)
    if dataset_stats.get("imbalance_warning"):
        log(str(dataset_stats["imbalance_warning"]))

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    experiments_root = Path(args.experiments_root).expanduser().resolve()
    experiment_dir = experiments_root / run_id

    if experiment_dir.exists() and not args.force_retrain:
        raise FileExistsError(
            f"Experiment directory already exists: {experiment_dir}. "
            "Use --force-retrain to allow overwrite."
        )
    if experiment_dir.exists() and args.force_retrain:
        shutil.rmtree(experiment_dir)
    experiment_dir.mkdir(parents=True, exist_ok=True)

    config_payload = {
        "run_id": run_id,
        "source_data_yaml": str(source_data_yaml),
        "rebuilt_data_yaml": str(rebuilt_data_yaml),
        "dataset_hash": dataset_stats["dataset_hash"],
        "hyperparameters": {
            "model": args.model,
            "epochs": args.epochs,
            "batch": args.batch,
            "imgsz": args.imgsz,
            "device": args.device,
            "workers": args.workers,
        },
        "advanced": {
            "enable_tensorboard": args.enable_tensorboard,
            "log_per_class_metrics": args.log_per_class_metrics,
        },
    }

    save_json(experiment_dir / "config.json", config_payload)
    save_json(experiment_dir / "dataset_stats.json", dataset_stats)
    save_json(experiment_dir / "validation_summary.json", validation_summary)

    log(f"Run ID: {run_id}")
    log(f"Dataset hash: {dataset_stats['dataset_hash']}")
    log(f"Config: epochs={args.epochs}, batch={args.batch}, imgsz={args.imgsz}, model={args.model}")

    run_training(
        data_yaml_path=rebuilt_data_yaml,
        run_id=run_id,
        experiment_dir=experiment_dir,
        model_name=args.model,
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
        workers=args.workers,
        enable_tensorboard=args.enable_tensorboard,
        log_per_class_metrics=args.log_per_class_metrics,
        deployed_model_path=Path(args.deployed_model_path).expanduser().resolve(),
    )

    log(f"Experiment completed successfully: {experiment_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
