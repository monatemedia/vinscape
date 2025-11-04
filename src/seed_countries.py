# src/seed_countries.py

import os
import json
import requests
# REMOVED: import sqlite3
from pathlib import Path
from flask import current_app

# ASSUMED IMPORTS: Import the SQLAlchemy db object and the Country model
# This requires the Flask app context to be active when 'main()' is called.
from app import db 
from app.models.country import Country 

# Configuration
DATA_DIR = Path("public_data_sources")
COUNTRIES_FILE = DATA_DIR / "countries.json"
# REMOVED: DB_PATH - handled by Flask-SQLAlchemy configuration
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
    """Map region names to standardized values"""
    region_mapping = {
        'Africa': 'Africa',
        # Updated to be consistent with the logic in scrape_wmi_regions.py and new seeder
        'Americas': 'North America' if subregion in ['Northern America', 'Central America', 'Caribbean'] else 'South America',
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

# REMOVED: create_database function. Database setup is now handled by the Flask app.

def seed_countries(countries_data):
    """Seed countries into database using SQLAlchemy models"""
    print(f"\n💾 Processing and inserting {len(countries_data)} countries...")
        
    inserted_count = 0
    skipped_count = 0
    
    # Use a set for faster lookup of existing ISO alpha-2 codes
    existing_isos = {c.iso_alpha2 for c in Country.query.with_entities(Country.iso_alpha2).all()}
        
    try:
        for country_data in countries_data:
            iso_alpha2 = country_data.get('cca2')

            if not iso_alpha2:
                print(f"⚠ Skipping country without ISO Alpha-2 code")
                skipped_count += 1
                continue

            # Check if country already exists
            if iso_alpha2 in existing_isos:
                skipped_count += 1
                continue

            # Prepare country data
            name_data = country_data.get('name', {})
            official_name = name_data.get('official', name_data.get('common'))
            common_name = name_data.get('common')
            region = map_region(country_data.get('region'), country_data.get('subregion'))

            # Create and insert country object
            country = Country(
                iso_alpha2=iso_alpha2,
                iso_alpha3=country_data.get('cca3'),
                iso_numeric=country_data.get('ccn3'),
                name=official_name,
                common_name=common_name,
                region=region,
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
        if 'XX' not in existing_isos:
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
        print(f"✅ Successfully seeded {inserted_count} countries!")
        print(f"⊘ Skipped {skipped_count} existing countries")
        print("=" * 50)
        
        return inserted_count
        
    except Exception as e:
        db.session.rollback()
        raise e

# REMOVED: verify_seeding function, as it's cleaner to handle DB stats elsewhere.

def main():
    """Main execution function"""
    print("🚀 Starting countries data seeding process...\n")
        
    try:
        # Step 1: Download or load countries data
        countries_data = download_countries()
        
        # NOTE: Database creation and table setup (db.create_all()) 
        # must happen before this point, likely in the main runner script.
        
        # Step 2: Seed countries
        seed_countries(countries_data)
        
        # REMOVED: verify_seeding(conn) and conn.close()
        
        print("\n🎉 All done! Countries seeded successfully.")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        # The main runner script should catch and handle final errors
        raise

if __name__ == "__main__":
    # NOTE: In a real project, this block should not run directly 
    # unless it manually sets up the Flask application context.
    print("⚠️ Warning: Run this script via your main seeder runner (e.g., main.py)")
    main()