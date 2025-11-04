# src/wmi_region_code_seeder.py 

import json
from pathlib import Path

# Import the models and db session
from app import db
from app.models.country import Country
from app.models.wmi import WmiRegionCode 

# Configuration
WMI_DATA_FILE = Path("public_data_sources") / "wmi_region_codes.json"

# Valid VIN characters in order (excluding I, O, Q)
VIN_CHARACTERS = [
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M',
    'N', 'P', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'
]

# List of known regions
KNOWN_REGIONS = ['Africa', 'Asia', 'Europe', 'North America', 'South America', 'Oceania', 'Antarctica']

# NON-COLLIDING ISO PLACEHOLDER CODES FOR REGIONS
# Using '0' prefix to guarantee no collision with standard WMI/ISO codes.
# ISO Alpha 2 must be 2 chars, ISO Alpha 3 must be 3 chars.
REGION_CODE_MAP = {
    'Africa':        ('0A', '0AF'),      # 0-Africa
    'Asia':          ('0S', '0AS'),      # 0-Asia
    'Europe':        ('0E', '0EU'),      # 0-Europe (New unique codes: 0E / 0EU)
    'North America': ('0N', '0NA'),      # 0-North America
    'South America': ('0U', '0SA'),      # 0-South America (Using U to avoid clash with S)
    'Oceania':       ('0C', '0OC'),      # 0-Oceania
    'Antarctica':    ('0T', '0AN')       # 0-Antarctica
}

# ====================================================================
# NEW CONFIGURATION: MAPPING FOR INCONSISTENT COUNTRY/REGION NAMES
# Map names found in the WMI JSON data to the standardized names 
# used in the 'countries' database table.
# ====================================================================
NAME_MAPPING = {
    # WMI JSON Name  : Standardized DB Name
    "Turkey": "Türkiye",
    "Czech Republic": "Czechia",
    "Czechia": "Czech Republic", # If the JSON uses Czechia and the DB uses Czech Republic (Handle both ways)
    "SA": "South America" # Based on the error: ⚠ Country not found and not a known region: SA (range: 83)
}

def expand_range(range_str):
    """Expand a range string into individual 2-character codes."""
    range_str = range_str.strip()
    codes = []
    
    # ... (range expansion logic remains the same)
    if ',' in range_str:
        parts = [p.strip() for p in range_str.split(',')]
        for part in parts:
            codes.extend(expand_range(part))
        return codes

    if '-' in range_str:
        start, end = range_str.split('-')
        start = start.strip()
        end = end.strip()

        if len(start) == 2 and len(end) == 2:
            first_char = start[0]
            start_second = start[1]
            end_second = end[1]

            try:
                start_idx = VIN_CHARACTERS.index(start_second)
                end_idx = VIN_CHARACTERS.index(end_second)

                for i in range(start_idx, end_idx + 1):
                    codes.append(first_char + VIN_CHARACTERS[i])
            except ValueError as e:
                pass
        
    elif len(range_str) == 1:
        first_char = range_str
        for second_char in VIN_CHARACTERS:
            codes.append(first_char + second_char)

    elif len(range_str) == 2:
        codes.append(range_str)

    return codes

def find_or_create_region(location_name):
    """
    Finds a country/region by name or creates a new entry for a region.
    Returns the Country model instance or None.
    """
    # 1. Try to find the existing country/region
    country = Country.find_by_name(location_name)

    if country:
        return country

    # 2. If not found and it's a known region, create it
    if location_name in KNOWN_REGIONS:
        print(f"➕ Creating new region entry: {location_name}")
        
        # Get the non-colliding placeholder codes
        iso_a2_code, iso_a3_code = REGION_CODE_MAP.get(location_name)

        new_region = Country(
            iso_alpha2=iso_a2_code,
            iso_alpha3=iso_a3_code,
            iso_numeric='000',
            name=location_name,
            common_name=location_name,
            region=location_name,
            subregion=location_name,
            flag_emoji='🌐',
            is_active=True
        )
        db.session.add(new_region)
        
        # CRITICAL FIX: Commit the new region immediately so subsequent finds work.
        try:
            db.session.commit()
            return new_region
        except Exception as e:
            db.session.rollback()
            # If the commit fails due to IntegrityError, another process/autoflush 
            # beat us to it. We MUST assume it exists now and try to retrieve it.
            # No need for a print statement here, as it clutters the output.
            return Country.find_by_name(location_name) # This should succeed now.
        
    # 3. Not found and not a known region
    return None

def seed_wmi_region_codes():
    """Seed WMI region codes from JSON file using SQLAlchemy models"""
    
    print(f"\n📥 Loading WMI region codes from {WMI_DATA_FILE}...")
    
    if not WMI_DATA_FILE.exists():
        print(f"❌ Error: {WMI_DATA_FILE} not found. Please run scrape_wmi_regions.py first.")
        return

    try:
        with open(WMI_DATA_FILE, "r", encoding="utf-8") as f:
            wmi_data = json.load(f)

        print("✓ Loaded WMI region codes data")
        print("💾 Processing and inserting into database...")

        inserted_count = 0
        skipped_count = 0
        errors = []

        for entry in wmi_data:
            range_str = entry.get('range', '')
            location_name = entry.get('country', '')
            
            # ----------------------------------------------------
            # NEW: Normalize the name from the JSON data
            # ----------------------------------------------------
            # Use .get() to return the original name if no mapping is found.
            normalized_name = NAME_MAPPING.get(location_name, location_name)
            
            is_region = normalized_name in KNOWN_REGIONS

            # Find or create the Country/Region entry using the NORMALIZED name
            country_or_region = find_or_create_region(normalized_name)
            
            if not country_or_region:
                # Report the original location name for easier debugging of the JSON source
                error_msg = f"⚠ Country not found and not a known region: {location_name} (range: {range_str})"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            # Expand the range into individual codes
            codes = expand_range(range_str)
            
            if not codes:
                error_msg = f"⚠ No codes generated for range: {range_str}"
                print(error_msg)
                errors.append(error_msg)
                continue
            
            print(f"\n{'📍 Region' if is_region else '🌍 Country'}: {country_or_region.common_name}: {range_str} ({len(codes)} codes)")
            
            # Insert each code
            for code in codes:
                # Check if this code already exists for this country
                existing = WmiRegionCode.query.filter_by(
                    code=code,
                    country_id=country_or_region.id
                ).first()
                
                if existing:
                    skipped_count += 1
                    continue
                
                # Create new WMI region code
                wmi_code = WmiRegionCode(
                    code=code,
                    country=country_or_region
                )
                db.session.add(wmi_code)
                inserted_count += 1

        # Commit all changes (including new region entries and all WMI codes)
        db.session.commit()

        print("="*60)
        print(f"✅ Successfully seeded {inserted_count} WMI region codes!")
        print(f"⊘ Skipped {skipped_count} existing entries")

        if errors:
            print(f"\n⚠ {len(errors)} errors encountered:")
            for error in errors[:5]:
                print(f"  {error}")
            if len(errors) > 5:
                print(f"  ... and {len(errors) - 5} more")
        print("="*60)

    except json.JSONDecodeError as e:
        print(f"❌ Error parsing JSON: {e}")
        db.session.rollback()
        raise
    except Exception as e:
        print(f"❌ Error processing data: {e}")
        db.session.rollback()
        raise