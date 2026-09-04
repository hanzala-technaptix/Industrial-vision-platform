"""Use case 05 — Quality defect (static image gallery for now).

Reads sample images from test-images/quality/{good,defect}/ and shows each
labeled. Real defect model plugs in here later without changing the CLI.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from demos._paths import REPO_ROOT


def run(argv: list[str] | None = None) -> int:
    images_dir = REPO_ROOT / "test-images" / "quality"
    ap = argparse.ArgumentParser(description="Quality defect (static images)")
    ap.add_argument("--dir", default=str(images_dir),
                    help="Folder with good/ and defect/ subfolders")
    args = ap.parse_args(argv)

    root = Path(args.dir)
    good = sorted((root / "good").glob("*")) if (root / "good").exists() else []
    defect = sorted((root / "defect").glob("*")) if (root / "defect").exists() else []
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    images = [(p, "GOOD") for p in good if p.suffix.lower() in exts]
    images += [(p, "DEFECT") for p in defect if p.suffix.lower() in exts]

    if not images:
        print("[quality_defect] No sample images found.")
        print(f"  Add images under: {root / 'good'}  and  {root / 'defect'}")
        print("  (Not bundled — add MVTec or factory samples when ready.)")
        return 1

    print("[quality_defect] Press any key for next image, q or ESC to quit.")
    for path, label in images:
        img = cv2.imread(str(path))
        if img is None:
            continue
        color = (0, 255, 0) if label == "GOOD" else (0, 0, 255)
        cv2.putText(img, f"Label: {label}", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 2)
        cv2.putText(img, path.name, (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        cv2.imshow("Quality Defect", img)
        key = cv2.waitKey(0) & 0xFF
        if key in (ord("q"), 27):
            break
    cv2.destroyAllWindows()
    return 0
