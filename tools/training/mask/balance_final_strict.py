from __future__ import annotations

import json
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
SEED = 42

INPUT_ROOT = Path("data/final")
OUTPUT_ROOT = Path("data/final_balanced_strict")
OVERFLOW_ROOT = Path("data/overflow_removed")
QUARANTINE_ROOT = Path("data/quarantine_invalid")


@dataclass
class Sample:
    split: str
    stem: str
    image: Path
    label: Path
    primary_class: int


def safe_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def prepare_output_dirs() -> None:
    reset_dir(OUTPUT_ROOT)
    reset_dir(OVERFLOW_ROOT)
    # Keep existing quarantine content; only ensure dirs exist.
    (QUARANTINE_ROOT / "images").mkdir(parents=True, exist_ok=True)
    (QUARANTINE_ROOT / "labels").mkdir(parents=True, exist_ok=True)

    for root in (OUTPUT_ROOT,):
        for split in ("train", "val", "test"):
            (root / "images" / split).mkdir(parents=True, exist_ok=True)
            (root / "labels" / split).mkdir(parents=True, exist_ok=True)
    for cls_name in ("no_mask", "mask"):
        (OVERFLOW_ROOT / cls_name / "images").mkdir(parents=True, exist_ok=True)
        (OVERFLOW_ROOT / cls_name / "labels").mkdir(parents=True, exist_ok=True)


def parse_label_primary(path: Path) -> Tuple[bool, int]:
    """
    Validate YOLO format and return primary class (first non-empty annotation line).
    """
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except Exception:
        return False, -1

    primary = None
    found_any = False
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        found_any = True
        parts = s.split()
        if len(parts) != 5:
            return False, -1
        try:
            c = int(parts[0])
            x, y, w, h = map(float, parts[1:])
        except Exception:
            return False, -1
        if c not in (0, 1):
            return False, -1
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            return False, -1
        if primary is None:
            primary = c
    if not found_any or primary is None:
        return False, -1
    return True, primary


def collect_samples() -> Tuple[List[Sample], Dict[str, int], List[Dict[str, str]]]:
    stats = {
        "images_total": 0,
        "labels_total": 0,
        "matched_pairs": 0,
        "images_without_labels": 0,
        "labels_without_images": 0,
        "invalid_labels": 0,
    }
    quarantine_manifest: List[Dict[str, str]] = []
    out: List[Sample] = []

    for split in ("train", "val", "test"):
        img_dir = INPUT_ROOT / "images" / split
        lbl_dir = INPUT_ROOT / "labels" / split
        imgs = [p for p in img_dir.glob("*") if p.is_file() and p.suffix.lower() in IMG_EXTS] if img_dir.exists() else []
        lbls = [p for p in lbl_dir.glob("*.txt")] if lbl_dir.exists() else []
        stats["images_total"] += len(imgs)
        stats["labels_total"] += len(lbls)

        img_map = {p.stem: p for p in imgs}
        lbl_map = {p.stem: p for p in lbls}
        common = sorted(set(img_map) & set(lbl_map))
        img_only = sorted(set(img_map) - set(lbl_map))
        lbl_only = sorted(set(lbl_map) - set(img_map))

        stats["images_without_labels"] += len(img_only)
        stats["labels_without_images"] += len(lbl_only)

        for stem in img_only:
            src = img_map[stem]
            dst = QUARANTINE_ROOT / "images" / src.name
            safe_copy(src, dst)
            quarantine_manifest.append(
                {
                    "reason": "missing_label",
                    "source_image": str(src).replace("\\", "/"),
                    "quarantine_image": str(dst).replace("\\", "/"),
                }
            )
        for stem in lbl_only:
            src = lbl_map[stem]
            dst = QUARANTINE_ROOT / "labels" / src.name
            safe_copy(src, dst)
            quarantine_manifest.append(
                {
                    "reason": "missing_image",
                    "source_label": str(src).replace("\\", "/"),
                    "quarantine_label": str(dst).replace("\\", "/"),
                }
            )

        for stem in common:
            img = img_map[stem]
            lbl = lbl_map[stem]
            valid, primary = parse_label_primary(lbl)
            if not valid:
                stats["invalid_labels"] += 1
                qi = QUARANTINE_ROOT / "images" / img.name
                ql = QUARANTINE_ROOT / "labels" / lbl.name
                safe_copy(img, qi)
                safe_copy(lbl, ql)
                quarantine_manifest.append(
                    {
                        "reason": "invalid_label",
                        "source_image": str(img).replace("\\", "/"),
                        "source_label": str(lbl).replace("\\", "/"),
                        "quarantine_image": str(qi).replace("\\", "/"),
                        "quarantine_label": str(ql).replace("\\", "/"),
                    }
                )
                continue
            out.append(Sample(split=split, stem=stem, image=img, label=lbl, primary_class=primary))
    stats["matched_pairs"] = len(out)
    return out, stats, quarantine_manifest


def class_distribution(samples: List[Sample]) -> Dict[str, float]:
    c0 = sum(1 for s in samples if s.primary_class == 0)
    c1 = sum(1 for s in samples if s.primary_class == 1)
    t = max(c0 + c1, 1)
    return {
        "total_images": c0 + c1,
        "no_mask_count": c0,
        "mask_count": c1,
        "no_mask_pct": round(c0 * 100.0 / t, 2),
        "mask_pct": round(c1 * 100.0 / t, 2),
    }


def split_counts(n: int) -> Tuple[int, int, int]:
    tr = int(round(n * 0.70))
    va = int(round(n * 0.20))
    te = n - tr - va
    return tr, va, te


def main() -> None:
    random.seed(SEED)
    prepare_output_dirs()

    all_samples, validation, quarantine_manifest = collect_samples()
    before = class_distribution(all_samples)

    no_mask = [s for s in all_samples if s.primary_class == 0]
    mask = [s for s in all_samples if s.primary_class == 1]
    random.shuffle(no_mask)
    random.shuffle(mask)

    # Strict ratio computation as requested
    total_target = min(len(no_mask) / 0.6, len(mask) / 0.4)
    allowed_no_mask = int(total_target * 0.6)
    allowed_mask = int(total_target * 0.4)

    keep_no_mask = no_mask[:allowed_no_mask]
    keep_mask = mask[:allowed_mask]
    overflow_no_mask = no_mask[allowed_no_mask:]
    overflow_mask = mask[allowed_mask:]

    # Move overflow to separate folder (copy; source preserved)
    for i, s in enumerate(overflow_no_mask, 1):
        stem = f"overflow_no_mask_{i:06d}_{s.stem}"
        safe_copy(s.image, OVERFLOW_ROOT / "no_mask" / "images" / f"{stem}{s.image.suffix.lower()}")
        safe_copy(s.label, OVERFLOW_ROOT / "no_mask" / "labels" / f"{stem}.txt")
    for i, s in enumerate(overflow_mask, 1):
        stem = f"overflow_mask_{i:06d}_{s.stem}"
        safe_copy(s.image, OVERFLOW_ROOT / "mask" / "images" / f"{stem}{s.image.suffix.lower()}")
        safe_copy(s.label, OVERFLOW_ROOT / "mask" / "labels" / f"{stem}.txt")

    # Stratified 70/20/10 split after strict filtering
    tr0, va0, te0 = split_counts(len(keep_no_mask))
    tr1, va1, te1 = split_counts(len(keep_mask))
    split_map: Dict[str, List[Sample]] = {
        "train": keep_no_mask[:tr0] + keep_mask[:tr1],
        "val": keep_no_mask[tr0:tr0 + va0] + keep_mask[tr1:tr1 + va1],
        "test": keep_no_mask[tr0 + va0:tr0 + va0 + te0] + keep_mask[tr1 + va1:tr1 + va1 + te1],
    }
    for k in split_map:
        random.shuffle(split_map[k])

    split_report: Dict[str, Dict[str, float]] = {}
    for split, items in split_map.items():
        c0 = c1 = 0
        for s in items:
            safe_copy(s.image, OUTPUT_ROOT / "images" / split / s.image.name)
            safe_copy(s.label, OUTPUT_ROOT / "labels" / split / s.label.name)
            if s.primary_class == 0:
                c0 += 1
            else:
                c1 += 1
        tot = max(c0 + c1, 1)
        split_report[split] = {
            "images": c0 + c1,
            "no_mask_count": c0,
            "mask_count": c1,
            "no_mask_pct": round(c0 * 100.0 / tot, 2),
            "mask_pct": round(c1 * 100.0 / tot, 2),
        }

    final_kept = keep_no_mask + keep_mask
    after = class_distribution(final_kept)

    yaml_text = (
        "path: data/final_balanced_strict\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "\n"
        "names:\n"
        "  0: no_mask\n"
        "  1: mask\n"
    )
    (OUTPUT_ROOT / "data.yaml").write_text(yaml_text, encoding="utf-8")

    (QUARANTINE_ROOT / "manifest.json").write_text(json.dumps(quarantine_manifest, indent=2), encoding="utf-8")

    report = {
        "input": str(INPUT_ROOT).replace("\\", "/"),
        "output": str(OUTPUT_ROOT).replace("\\", "/"),
        "overflow_dir": str(OVERFLOW_ROOT).replace("\\", "/"),
        "validation": validation,
        "before_balancing": before,
        "strict_target": {"no_mask_pct": 60.0, "mask_pct": 40.0},
        "strict_allowed": {
            "total_target": int(total_target),
            "allowed_no_mask": allowed_no_mask,
            "allowed_mask": allowed_mask,
        },
        "overflow_moved": {
            "no_mask": len(overflow_no_mask),
            "mask": len(overflow_mask),
            "total": len(overflow_no_mask) + len(overflow_mask),
        },
        "after_balancing": after,
        "split_report": split_report,
        "status": "STRICT BALANCE ACHIEVED",
    }
    (OUTPUT_ROOT / "balance_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
