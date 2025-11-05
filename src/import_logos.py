# src/import_logos.py
import os
import re
import shutil
import stat
import subprocess
import sys
import json
from PIL import Image
from pathlib import Path

# --- Flask/SQLAlchemy Imports ---
from app import db, create_app
from app.models.wmi_factory import WmiFactory
from app.models.factory_logo import FactoryLogo

# --- Configuration ---
LOGOS_DIR = Path("./public_data_sources/brands") # New project path
OUTPUT_DIR = Path("./public/img/logos")
THUMBNAIL_HEIGHT = 100
SUPPORTED_FORMATS = ['.png', '.jpg', '.jpeg', '.svg']

# --- ALIAS DEFINITIONS ---
# Maps the primary normalized brand name (derived from the file name, e.g., 'general motors'
# from 'general_motors.png') to a list of its normalized aliases.
BRAND_ALIASES = {
    "general motors": ["gm"],
    "volkswagen": ["vw"],
    # Added alias for International Trucks to cover the 'incomplete bus' variation
    "international trucks": ["international incomplete bus"],
}

# --- UTILITY FUNCTIONS (SVG conversion, name normalization, matching) ---
def check_svg_converter():
    """Check which SVG converter is available"""
    # ... (Function body remains the same)
    converters = {
        'cairosvg': False,
        'inkscape': False,
        'imagemagick': False
    }
    # Check for cairosvg
    try:
        import cairosvg
        converters['cairosvg'] = True
        return 'cairosvg', converters
    except (ImportError, OSError):
        pass
    # Check for Inkscape
    try:
        result = subprocess.run(['inkscape', '--version'],
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            converters['inkscape'] = True
            return 'inkscape', converters
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    # Check for ImageMagick
    try:
        result = subprocess.run(['magick', '--version'],
                               capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            converters['imagemagick'] = True
            return 'imagemagick', converters
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None, converters

def normalize_name(name):
    """
    Normalize a name for comparison.
    Crucially, it converts common delimiters (including hyphens) to spaces
    to ensure multi-word and hyphenated brands match correctly.
    """
    # 1. Remove boilerplate words.
    # The word 'trucks' was removed as it led to false positives when a brand name 
    # included a specific model/company name that ended in 'international'.
    name = re.sub(r'\b(ltd|limited|inc|incorporated|corp|corporation|gmbh|ag|sa|pty|llc|co|auto|cars|suv|plant|joint venture|export)\b', '', name, flags=re.IGNORECASE)

    name = name.lower()

    # 2. Replace common brand delimiters (/, &, ,) and HYPHENS (-) with a space.
    # This allows 'harley-davidson' and 'harley davidson' to both normalize to 'harley davidson'.
    name = re.sub(r'[/\,&-]', ' ', name)

    # 3. Remove any remaining non-alphanumeric characters (except spaces)
    name = re.sub(r'[^a-z0-9\s]', '', name)

    # 4. Clean up multiple spaces
    name = ' '.join(name.split())
    return name

def get_logo_files():
    """Get all logo files from the logos directory and calculate their aliases"""
    if not LOGOS_DIR.exists():
        print(f"Error: Logos directory not found at {LOGOS_DIR}")
        return []
    logo_files = []
    for ext in SUPPORTED_FORMATS:
        for file_path in LOGOS_DIR.glob(f'*{ext}'):
            file = file_path.name
            brand_name = file[:file.rfind('.')].replace('_', ' ')
            logo_normalized = normalize_name(brand_name)
            
            # Determine all names (primary + aliases) to search for
            aliases = BRAND_ALIASES.get(logo_normalized, [])
            all_search_terms = [logo_normalized] + aliases

            logo_files.append({
                'filename': file,
                'brand_name': brand_name,
                'normalized': logo_normalized,
                'aliases': all_search_terms, # This list contains the primary name and all aliases
                'extension': ext
            })
    return logo_files

def get_all_factories():
    """Get all factories from the database using SQLAlchemy"""
    factories = WmiFactory.query.with_entities(WmiFactory.id, WmiFactory.name).all()

    return [
        {
            'id': f_id,
            'name': name,
            'normalized': normalize_name(name)
        }
        for f_id, name in factories
    ]

def find_matches(logos, factories):
    """
    Find matches between logos and factories.
    Matches are found if the factory name contains the logo's primary name
    OR any of its defined aliases, preventing duplicate matches for the same brand.
    """
    all_mappings = {}
    match_count = 0
    for logo in logos:
        # Check if the logo has any search terms (primary name + aliases)
        if not logo['aliases']:
            continue

        for factory in factories:
            factory_normalized = factory['normalized']
            factory_matched = False

            if not factory_normalized:
                continue
            
            # Iterate through all aliases (including the primary name itself)
            for search_term in logo['aliases']:
                if not search_term:
                    continue
                    
                logo_words = search_term.split()

                # Case 1: Single-word search term (e.g., 'ford', or 'gm')
                if len(logo_words) == 1:
                    # Must be exact standalone word.
                    strict_word_pattern = re.compile(
                        r'\b' + re.escape(search_term) + r'\b'
                    )
                    if re.search(strict_word_pattern, factory_normalized):
                        factory_matched = True
                        break # Found a match, move to adding the mapping

                # Case 2: Multi-word search term (e.g., 'international trucks', 'general motors')
                else:
                    # Must check for the full, contiguous phrase surrounded by word boundaries.
                    strict_phrase_pattern = re.compile(
                        r'\b' + re.escape(search_term) + r'\b'
                    )
                    if re.search(strict_phrase_pattern, factory_normalized):
                        factory_matched = True
                        break # Found a match, move to adding the mapping

            if factory_matched:
                # Add the mapping only once, using the primary logo information
                if factory['id'] not in all_mappings:
                    all_mappings[factory['id']] = []
                # Check for uniqueness based on the logo's primary information
                if logo not in all_mappings[factory['id']]:
                    all_mappings[factory['id']].append(logo)
                    match_count += 1

    return all_mappings, match_count

# --- Image Conversion Functions ---
# NOTE: The three conversion functions (convert_svg_cairosvg, convert_svg_inkscape,
# convert_svg_imagemagick) and handle_remove_read_only are copied exactly below
# for brevity and since they don't involve database or model changes.
def convert_svg_cairosvg(svg_path, png_path, height):
    """Convert SVG using cairosvg"""
    try:
        import cairosvg
        cairosvg.svg2png(url=str(svg_path), write_to=str(png_path), output_height=height, unsafe=True)
        return True
    except Exception as e:
        print(f"  cairosvg error: {e}")
        return False

def convert_svg_inkscape(svg_path, png_path, height):
    """Convert SVG using Inkscape"""
    try:
        result = subprocess.run([
            'inkscape',
            str(svg_path),
            '--export-type=png',
            f'--export-height={height}',
            f'--export-filename={str(png_path)}'
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and png_path.exists()
    except Exception as e:
        print(f"  Inkscape error: {e}")
        return False

def convert_svg_imagemagick(svg_path, png_path, height):
    """Convert SVG using ImageMagick"""
    try:
        # Calculate DPI for desired height (assuming 96 DPI base)
        dpi = int(height * 96 / 100)  # Approximate
        result = subprocess.run([
            'magick',
            'convert',
            '-density', str(dpi),
            '-background', 'none',
            str(svg_path),
            '-resize', f'x{height}',
            str(png_path)
        ], capture_output=True, text=True, timeout=30)
        return result.returncode == 0 and png_path.exists()
    except Exception as e:
        print(f"  ImageMagick error: {e}")
        return False

def create_thumbnail(source_path, dest_path, source_extension, svg_converter=None):
    """Create a thumbnail of the logo"""
    try:
        resolved_source_path = Path(source_path).resolve()
        dest_path = Path(dest_path).with_suffix('.png')
        # Handle SVG files
        if source_extension.lower() == '.svg':
            if svg_converter == 'cairosvg':
                return convert_svg_cairosvg(resolved_source_path, dest_path, THUMBNAIL_HEIGHT)
            elif svg_converter == 'inkscape':
                return convert_svg_inkscape(resolved_source_path, dest_path, THUMBNAIL_HEIGHT)
            elif svg_converter == 'imagemagick':
                return convert_svg_imagemagick(resolved_source_path, dest_path, THUMBNAIL_HEIGHT)
            else:
                print(f"  No SVG converter available for {source_path.name}")
                return False
        # Handle raster images
        with Image.open(resolved_source_path) as img:
            if img.mode != 'RGBA':
                if img.mode == 'RGB':
                    img = img.convert('RGBA')
                elif img.mode == 'P':
                    img = img.convert('RGBA')
                elif img.mode in ('L', 'LA'):
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGBA')
            aspect_ratio = img.width / img.height
            new_height = THUMBNAIL_HEIGHT
            new_width = int(new_height * aspect_ratio)
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            img.save(dest_path, 'PNG', optimize=True)
            return True
    except Exception as e:
        print(f"  Error creating thumbnail for {source_path}: {e}")
        return False

def handle_remove_read_only(func, path, exc_info):
    """Error handler for shutil.rmtree"""
    if func in (os.rmdir, os.remove, os.unlink):
        try:
            os.chmod(path, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            func(path)
        except Exception as e:
            raise e
    else:
        raise exc_info[1]

# --- Main Logic ---
def import_logos(app):
    """
    Main function to run logo processing and database insertion within
    the Flask application context.
    """
    with app.app_context():
        print("=" * 80)
        print("LOGO MATCHER AND THUMBNAIL GENERATOR")
        print("=" * 80)
        # Check for SVG converters
        svg_converter, available_converters = check_svg_converter()
        print("\nSVG Converter Status:")
        print(f"  cairosvg:    {'✓ Available' if available_converters['cairosvg'] else '✗ Not available'}")
        print(f"  Inkscape:    {'✓ Available' if available_converters['inkscape'] else '✗ Not available'}")
        print(f"  ImageMagick: {'✓ Available' if available_converters['imagemagick'] else '✗ Not available'}")
        if svg_converter:
            print(f"\nUsing: {svg_converter.upper()}")
            supported_msg = ', '.join(SUPPORTED_FORMATS)
        else:
            print("\nNo SVG converter available - SVG files will be skipped")
            print("\nTo enable SVG support:")
            print("  Option 1: Install GTK3 runtime, then: pip install cairosvg")
            print("  Option 2: Install Inkscape from https://inkscape.org")
            print("  Option 3: Install ImageMagick from https://imagemagick.org")
            supported_msg = ', '.join([f for f in SUPPORTED_FORMATS if f != '.svg'])
        print(f"\nSupported formats: {supported_msg}")
        print()
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
        # --- Setup Database (SQLAlchemy way) ---
        print("Setting up database...")
        # Drop the FactoryLogo table and recreate it
        FactoryLogo.__table__.drop(db.engine, checkfirst=True)
        FactoryLogo.__table__.create(db.engine)
        print("Dropped and recreated 'factory_logos' table")
        print()
        # Get logos and factories
        print("Loading logos...")
        logos = get_logo_files()
        print(f"Found {len(logos)} logos")
        # Show format breakdown
        format_counts = {}
        for logo in logos:
            ext = logo['extension']
            format_counts[ext] = format_counts.get(ext, 0) + 1

        if format_counts:
            print("Format breakdown:")
            for ext, count in sorted(format_counts.items()):
                status = "" if svg_converter or ext != '.svg' else " (will be skipped)"
                print(f"  {ext}: {count}{status}")
        print()
        print("Loading factories...")
        factories = get_all_factories()
        print(f"Found {len(factories)} factories")
        print()
        # Find matches
        print("Finding matches...")
        final_mappings, total_matches_count = find_matches(logos, factories)
        print(f"Found {total_matches_count} total logo-to-factory mappings across {len(final_mappings)} factories.")
        # ... (Print sample matches) ...
        if final_mappings:
            print("\nFirst 5 factories with matches:")
            print("-" * 80)
            for factory_id, logo_list in list(final_mappings.items())[:5]:
                factory_name = next((f['name'] for f in factories if f['id'] == factory_id), f"ID {factory_id}")
                logo_names = [logo['brand_name'] for logo in logo_list]
                print(f"  {factory_name[:50]:50} -> {', '.join(logo_names)}")
        print()
        # Create thumbnails
        print("Creating thumbnails and saving to database...")
        print("-" * 80)
        thumbnail_count = 0
        skipped_count = 0
        processed_logos = set()
        mappings_created = 0
        try:
            for factory_id, logo_list in final_mappings.items():
                for logo in logo_list:
                    logo_filename = logo['filename']

                    if logo_filename not in processed_logos:
                        # ... (Thumbnail generation logic remains the same) ...
                        source_path = LOGOS_DIR / logo_filename
                        output_filename_base = Path(logo_filename).stem
                        output_filename = output_filename_base + '.png'
                        dest_path = OUTPUT_DIR / output_filename

                        # Skip SVG if no converter
                        if logo['extension'] == '.svg' and not svg_converter:
                            skipped_count += 1
                            processed_logos.add(logo_filename)
                            continue
                        # Generate thumbnail
                        if create_thumbnail(str(source_path), str(dest_path), logo['extension'], svg_converter):
                            thumbnail_count += 1
                        else:
                            skipped_count += 1

                        processed_logos.add(logo_filename)

                    # Insert mapping into database
                    output_filename = Path(logo_filename).stem + '.png'
                    output_path = OUTPUT_DIR / output_filename

                    if output_path.exists():
                        # --- CRITICAL FIX: Check for existing mapping before inserting ---
                        # This avoids the IntegrityError entirely by skipping duplicates.
                        existing_mapping = db.session.scalar(
                            db.select(FactoryLogo).filter_by(
                                factory_id=factory_id,
                                logo_filename=output_filename
                            )
                        )

                        if not existing_mapping:
                            factory_logo = FactoryLogo(
                                factory_id=factory_id,
                                logo_filename=output_filename
                            )
                            db.session.add(factory_logo)
                            mappings_created += 1
                        # Commit all unique objects added in the loop
            db.session.commit()

        except Exception as e:
            # Note: We must re-import `sqlalchemy.exc` to handle a specific error,
            # but given the database is clean (recreated every run), the `db.select`
            # check should make this outer except unnecessary for IntegrityErrors.
            db.session.rollback()
            raise e
        print(f"Total unique thumbnails created: {thumbnail_count}")
        if skipped_count > 0:
            print(f"Total files skipped: {skipped_count}")
        print()
        # Summary
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total logos processed: {len(logos)}")
        print(f"Factories with matches: {len(final_mappings)} / {len(factories)} ({len(final_mappings)/len(factories)*100:.1f}%)")
        print(f"Total factory-logo mappings created: {mappings_created}")
        print()
        # Sample mappings
        print("Sample mappings (first 20):")
        print("-" * 80)
        # SQLAlchemy Query for verification
        sample_logos = db.session.query(WmiFactory.name, FactoryLogo.logo_filename). \
            join(FactoryLogo, WmiFactory.id == FactoryLogo.factory_id). \
            limit(20).all()

        for manufacturer, logo in sample_logos:
            print(f"{manufacturer[:60]:60} -> {logo}")
        print()
        # Top logos
        print("Top 10 logos by number of factory matches:")
        print("-" * 80)
        # SQLAlchemy Query for verification
        top_logos = db.session.query(FactoryLogo.logo_filename, db.func.count(FactoryLogo.id)). \
            group_by(FactoryLogo.logo_filename). \
            order_by(db.func.count(FactoryLogo.id).desc()). \
            limit(10).all()

        for logo, count in top_logos:
            print(f"{logo:30} -> {count:4} factories")
        print()
        print("=" * 80)
        print(f"Thumbnails saved to: {OUTPUT_DIR}")
        print("Database table 'factory_logos' created and populated")
        print("=" * 80)
def main():
    # We need to create the app instance to run the logo import
    app = create_app()
    import_logos(app)

if __name__ == "__main__":
    main()
