from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SOURCE = Path("data/merged_pool")
FINAL = Path("data/final")
QUARANTINE = Path("data/quarantine_invalid")
SEED = 42


@dataclass
class Sample:
    stem: str
    image: Path
    label: Path
    primary_class: int
    all_classes: List[int]


def safe_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def parse_label(path: Path) -> Tuple[bool, int, List[int]]:
    """
    Returns (is_valid, primary_class, all_classes).
    Valid line format: class x y w h
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return False, -1, []

    first_class = None
    classes: List[int] = []
    for raw in lines:
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        parts = s.split()
        if len(parts) != 5:
            return False, -1, []
        try:
            c = int(parts[0])
            x, y, w, h = map(float, parts[1:])
        except Exception:
            return False, -1, []
        if c not in (0, 1):
            return False, -1, []
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            return False, -1, []
        if first_class is None:
            first_class = c
        classes.append(c)

    if first_class is None:
        return False, -1, []
    return True, first_class, classes


def build_dirs() -> None:
    if FINAL.exists():
        shutil.rmtree(FINAL)
    for split in ("train", "val", "test"):
        (FINAL / "images" / split).mkdir(parents=True, exist_ok=True)
        (FINAL / "labels" / split).mkdir(parents=True, exist_ok=True)

    (QUARANTINE / "images").mkdir(parents=True, exist_ok=True)
    (QUARANTINE / "labels").mkdir(parents=True, exist_ok=True)


def collect_valid_samples() -> Tuple[List[Sample], Dict[str, int], List[Dict[str, str]]]:
    img_dir = SOURCE / "images_all"
    lbl_dir = SOURCE / "labels_all"

    images = [p for p in img_dir.glob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS]
    labels = [p for p in lbl_dir.glob("*.txt") if p.is_file()]
    img_map = {p.stem: p for p in images}
    lbl_map = {p.stem: p for p in labels}

    stats = {
        "images_total": len(images),
        "labels_total": len(labels),
        "matched_pairs": 0,
        "images_without_labels": 0,
        "labels_without_images": 0,
        "invalid_labels": 0,
    }
    quarantine_manifest: List[Dict[str, str]] = []

    image_only = sorted(set(img_map) - set(lbl_map))
    label_only = sorted(set(lbl_map) - set(img_map))
    stats["images_without_labels"] = len(image_only)
    stats["labels_without_images"] = len(label_only)

    for stem in image_only:
        src_img = img_map[stem]
        dst_img = QUARANTINE / "images" / src_img.name
        safe_copy(src_img, dst_img)
        quarantine_manifest.append(
            {
                "reason": "missing_label",
                "source_image": str(src_img).replace("\\", "/"),
                "quarantine_image": str(dst_img).replace("\\", "/"),
            }
        )

    for stem in label_only:
        src_lbl = lbl_map[stem]
        dst_lbl = QUARANTINE / "labels" / src_lbl.name
        safe_copy(src_lbl, dst_lbl)
        quarantine_manifest.append(
            {
                "reason": "missing_image",
                "source_label": str(src_lbl).replace("\\", "/"),
                "quarantine_label": str(dst_lbl).replace("\\", "/"),
            }
        )

    samples: List[Sample] = []
    for stem in sorted(set(img_map) & set(lbl_map)):
        img = img_map[stem]
        lbl = lbl_map[stem]
        valid, primary, classes = parse_label(lbl)
        if not valid:
            stats["invalid_labels"] += 1
            dst_img = QUARANTINE / "images" / img.name
            dst_lbl = QUARANTINE / "labels" / lbl.name
            safe_copy(img, dst_img)
            safe_copy(lbl, dst_lbl)
            quarantine_manifest.append(
                {
                    "reason": "invalid_label_format",
                    "source_image": str(img).replace("\\", "/"),
                    "source_label": str(lbl).replace("\\", "/"),
                    "quarantine_image": str(dst_img).replace("\\", "/"),
                    "quarantine_label": str(dst_lbl).replace("\\", "/"),
                }
            )
            continue
        samples.append(Sample(stem=stem, image=img, label=lbl, primary_class=primary, all_classes=classes))

    stats["matched_pairs"] = len(samples)
    return samples, stats, quarantine_manifest


def split_counts(n: int) -> Tuple[int, int, int]:
    train = int(round(n * 0.70))
    val = int(round(n * 0.20))
    test = n - train - val
    return train, val, test


def stratified_split(samples: List[Sample]) -> Dict[str, List[Sample]]:
    random.seed(SEED)
    c0 = [s for s in samples if s.primary_class == 0]
    c1 = [s for s in samples if s.primary_class == 1]
    random.shuffle(c0)
    random.shuffle(c1)

    c0_t, c0_v, c0_te = split_counts(len(c0))
    c1_t, c1_v, c1_te = split_counts(len(c1))

    split = {
        "train": c0[:c0_t] + c1[:c1_t],
        "val": c0[c0_t:c0_t + c0_v] + c1[c1_t:c1_t + c1_v],
        "test": c0[c0_t + c0_v:c0_t + c0_v + c0_te] + c1[c1_t + c1_v:c1_t + c1_v + c1_te],
    }
    for k in split:
        random.shuffle(split[k])
    return split


def write_split(split_map: Dict[str, List[Sample]]) -> Dict[str, Dict[str, float]]:
    report: Dict[str, Dict[str, float]] = {}
    for split, items in split_map.items():
        c0 = c1 = 0
        for s in items:
            safe_copy(s.image, FINAL / "images" / split / s.image.name)
            safe_copy(s.label, FINAL / "labels" / split / s.label.name)
            if s.primary_class == 0:
                c0 += 1
            elif s.primary_class == 1:
                c1 += 1
        total = max(c0 + c1, 1)
        report[split] = {
            "images": c0 + c1,
            "no_mask_primary": c0,
            "mask_primary": c1,
            "no_mask_pct": round((c0 * 100.0) / total, 2),
            "mask_pct": round((c1 * 100.0) / total, 2),
        }
    return report


def write_yaml() -> None:
    yaml_text = (
        "path: data/final\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "\n"
        "names:\n"
        "  0: no_mask\n"
        "  1: mask\n"
    )
    (FINAL / "data.yaml").write_text(yaml_text, encoding="utf-8")


def main() -> None:
    build_dirs()
    samples, validation_stats, quarantine_manifest = collect_valid_samples()
    split_map = stratified_split(samples)
    split_report = write_split(split_map)
    write_yaml()

    total = sum(split_report[s]["images"] for s in ("train", "val", "test"))
    total_no_mask = sum(split_report[s]["no_mask_primary"] for s in ("train", "val", "test"))
    total_mask = sum(split_report[s]["mask_primary"] for s in ("train", "val", "test"))
    denom = max(total_no_mask + total_mask, 1)

    final_report = {
        "source": str(SOURCE).replace("\\", "/"),
        "output": str(FINAL).replace("\\", "/"),
        "validation": validation_stats,
        "quarantine_invalid_dir": str(QUARANTINE).replace("\\", "/"),
        "quarantine_invalid_count": len(quarantine_manifest),
        "split_report": split_report,
        "overall": {
            "total_images": total,
            "no_mask_primary": total_no_mask,
            "mask_primary": total_mask,
            "no_mask_pct": round((total_no_mask * 100.0) / denom, 2),
            "mask_pct": round((total_mask * 100.0) / denom, 2),
        },
        "status": "READY FOR YOLO TRAINING",
    }

    (QUARANTINE / "manifest.json").write_text(json.dumps(quarantine_manifest, indent=2), encoding="utf-8")
    (FINAL / "final_report.json").write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    print(json.dumps(final_report, indent=2))


if __name__ == "__main__":
    main()
