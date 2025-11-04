# src/wmi_factory_code_seeder.py

import json
import re
from pathlib import Path
from app import db # Import the SQLAlchemy db object
from app.models.country import Country
from app.models.wmi_factory import WmiFactory
from app.models.wmi_region import WmiRegion

# Configuration
FACTORY_DATA_FILE = Path("public_data_sources") / "wmi_factory_codes.json"

# Valid VIN characters in order (excluding I, O, Q)
VIN_CHARACTERS = [
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 
    'N', 'P', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'
]

# List of known regions for lookups
KNOWN_REGIONS = ['Africa', 'Asia', 'Europe', 'North America', 'South America', 'Oceania', 'Antarctica']


def expand_wmi_range(range_str):
    """
    Expand WMI range into individual 3-character codes.
    Examples: 'JHF-JHG', 'JH1-JH5', 'JHZ'
    """
    # ... (Logic remains identical)
    range_str = range_str.strip()
    codes = []
    
    # Handle range (e.g., "JHF-JHG")
    if '-' in range_str:
        start, end = range_str.split('-')
        start = start.strip()
        end = end.strip()
        
        if len(start) == 3 and len(end) == 3:
            prefix = start[:2]
            start_third = start[2]
            end_third = end[2]
            
            try:
                start_idx = VIN_CHARACTERS.index(start_third)
                end_idx = VIN_CHARACTERS.index(end_third)
                
                for i in range(start_idx, end_idx + 1):
                    codes.append(prefix + VIN_CHARACTERS[i])
            except ValueError:
                # Should not happen if data is clean
                print(f"⚠ Invalid character in range '{range_str}'")
        else:
            print(f"⚠ Invalid range format '{range_str}'")
    # Single 3-character code
    elif len(range_str) == 3:
        codes.append(range_str)
    else:
        print(f"⚠ Unknown WMI range format: '{range_str}'")
        
    return codes


def parse_complex_wmi(wmi_str):
    """
    Parse complex WMI strings with multiple ranges and codes.
    Example: 'JHF-JHG, JHL-JHN, JHZ, JH1-JH5'
    """
    # ... (Logic remains identical)
    all_codes = []
    
    # Split by comma
    parts = [p.strip() for p in wmi_str.split(',')]
    
    for part in parts:
        codes = expand_wmi_range(part)
        all_codes.extend(codes)
        
    return all_codes


def seed_wmi_factory_codes():
    """Seed WMI factory codes from JSON file"""

    print(f"\n📥 Loading WMI factory codes from {FACTORY_DATA_FILE}...")

    if not FACTORY_DATA_FILE.exists():
        print(f"❌ Error: {FACTORY_DATA_FILE} not found. Please run scrape_wmi_factories.py first.")
        return

    try:
        with open(FACTORY_DATA_FILE, "r", encoding="utf-8") as f:
            factory_data = json.load(f)

        print("✓ Loaded WMI factory codes data")
        print("💾 Processing and inserting into database...")

        inserted_count = 0
        updated_count = 0
        skipped_count = 0
        errors = []

        for entry in factory_data:
            wmi_raw = entry.get('WMI', '').strip()
            manufacturer = entry.get('Manufacturer', '').strip()

            if not manufacturer:
                error_msg = f"⚠ No manufacturer name for WMI: {wmi_raw}"
                errors.append(error_msg)
                skipped_count += 1
                continue

            # --- WMI Parsing Logic ---
            wmi_codes = []
            
            # Normalize common complex separators: convert spaces and forward slashes to commas for simpler handling
            wmi_normalized = wmi_raw.replace(' ', ',').replace('/', ',')
            
            # Split by comma (handles the original comma, and the new space/slash separators)
            parts = [p.strip() for p in wmi_normalized.split(',') if p.strip()]

            for part in parts:
                if len(part) == 3:
                    # Case: Single 3-character code (e.g., '1A4')
                    wmi_codes.append(part)
                elif re.match(r'[A-Z0-9]{3}-[A-Z0-9]{3}', part):
                    # Case: Standard 3-character range (e.g., '1A4-1A8')
                    wmi_codes.extend(expand_wmi_range(part))
                elif len(part) == 2:
                    # ⭐ NEW LOGIC: Handle 2-Character Block (e.g., 'KL' -> 'KLA-KL0')
                    prefix = part
                    range_str = f"{prefix}{VIN_CHARACTERS[0]}-{prefix}{VIN_CHARACTERS[-1]}"
                    wmi_codes.extend(expand_wmi_range(range_str))
                else:
                    error_msg = f"⚠ Invalid WMI format (not 2 or 3 chars, not a range): '{wmi_raw}'"
                    errors.append(error_msg)
                    
            if not wmi_codes:
                # Only report error if the original raw string wasn't empty and failed to produce codes
                if wmi_raw:
                    error_msg = f"⚠ No valid codes generated from: '{wmi_raw}'"
                    errors.append(error_msg)
                continue

            # --- Processing Each 3-Character WMI Code ---
            for wmi in wmi_codes:
                if len(wmi) != 3:
                    errors.append(f"⚠ Invalid WMI code length after generation: '{wmi}'")
                    continue

                # Extract first 2 characters (WMI region code)
                region_code = wmi[:2]

                # Find the country/region entry using the WmiRegionCode lookup
                wmi_region_entry = WmiRegion.query.filter_by(code=region_code).first()

                country_id = None
                region_name = None
                country_display_name = "Unknown"

                if wmi_region_entry:
                    country_obj = wmi_region_entry.country
                    country_display_name = country_obj.common_name

                    # Determine if the 2-char code maps to a country or a general region
                    if country_display_name in KNOWN_REGIONS:
                        region_name = country_display_name
                    else:
                        country_id = country_obj.id # Link the manufacturer to the Country record

                # Check if this WMI already exists (Manufacturer.wmi is unique)
                existing = WmiFactory.query.filter_by(wmi=wmi).first()

                if existing:
                    # MERGE LOGIC: Combine manufacturer names if they differ
                    if manufacturer not in existing.name:
                        existing.name = f"{existing.name} & {manufacturer}"
                        db.session.add(existing)
                        location = existing.country.common_name if existing.country else existing.region or "Unknown"
                        print(f"  ⟳ Updated {wmi} -> {existing.name[:50]}... ({location})")
                        updated_count += 1
                    else:
                        skipped_count += 1
                    continue

                # Create new Manufacturer record
                factory_code = WmiFactory(
                    wmi=wmi,
                    name=manufacturer,
                    country_id=country_id, # Foreign key to Country
                    region=region_name # String name of the region
                )

                db.session.add(factory_code)
                location = country_display_name if country_display_name else region_name or "No Region/Country"

                # Print status only for new records
                print(f"  ✓ {wmi} -> {manufacturer[:50]}... ({location})")
                inserted_count += 1

        # Commit all changes
        db.session.commit()

        print("="*60)
        print(f"✅ Successfully seeded {inserted_count} WMI factory codes!")
        print(f"⟳ Updated {updated_count} existing codes with merged manufacturers")
        print(f"⊘ Skipped {skipped_count} entries")

        if errors:
            print(f"\n⚠ {len(errors)} errors encountered:")
            for error in errors[:10]:
                print(f"  {error}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
            print("="*60)

    except FileNotFoundError:
        print(f"❌ Error: {FACTORY_DATA_FILE} not found")
        print("Please make sure the file exists in the public_data_sources directory")
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        db.session.rollback()
    except Exception as e:
        print(f"❌ Error processing data: {e}")
        db.session.rollback()
        raise