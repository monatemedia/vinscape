import os
import json
import requests
from pathlib import Path
from flask import current_app
# ASSUMED IMPORTS: Import the SQLAlchemy db object and the Country model
from app import db 
from app.models.country import Country 

# Configuration
DATA_DIR = Path("public_data_sources")
COUNTRIES_FILE = DATA_DIR / "countries.json"
COUNTRIES_URL = "https://raw.githubusercontent.com/mledoze/countries/master/countries.json"

# Helper functions (kept identical)
def get_first_value(dict_obj):
    """Get first value from a dictionary (for currencies)"""
    if not dict_obj or not isinstance(dict_obj, dict):
        return None
    return next(iter(dict_obj.keys()), None)

def get_calling_code(idd_obj):
    """Extract calling code from IDD object"""
    if not idd_obj or not isinstance(idd_obj, dict):
        return None
        
    root = idd_obj.get('root', '')
    suffixes = idd_obj.get('suffixes', [])
        
    if root and suffixes:
        return f"{root}{suffixes[0]}"
    return root if root else None

def map_region(region, subregion):
    """
    Map region names to standardized values.
    
    FIXED: Added 'North America' to the subregion check list to correctly
    classify the United States.
    """
    region_mapping = {
        'Africa': 'Africa',
        # --- FIX APPLIED HERE ---
        # 'North America' subregion (used by US) is now correctly mapped.
        'Americas': 'North America' if subregion in ['Northern America', 'Central America', 'Caribbean', 'North America'] else 'South America',
        'Asia': 'Asia',
        'Europe': 'Europe',
        'Oceania': 'Oceania',
        'Antarctic': 'Antarctica'
    }
    return region_mapping.get(region, region)

def download_countries():
    """Download countries.json if it doesn't exist"""
    DATA_DIR.mkdir(exist_ok=True)
        
    if COUNTRIES_FILE.exists():
        print(f"✓ Countries file already exists: {COUNTRIES_FILE}")
        with open(COUNTRIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    print(f"📥 Downloading countries data from {COUNTRIES_URL}...")
    try:
        response = requests.get(COUNTRIES_URL, timeout=30)
        response.raise_for_status()
        countries = response.json()
                
        # Save to file
        with open(COUNTRIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(countries, f, indent=2, ensure_ascii=False)
                
        print(f"✓ Downloaded and saved {len(countries)} countries to {COUNTRIES_FILE}")
        return countries
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error downloading data: {e}")
        raise

def seed_countries(countries_data):
    """Seed countries into database using SQLAlchemy models"""
    print(f"\n💾 Processing and inserting {len(countries_data)} countries...")
        
    inserted_count = 0
    skipped_count = 0
    updated_count = 0

    # Use a set for faster lookup of existing ISO alpha-2 codes
    # Fetch all existing countries to determine if we insert or skip/update
    existing_countries = {c.iso_alpha2: c for c in Country.query.all()}
        
    try:
        for country_data in countries_data:
            iso_alpha2 = country_data.get('cca2')
            if not iso_alpha2:
                print(f"⚠ Skipping country without ISO Alpha-2 code")
                skipped_count += 1
                continue

            # Prepare common data used for both insert/update
            name_data = country_data.get('name', {})
            official_name = name_data.get('official', name_data.get('common'))
            common_name = name_data.get('common')
            region = map_region(country_data.get('region'), country_data.get('subregion'))

            # Check if country already exists
            if iso_alpha2 in existing_countries:
                country = existing_countries[iso_alpha2]
                
                # Special check for US: force region update if needed
                if iso_alpha2 == 'US' and country.region != region:
                    country.region = region
                    db.session.add(country)
                    print(f"  ⬆ Updated region for {common_name} to {region} (FIXED)")
                    updated_count += 1
                else:
                    skipped_count += 1
                continue

            # If country does not exist, insert it
            country = Country(
                iso_alpha2=iso_alpha2,
                iso_alpha3=country_data.get('cca3'),
                iso_numeric=country_data.get('ccn3'),
                name=official_name,
                common_name=common_name,
                region=region, # Uses the fixed region mapping
                subregion=country_data.get('subregion'),
                currency_code=get_first_value(country_data.get('currencies')),
                calling_code=get_calling_code(country_data.get('idd', {})),
                tld=country_data.get('tld', [None])[0],
                flag_emoji=country_data.get('flag'),
            )
            db.session.add(country)
            print(f"  ✓ {common_name}")
            inserted_count += 1
            
        # Add special "Unknown" country for unassigned/invalid VIN ranges
        if 'XX' not in existing_countries:
            unknown_country = Country(
                iso_alpha2='XX', 
                iso_alpha3='XXX', 
                iso_numeric='999', 
                name='Unknown', 
                common_name='Unknown',
                region='Unknown', 
                subregion='Unknown', 
                flag_emoji='🏳', 
            )
            db.session.add(unknown_country)
            print(f"  ✓ Unknown (special catch-all country)")
            inserted_count += 1
            
        db.session.commit()
                
        print("=" * 50)
        print(f"✅ Successfully seeded {inserted_count} new countries!")
        print(f"⬆ Updated {updated_count} existing countries (US region fix).")
        print(f"⊘ Skipped {skipped_count} existing/unspecified countries.")
        print("=" * 50)
                
        return inserted_count
            
    except Exception as e:
        db.session.rollback()
        raise e

def main():
    """Main execution function"""
    print("🚀 Starting countries data seeding process...\n")
            
    try:
        # Step 1: Download or load countries data
        countries_data = download_countries()
                
        # Step 2: Seed countries
        seed_countries(countries_data)
                
        print("\n🎉 All done! Countries seeded successfully.")
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise

if __name__ == "__main__":
    # NOTE: In a real project, this block should not run directly 
    # unless it manually sets up the Flask application context.
    print("⚠️ Warning: Run this script via your main seeder runner (e.g., main.py)")
    main()
