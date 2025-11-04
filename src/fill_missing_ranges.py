# src/fill_missing_ranges.py

import sys
from pathlib import Path

# Add the parent directory to the path to import 'app' and its contents
sys.path.append(str(Path(__file__).parent.parent))

# Import the SQLAlchemy db object and models
from app import db
from app.models.country import Country
from app.models.wmi import WmiRegionCode # <-- Changed to the current model name

# Valid VIN characters in order (excluding I, O, Q)
VIN_CHARACTERS = [
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 
    'N', 'P', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'
]

def fill_missing_wmi_ranges():
    """Fill all missing WMI region code ranges with Unknown country"""
        
    print("\n📥 Filling missing WMI region code ranges...")
        
    try:
        # Get the "Unknown" country record (inserted by seed_countries.py using code 'XX')
        unknown_country = Country.query.filter_by(iso_alpha2='XX').first() 
        # Using iso_alpha2='XX' is more robust than common_name='Unknown'

        if not unknown_country:
            print("❌ Error: 'Unknown' country (XX) not found in database")
            print("   Make sure seed_countries() has run first")
            return

        # 1. Generate all possible 2-character codes
        all_possible_codes = []
        for first_char in VIN_CHARACTERS:
            for second_char in VIN_CHARACTERS:
                all_possible_codes.append(first_char + second_char)
                
        # 2. Get all existing codes from the WmiRegionCode table
        existing_codes = set(code.code for code in WmiRegionCode.query.all())
                
        # 3. Find missing codes
        missing_codes = set(all_possible_codes) - existing_codes

        if not missing_codes:
            print("✅ No missing codes found - all ranges are assigned!")
            return

        print(f"✓ Found {len(missing_codes)} missing codes")
        print("💾 Assigning to 'Unknown' country...")

        # Group by first character for display
        missing_by_first = {}
        for code in sorted(missing_codes):
            first = code[0]
            if first not in missing_by_first:
                missing_by_first[first] = []
            missing_by_first[first].append(code)

        inserted_count = 0
        
        # 4. Insert records for missing codes
        for first_char, codes in sorted(missing_by_first.items()):
            print(f"\n🔧 Filling range {first_char}: {len(codes)} codes")
            
            for code in codes:
                wmi_code = WmiRegionCode( # <-- Use the correct model
                    code=code,
                    country_id=unknown_country.id
                )
                db.session.add(wmi_code)
                inserted_count += 1
                
        # 5. Commit all changes
        db.session.commit()

        print("\n" + "="*60)
        print(f"✅ Successfully filled {inserted_count} missing codes!")
        print(f"   All {len(all_possible_codes)} WMI codes are now assigned.")
        print("="*60)
            
    except Exception as e:
        print(f"❌ Error filling missing ranges: {e}")
        db.session.rollback()
        # Optional: re-raise if this is running in a critical path
        # raise 
        
# Example of how to integrate this into your main runner:
# if __name__ == "__main__":
#     fill_missing_wmi_ranges()