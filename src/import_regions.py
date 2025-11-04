import os
import shutil
import stat # Required for handle_remove_read_only
from pathlib import Path
# Removed: from PIL import Image, ImageDraw, ImageFont (No longer needed)

# --- Configuration ---
SOURCE_DIR = Path("./public_data_sources/regions")
OUTPUT_DIR = Path("./public/img/regions")
# Removed: IMAGE_SIZE = (50, 50)
SUPPORTED_FORMATS = ['.png', '.jpg', '.jpeg', '.svg'] # Added SVG as it's often used for flags

def handle_remove_read_only(func, path, exc_info):
    """Error handler for shutil.rmtree on Windows read-only files"""
    if func in (os.rmdir, os.remove, os.unlink):
        try:
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            func(path)
        except Exception as e:
            raise e
    else:
        # Re-raise the exception if the issue was not permissions
        raise exc_info[1]

# Removed: process_region_image function

def import_regions():
    print("=" * 80)
    print("REGION IMAGE IMPORTER (Direct Copy - No Resizing)")
    print("=" * 80)

    if not SOURCE_DIR.exists():
        print(f"Error: Source directory not found at {SOURCE_DIR}. Skipping region import.")
        return

    # Clean output directory
    print("Cleaning output directory...")
    if OUTPUT_DIR.exists():
        try:
            shutil.rmtree(OUTPUT_DIR, onerror=handle_remove_read_only)
            print(f"Successfully deleted {OUTPUT_DIR}")
        except Exception as e:
            print(f"Error deleting directory {OUTPUT_DIR}: {e}")
            
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created {OUTPUT_DIR}")
    print()

    print("Copying region images (preserving original quality)...")
    processed_count = 0
    skipped_count = 0

    # Iterate through all files in the source directory
    for file_path in SOURCE_DIR.iterdir():
        if not file_path.is_file():
            continue
            
        # Check if the file extension is supported
        if file_path.suffix.lower() in SUPPORTED_FORMATS:
            dest_path = OUTPUT_DIR / file_path.name # Preserve original filename and extension
            try:
                # Use shutil.copy2 to copy the file, preserving metadata (like timestamps)
                shutil.copy2(file_path, dest_path)
                print(f"  ✅ Copied: {file_path.name}")
                processed_count += 1
            except Exception as e:
                print(f"  ❌ Error copying file {file_path.name}: {e}")
                skipped_count += 1
        else:
            print(f"  ⚠ Skipping unsupported file: {file_path.name}")
            skipped_count += 1

    print("-" * 80)
    print(f"Total images copied: {processed_count}")
    if skipped_count > 0:
        print(f"Total items skipped/failed: {skipped_count}")
    print(f"Images saved to: {OUTPUT_DIR}")
    print("=" * 80)

def main():
    # Region image processing is independent of the Flask app context
    import_regions()

if __name__ == "__main__":
    import_regions()
