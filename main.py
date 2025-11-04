import sys
from pathlib import Path
import os
import sqlite3
from flask import Flask

# --- Configuration ---
# You'll need to define how to import your Flask application and database object.
# Assuming you have an __init__.py in your 'app' directory that initializes 'db'.
# We need to manually add the 'app' directory to the path for importing.
APP_DIR = Path(__file__).parent / "app"
sys.path.append(str(APP_DIR))

# Database configuration path (used for deletion/verification)
DB_PATH = Path(__file__).parent / "instance" / "vin.db"

# NOTE: The imports below assume you have defined 'create_app' 
# and that 'db' and your models are importable within the app context.
try:
    from app import create_app, db
    from app.models.country import Country 
    from app.models.wmi import WmiRegionCode
except ImportError as e:
    print(f"❌ Critical Error: Could not import app components. Ensure 'app' directory is set up correctly. Details: {e}")
    sys.exit(1)

# Add the 'src' directory to the Python path
sys.path.append(str(Path(__file__).parent / "src"))

# Import the main functions from your individual scripts
from src.seed_countries import main as seed_countries
from src.scrape_wmi_regions import main as scrape_regions
from src.wmi_region_code_seeder import seed_wmi_region_codes
from src.scrape_wmi_factories import main as scrape_factories
from src.fill_missing_ranges import fill_missing_wmi_ranges
from src.wmi_factory_code_seeder import seed_wmi_factory_codes

# ----------------------------------------------------------------------

def initialize_database(app: Flask):
    """Deletes old DB file and creates all tables defined by SQLAlchemy models."""
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"🗑️  Removed old database: {DB_PATH}")

    # Ensure the instance directory exists
    DB_PATH.parent.mkdir(exist_ok=True)
    
    with app.app_context():
        # This creates all tables from the imported models (Country, WmiRegionCode, etc.)
        db.create_all()
        print(f"✅ Created new database structure at: {DB_PATH}")

def run_all_scripts(app: Flask):
    """
    Executes all individual project scripts in a desired sequence within the 
    Flask application context.
    """
    print("✨ Starting the comprehensive data processing sequence...")
    
    # All database seeding logic MUST happen inside the application context
    with app.app_context():
        try:
            # 1. Run the Country Seeder (Downloads data, uses models to insert)
            print("\n--- Running Country Seeder ---")
            # NOTE: seed_countries should not take 'conn' anymore, just data.
            # It only needs the data as it uses db.session internally.
            seed_countries() 

            # 2. Run the Scrape WMI Regions Script (Writes data to JSON file)
            print("\n--- Running Scrape WMI Regions Script ---")
            scrape_regions() 

            # 3. Run the WMI Region Code Seeder (Reads JSON, uses models to insert)
            print("\n--- Running WMI Region Code Seeder ---")
            seed_wmi_region_codes() 

            # 4. Fill Missing WMI Ranges with 'Unknown' (New Step)
            print("\n--- Running Fill Missing Ranges Script ---")
            fill_missing_wmi_ranges() # <--- NEW EXECUTION

            # 5. Run the Scrape WMI Factory Script (Scrapes, uses models to insert)
            print("\n--- Running WMI Factory Scraper Script ---")
            scrape_factories() 

            # 6. Run the WMI Factory Code Seeder (Reads JSON, uses models to insert)
            print("\n--- Running WMI Factory Code Seeder ---")
            seed_wmi_factory_codes() 

            # Optional: Verify final count
            total_countries = Country.query.count()
            total_wmi_codes = WmiRegionCode.query.count()
            print("\n--- Database Verification ---")
            print(f"Total Countries/Regions in DB: {total_countries}")
            print(f"Total WMI Region Codes in DB: {total_wmi_codes}")


            print("\n✅ All scripts completed successfully!")
        
        except Exception as e:
            # Ensure any open transaction is rolled back on error
            db.session.rollback()
            print(f"\n❌ A script failed during execution: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    # 1. Create the Flask application instance
    app = create_app()

    # 2. Initialize the database (Drop old, create new tables)
    initialize_database(app)
    
    # 3. Run all seeders
    run_all_scripts(app)