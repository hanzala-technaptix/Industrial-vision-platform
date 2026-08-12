import argparse
import hashlib
import shutil
from pathlib import Path
import yaml


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _stable_stem(split: str, original_name: str) -> str:
    key = f"{split}:{original_name}"
    return hashlib.md5(key.encode("utf-8")).hexdigest()


def reconstruct_dataset(src_dir: Path, dest_dir: Path) -> None:
    src_dir = src_dir.resolve()
    dest_dir = dest_dir.resolve()
    
    if not src_dir.exists():
        print(f"Source directory {src_dir} not found. Please ensure download completed.")
        return

    print("Cleaning up old broken structure...")
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
        
    print("Rebuilding dataset in strict YOLO format...")
    
    split_stats = {}
    for split in ['train', 'valid', 'test']:
        src_split = src_dir / split
        if not src_split.exists():
            continue
            
        dest_split_name = 'val' if split == 'valid' else split
        
        dest_img_dir = dest_dir / 'images' / dest_split_name
        dest_lbl_dir = dest_dir / 'labels' / dest_split_name
        dest_img_dir.mkdir(parents=True, exist_ok=True)
        dest_lbl_dir.mkdir(parents=True, exist_ok=True)
        
        copied = 0
        skipped_missing_label = 0
        for file_path in src_split.glob("*"):
            if not file_path.is_file() or file_path.name.lower() == 'classes.txt':
                continue

            ext = file_path.suffix.lower()
            if ext not in IMAGE_EXTS:
                continue

            label_path = src_split / f"{file_path.stem}.txt"
            if not label_path.exists():
                skipped_missing_label += 1
                continue

            stable_stem = _stable_stem(dest_split_name, file_path.name)
            shutil.copy2(file_path, dest_img_dir / f"{stable_stem}{ext}")
            shutil.copy2(label_path, dest_lbl_dir / f"{stable_stem}.txt")
            copied += 1

        split_stats[dest_split_name] = {
            "copied_pairs": copied,
            "skipped_missing_label": skipped_missing_label,
        }

    print("Generating pure data.yaml...")
    yaml_content = {
        'path': str(dest_dir),
        'train': 'images/train',
        'val': 'images/val',
        'test': 'images/test' if (dest_dir / 'images' / 'test').exists() else '',
        'nc': 2,
        'names': {
            0: 'Person',
            1: 'Mask'
        }
    }
    
    # Remove empty test split if it doesn't exist
    if not yaml_content['test']:
        del yaml_content['test']

    with open(dest_dir / 'data.yaml', 'w', encoding="utf-8") as f:
        yaml.dump(yaml_content, f, sort_keys=False)

    print("Rebuild stats:", split_stats)
    print("✅ Dataset reconstruction complete!")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconstruct YOLO dataset with deterministic pair-safe naming.")
    parser.add_argument(
        "--source-images-dir",
        required=True,
        help="Path to source split directory containing train/valid/test files.",
    )
    parser.add_argument(
        "--dest-dir",
        default="data/face_mask",
        help="Destination directory for rebuilt dataset.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    reconstruct_dataset(Path(cli_args.source_images_dir), Path(cli_args.dest_dir))
