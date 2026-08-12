from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path("data")
IMG_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
QUARANTINE_DIR = ROOT / "quarantine_duplicates"
MERGED_POOL_DIR = ROOT / "merged_pool"
CANONICAL_YOLO = ROOT / "face_mask_rebuilt"


@dataclass
class PairRecord:
    dataset: str
    split: str
    image: Path
    label: Path
    img_hash: str
    label_hash: str
    classes: List[int]
    invalid_lines: int
    empty_label: bool


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_label(path: Path) -> Tuple[List[int], int, bool]:
    classes: List[int] = []
    invalid = 0
    if path.stat().st_size == 0:
        return classes, 0, True

    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    found = False
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        found = True
        parts = s.split()
        if len(parts) != 5:
            invalid += 1
            continue
        try:
            c = int(parts[0])
            x, y, w, h = map(float, parts[1:])
        except Exception:
            invalid += 1
            continue
        if c < 0 or not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
            invalid += 1
        classes.append(c)
    if not found:
        return classes, invalid, True
    return classes, invalid, False


def is_readable_image(path: Path) -> bool:
    try:
        import cv2  # type: ignore
    except Exception:
        return True
    img = cv2.imread(str(path))
    return img is not None


def list_yolo_roots() -> List[Path]:
    roots = []
    for p in ROOT.rglob("*"):
        if p.is_dir() and (p / "images").exists() and (p / "labels").exists():
            roots.append(p)
    return sorted(roots)


def collect_flat_pairs(folder: Path) -> Tuple[List[PairRecord], Dict[str, int]]:
    """
    Collect image+sidecar-txt pairs from a flat folder (no images/labels subdirs).
    """
    issues = {
        "images": 0,
        "labels": 0,
        "matched": 0,
        "images_without_labels": 0,
        "labels_without_images": 0,
        "corrupt_images": 0,
        "empty_label_files": 0,
        "invalid_annotations": 0,
    }
    pairs: List[PairRecord] = []

    imgs = [p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in IMG_EXT]
    lbls = [p for p in folder.rglob("*.txt") if p.is_file()]
    img_map = {p.stem: p for p in imgs}
    lbl_map = {p.stem: p for p in lbls}
    common = sorted(set(img_map) & set(lbl_map))

    issues["images"] = len(imgs)
    issues["labels"] = len(lbls)
    issues["matched"] = len(common)
    issues["images_without_labels"] = len(set(img_map) - set(lbl_map))
    issues["labels_without_images"] = len(set(lbl_map) - set(img_map))

    for stem in common:
        image = img_map[stem]
        label = lbl_map[stem]
        if not is_readable_image(image):
            issues["corrupt_images"] += 1
            continue
        classes, invalid, empty = parse_label(label)
        issues["invalid_annotations"] += invalid
        if empty:
            issues["empty_label_files"] += 1
            continue
        pairs.append(
            PairRecord(
                dataset=str(folder).replace("\\", "/"),
                split="flat",
                image=image,
                label=label,
                img_hash=md5_file(image),
                label_hash=md5_file(label),
                classes=classes,
                invalid_lines=invalid,
                empty_label=empty,
            )
        )
    return pairs, issues


def collect_pairs(yolo_root: Path) -> Tuple[List[PairRecord], Dict[str, int]]:
    issues = {
        "images": 0,
        "labels": 0,
        "matched": 0,
        "images_without_labels": 0,
        "labels_without_images": 0,
        "corrupt_images": 0,
        "empty_label_files": 0,
        "invalid_annotations": 0,
    }
    pairs: List[PairRecord] = []

    split_names = sorted(
        {p.name for p in (yolo_root / "images").glob("*") if p.is_dir()}
        | {p.name for p in (yolo_root / "labels").glob("*") if p.is_dir()}
    )
    for split in split_names:
        img_dir = yolo_root / "images" / split
        lbl_dir = yolo_root / "labels" / split
        imgs = [p for p in img_dir.glob("*") if p.is_file() and p.suffix.lower() in IMG_EXT] if img_dir.exists() else []
        lbls = [p for p in lbl_dir.glob("*.txt")] if lbl_dir.exists() else []

        img_map = {p.stem: p for p in imgs}
        lbl_map = {p.stem: p for p in lbls}
        common = sorted(set(img_map) & set(lbl_map))

        issues["images"] += len(imgs)
        issues["labels"] += len(lbls)
        issues["matched"] += len(common)
        issues["images_without_labels"] += len(set(img_map) - set(lbl_map))
        issues["labels_without_images"] += len(set(lbl_map) - set(img_map))

        for stem in common:
            image = img_map[stem]
            label = lbl_map[stem]
            if not is_readable_image(image):
                issues["corrupt_images"] += 1
                continue
            classes, invalid, empty = parse_label(label)
            issues["invalid_annotations"] += invalid
            if empty:
                issues["empty_label_files"] += 1
                continue
            pairs.append(
                PairRecord(
                    dataset=str(yolo_root).replace("\\", "/"),
                    split=split,
                    image=image,
                    label=label,
                    img_hash=md5_file(image),
                    label_hash=md5_file(label),
                    classes=classes,
                    invalid_lines=invalid,
                    empty_label=empty,
                )
            )
    return pairs, issues


def ensure_dirs():
    (QUARANTINE_DIR / "images").mkdir(parents=True, exist_ok=True)
    (QUARANTINE_DIR / "labels").mkdir(parents=True, exist_ok=True)
    (MERGED_POOL_DIR / "images_all").mkdir(parents=True, exist_ok=True)
    (MERGED_POOL_DIR / "labels_all").mkdir(parents=True, exist_ok=True)


def safe_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)


def main():
    ensure_dirs()
    yolo_roots = list_yolo_roots()

    all_pairs: List[PairRecord] = []
    per_dataset_issues: Dict[str, Dict[str, int]] = {}
    image_only_folders = []
    flat_labeled_folders = []
    for top in sorted([p for p in ROOT.iterdir() if p.is_dir()]):
        if (top / "images").exists() and (top / "labels").exists():
            continue
        img_count = sum(1 for f in top.rglob("*") if f.is_file() and f.suffix.lower() in IMG_EXT)
        txt_count = sum(1 for f in top.rglob("*.txt") if f.is_file())
        if img_count > 0 and txt_count == 0:
            image_only_folders.append(str(top).replace("\\", "/"))
        elif img_count > 0 and txt_count > 0 and not (top / "images").exists():
            flat_labeled_folders.append(top)

    for ds in yolo_roots:
        pairs, issues = collect_pairs(ds)
        all_pairs.extend(pairs)
        per_dataset_issues[str(ds).replace("\\", "/")] = issues

    for flat_ds in flat_labeled_folders:
        pairs, issues = collect_flat_pairs(flat_ds)
        all_pairs.extend(pairs)
        per_dataset_issues[str(flat_ds).replace("\\", "/")] = issues

    # Duplicate detection:
    # - exact image hash
    # - filename + label hash
    by_img_hash: Dict[str, List[PairRecord]] = {}
    by_name_label: Dict[Tuple[str, str], List[PairRecord]] = {}
    for p in all_pairs:
        by_img_hash.setdefault(p.img_hash, []).append(p)
        by_name_label.setdefault((p.image.name.lower(), p.label_hash), []).append(p)

    duplicate_candidates: List[PairRecord] = []
    seen_hashes = set()
    canonical = str(CANONICAL_YOLO).replace("\\", "/")
    ordered = sorted(
        all_pairs,
        key=lambda r: (0 if r.dataset == canonical else 1, r.dataset, r.split, r.image.name.lower()),
    )
    for rec in ordered:
        if rec.img_hash in seen_hashes:
            duplicate_candidates.append(rec)
        else:
            seen_hashes.add(rec.img_hash)

    # Quarantine duplicates as COPIES (source preserved)
    quarantine_manifest = []
    for i, rec in enumerate(duplicate_candidates, 1):
        qstem = f"dup_{i:06d}_{Path(rec.image.name).stem}"
        qimg = QUARANTINE_DIR / "images" / f"{qstem}{rec.image.suffix.lower()}"
        qlbl = QUARANTINE_DIR / "labels" / f"{qstem}.txt"
        safe_copy(rec.image, qimg)
        safe_copy(rec.label, qlbl)
        quarantine_manifest.append(
            {
                "source_dataset": rec.dataset,
                "source_split": rec.split,
                "source_image": str(rec.image).replace("\\", "/"),
                "source_label": str(rec.label).replace("\\", "/"),
                "quarantine_image": str(qimg).replace("\\", "/"),
                "quarantine_label": str(qlbl).replace("\\", "/"),
                "img_hash": rec.img_hash,
            }
        )

    # Build merged_pool from unique valid pairs only (no overwrite of raw datasets)
    merged_manifest = []
    merged_boxes = {0: 0, 1: 0, "other": 0}
    for i, rec in enumerate([r for r in ordered if r.img_hash in seen_hashes], 1):
        # Keep one unique pair by hash (first seen according to ordering).
        # Use deterministic destination names.
        if i > len(seen_hashes):
            break

    # deterministic unique pass
    used_hash = set()
    idx = 0
    for rec in ordered:
        if rec.img_hash in used_hash:
            continue
        used_hash.add(rec.img_hash)
        idx += 1
        stem = f"pool_{idx:06d}"
        dst_img = MERGED_POOL_DIR / "images_all" / f"{stem}{rec.image.suffix.lower()}"
        dst_lbl = MERGED_POOL_DIR / "labels_all" / f"{stem}.txt"
        safe_copy(rec.image, dst_img)
        # normalize class IDs: keep 0/1 and drop other classes
        out_lines = []
        for ln in rec.label.read_text(encoding="utf-8", errors="ignore").splitlines():
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            pr = s.split()
            if len(pr) != 5:
                continue
            try:
                c = int(pr[0])
                x, y, w, h = map(float, pr[1:])
            except Exception:
                continue
            if c not in (0, 1):
                merged_boxes["other"] += 1
                continue
            if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1):
                continue
            merged_boxes[c] += 1
            out_lines.append(f"{c} {x:.6f} {y:.6f} {w:.6f} {h:.6f}")
        dst_lbl.write_text("\n".join(out_lines) + ("\n" if out_lines else ""), encoding="utf-8")
        merged_manifest.append(
            {
                "source_dataset": rec.dataset,
                "source_split": rec.split,
                "source_image": str(rec.image).replace("\\", "/"),
                "source_label": str(rec.label).replace("\\", "/"),
                "merged_image": str(dst_img).replace("\\", "/"),
                "merged_label": str(dst_lbl).replace("\\", "/"),
                "img_hash": rec.img_hash,
            }
        )

    report = {
        "top_level_folders": [p.name for p in sorted(ROOT.iterdir()) if p.is_dir()],
        "yolo_roots": [str(p).replace("\\", "/") for p in yolo_roots],
        "image_only_folders": image_only_folders,
        "flat_labeled_folders": [str(p).replace("\\", "/") for p in flat_labeled_folders],
        "dataset_inventory": per_dataset_issues,
        "duplicates": {
            "exact_image_hash_groups": sum(1 for v in by_img_hash.values() if len(v) > 1),
            "exact_image_duplicate_files": len(duplicate_candidates),
            "filename_plus_labelhash_groups": sum(1 for v in by_name_label.values() if len(v) > 1),
            "quarantine_copied": len(quarantine_manifest),
        },
        "class_distribution_merged_pool_boxes": merged_boxes,
        "manifests": {
            "quarantine_manifest": str(QUARANTINE_DIR / "manifest.json").replace("\\", "/"),
            "merged_pool_manifest": str(MERGED_POOL_DIR / "manifest.json").replace("\\", "/"),
        },
    }

    (QUARANTINE_DIR / "manifest.json").write_text(json.dumps(quarantine_manifest, indent=2), encoding="utf-8")
    (MERGED_POOL_DIR / "manifest.json").write_text(json.dumps(merged_manifest, indent=2), encoding="utf-8")
    (MERGED_POOL_DIR / "audit_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
