# src/import_regions.py

import os
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# --- Configuration ---
SOURCE_DIR = Path("./public_data_sources/regions")
OUTPUT_DIR = Path("./public/img/regions")
IMAGE_SIZE = (50, 50)  # Standard size for small icons
SUPPORTED_FORMATS = ['.png', '.jpg', '.jpeg']

def handle_remove_read_only(func, path, exc_info):
    """Error handler for shutil.rmtree on Windows read-only files"""
    if func in (os.rmdir, os.remove, os.unlink):
        try:
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            func(path)
        except Exception as e:
            raise e
    else:
        raise exc_info[1]

def process_region_image(source_path, dest_path):
    """Opens an image, resizes it, and saves it as a 50x50 PNG."""
    try:
        with Image.open(source_path) as img:
            # Convert to RGBA to ensure transparency is preserved
            img = img.convert('RGBA')
            
            # Use thumbnail for a safe, in-place resize (preserving aspect ratio)
            # Then crop/pad to ensure it's exactly the desired size
            
            # 1. Resize while maintaining aspect ratio
            img.thumbnail(IMAGE_SIZE, Image.Resampling.LANCZOS)
            
            # 2. Create a new canvas with the desired size (transparent background)
            new_img = Image.new('RGBA', IMAGE_SIZE, (0, 0, 0, 0))
            
            # 3. Paste the resized image into the center of the new canvas
            x_offset = (IMAGE_SIZE[0] - img.width) // 2
            y_offset = (IMAGE_SIZE[1] - img.height) // 2
            new_img.paste(img, (x_offset, y_offset), img)

            # Save as PNG
            new_img.save(dest_path, 'PNG', optimize=True)
            return True
            
    except Exception as e:
        print(f"  Error processing image {source_path.name}: {e}")
        return False

def import_regions():
    print("=" * 80)
    print("REGION IMAGE IMPORTER AND OPTIMIZER")
    print("=" * 80)
    
    if not SOURCE_DIR.exists():
        print(f"Error: Source directory not found at {SOURCE_DIR}. Skipping region import.")
        return

    # Clean output directory
    print("Cleaning output directory...")
    if OUTPUT_DIR.exists():
        try:
            # Need to re-import stat for handle_remove_read_only if not at module level
            import stat 
            shutil.rmtree(OUTPUT_DIR, onerror=handle_remove_read_only)
            print(f"Successfully deleted {OUTPUT_DIR}")
        except Exception as e:
            print(f"Error deleting directory {OUTPUT_DIR}: {e}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created {OUTPUT_DIR}")
    print()

    print("Processing region images...")
    processed_count = 0
    skipped_count = 0
    
    for ext in SUPPORTED_FORMATS:
        for file_path in SOURCE_DIR.glob(f'*{ext}'):
            output_filename = file_path.stem + '.png'
            dest_path = OUTPUT_DIR / output_filename
            
            if process_region_image(file_path, dest_path):
                print(f"  ✅ Processed: {file_path.name} -> {output_filename}")
                processed_count += 1
            else:
                skipped_count += 1
    
    print("-" * 80)
    print(f"Total images processed: {processed_count}")
    if skipped_count > 0:
        print(f"Total images skipped/failed: {skipped_count}")
    print(f"Optimized images saved to: {OUTPUT_DIR}")
    print("=" * 80)

def main():
    # Region image processing is independent of the Flask app context
    import_regions()

if __name__ == "__main__":
    # Ensure PILLOW is installed: pip install Pillow
    import_regions()