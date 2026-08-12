from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Tuple

import cv2


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def iter_images(folder: Path) -> Iterable[Path]:
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
            yield p


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def rect_to_yolo(x: int, y: int, w: int, h: int, img_w: int, img_h: int) -> Tuple[float, float, float, float]:
    xc = (x + w / 2.0) / img_w
    yc = (y + h / 2.0) / img_h
    ww = w / img_w
    hh = h / img_h
    return (
        clamp(xc, 0.0, 1.0),
        clamp(yc, 0.0, 1.0),
        clamp(ww, 1e-6, 1.0),
        clamp(hh, 1e-6, 1.0),
    )


def write_label_file(path: Path, boxes: List[Tuple[float, float, float, float]], class_id: int) -> None:
    lines = [f"{class_id} {x:.6f} {y:.6f} {w:.6f} {h:.6f}" for x, y, w, h in boxes]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-label image-only no-mask folders with YOLO labels.")
    parser.add_argument(
        "--folders",
        nargs="+",
        default=["data/WithoutMask-Train", "data/WithoutMask-val", "data/WithoutMask-Test"],
        help="Folders containing images that should be labeled as class 0 (No-Mask).",
    )
    parser.add_argument("--class-id", type=int, default=0, help="YOLO class id for No-Mask.")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .txt files if they exist. Default is skip existing labels.",
    )
    parser.add_argument(
        "--fallback-center-box",
        action="store_true",
        help="If no face is detected, write one center box instead of empty label.",
    )
    args = parser.parse_args()

    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    if face_cascade.empty():
        raise RuntimeError("Failed to load OpenCV Haar cascade for face detection.")

    total_images = 0
    labeled_files = 0
    skipped_existing = 0
    unreadable = 0
    with_faces = 0
    no_faces = 0
    fallback_used = 0

    for folder_str in args.folders:
        folder = Path(folder_str)
        if not folder.exists():
            print(f"[WARN] Folder not found: {folder}")
            continue

        for img_path in iter_images(folder):
            total_images += 1
            label_path = img_path.with_suffix(".txt")
            if label_path.exists() and not args.overwrite:
                skipped_existing += 1
                continue

            img = cv2.imread(str(img_path))
            if img is None:
                unreadable += 1
                continue
            h, w = img.shape[:2]
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            faces = face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=4,
                minSize=(20, 20),
            )

            boxes: List[Tuple[float, float, float, float]] = []
            if len(faces) > 0:
                with_faces += 1
                for (x, y, fw, fh) in faces:
                    boxes.append(rect_to_yolo(int(x), int(y), int(fw), int(fh), w, h))
            else:
                no_faces += 1
                if args.fallback_center_box:
                    bw = int(w * 0.55)
                    bh = int(h * 0.65)
                    bx = int((w - bw) / 2)
                    by = int((h - bh) / 2)
                    boxes.append(rect_to_yolo(bx, by, bw, bh, w, h))
                    fallback_used += 1

            write_label_file(label_path, boxes, args.class_id)
            labeled_files += 1

    print("[DONE] Auto-label completed")
    print(f"total_images_seen={total_images}")
    print(f"labeled_files_written={labeled_files}")
    print(f"skipped_existing_labels={skipped_existing}")
    print(f"unreadable_images={unreadable}")
    print(f"images_with_face_detection={with_faces}")
    print(f"images_without_face_detection={no_faces}")
    print(f"fallback_center_box_used={fallback_used}")


if __name__ == "__main__":
    main()
