import os
import hashlib
from pathlib import Path
from collections import defaultdict
from datetime import datetime

def get_file_hash(filepath):
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                h.update(chunk)
    except FileNotFoundError:
        return None
    return h.hexdigest()

def scan_models(base_dir):
    """Scan directories for .pt files."""
    target_dirs = ['runs', 'models', 'weights']
    model_files = []
    
    for d in target_dirs:
        dir_path = base_dir / d
        if dir_path.exists() and dir_path.is_dir():
            model_files.extend(list(dir_path.rglob("*.pt")))
            
    return model_files

def main():
    base_dir = Path(__file__).resolve().parent.parent
    print(f"Scanning for models in {base_dir} (runs/, models/, weights/)...")
    
    model_files = scan_models(base_dir)
    print(f"Found {len(model_files)} .pt files.")
    
    # Dictionary to group models by hash
    hash_map = defaultdict(list)
    
    for filepath in model_files:
        file_size = os.path.getsize(filepath)
        # Skip empty files
        if file_size == 0:
            continue
            
        file_hash = get_file_hash(filepath)
        if file_hash:
            # Store tuple of (filepath, modification_time)
            mtime = os.path.getmtime(filepath)
            hash_map[file_hash].append((filepath, mtime, file_size))
            
    print("\n--- Duplicate Analysis ---")
    duplicate_groups = {h: files for h, files in hash_map.items() if len(files) > 1}
    
    if not duplicate_groups:
        print("No duplicate models found.")
        return

    print(f"Found {len(duplicate_groups)} groups of duplicate models.\n")
    
    for h, files in duplicate_groups.items():
        # Sort by modification time (descending), so the latest is first
        files.sort(key=lambda x: x[1], reverse=True)
        
        latest_file = files[0]
        redundant_files = files[1:]
        
        file_size_mb = latest_file[2] / (1024 * 1024)
        
        print(f"Duplicate Group (Hash: {h[:8]}..., Size: {file_size_mb:.2f} MB)")
        print(f"  [KEEP] Latest/Best Model: {latest_file[0].relative_to(base_dir)}")
        
        for r_file in redundant_files:
            print(f"  [DELETE SUGGESTION] Redundant Model: {r_file[0].relative_to(base_dir)}")
        print("-" * 40)
        
    print("\n[NOTE] This is a dry run. No files have been deleted.")
    print("To delete a file, you must do it manually or confirm.")

if __name__ == "__main__":
    main()
