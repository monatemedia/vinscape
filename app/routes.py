# app/routes.py
from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from app import db # Import the database object initialized in __init__.py
from app.models.country import Country
from app.models.wmi_region import WmiRegion # Corrected model name
from app.models.wmi_factory import WmiFactory # Corrected model name
from app.models.factory_logo import FactoryLogo # New logo model
from sqlalchemy import text, func, select
from sqlalchemy.orm import joinedload 
import random
from datetime import datetime
import os
import sys
import re

# Define a Blueprint for organization
bp = Blueprint('main', __name__)

# --- VIN CONSTANTS (Same as before) ---
VIN_LENGTH = 17
INVALID_CHARS = ['I', 'O', 'Q']
VIN_CHARACTERS = 'ABCDEFGHJKLMNPRSTUVWXYZ0123456789'
DIGITS = '0123456789'
TRANSLITERATION = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
    'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
    'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
    '0': 0, '1': 1, '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9
}
WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]
MODEL_YEARS = {
    'A': 2010, 'B': 2011, 'C': 2012, 'D': 2013, 'E': 2014, 'F': 2015,
    'G': 2016, 'H': 2017, 'J': 2018, 'K': 2019, 'L': 2020, 'M': 2021,
    'N': 2022, 'P': 2023, 'R': 2024, 'S': 2025, 'T': 2026, 'V': 2027,
    'W': 2028, 'X': 2029, 'Y': 2030, '1': 2031, '2': 2032, '3': 2033,
    '4': 2034, '5': 2035, '6': 2036, '7': 2037, '8': 2038, '9': 2039
}
# --- END VIN CONSTANTS ---


# --- VIN UTILITY FUNCTIONS (Adapted to use current models) ---

def compute_check_digit(vin):
    """Compute VIN check digit"""
    total = sum(TRANSLITERATION.get(vin[i], 0) * WEIGHTS[i] for i in range(VIN_LENGTH))
    remainder = total % 11
    return 'X' if remainder == 10 else str(remainder)

def validate_check_digit(vin):
    """Validate VIN check digit"""
    computed = compute_check_digit(vin)
    return vin[8] == computed

def is_north_american(vin):
    """Check if VIN is from North America (1-5)"""
    return vin[0] in '12345'

def resolve_model_year(char):
    """Resolve model year with 30-year cycle"""
    base_year = MODEL_YEARS.get(char)
    if not base_year:
        return None
    current_year = datetime.now().year
    year = base_year
    if year < current_year - 30:
        year += 30
    return year if year <= current_year else None

def get_factory_logos(factory_id):
    """Get all logos for a factory using SQLAlchemy/FactoryLogo model"""
    logos = db.session.scalars(
        select(FactoryLogo.logo_filename).filter(FactoryLogo.factory_id == factory_id)
    ).all()
    return logos

# --- REGION MAPPING HELPERS ---

def map_vin_region_to_name(wmi_char):
    """Maps the first VIN character (WMI Region Code) to a standard region name."""
    # Based on ISO 3780
    mappings = {
        '1': 'North America', '2': 'North America', '3': 'North America',
        '4': 'North America', '5': 'North America',
        '6': 'Oceania', '7': 'Oceania',
        '8': 'South America', '9': 'South America',
        'J': 'Asia', 'K': 'Asia', 'L': 'Asia', 'M': 'Asia', 'N': 'Asia',
        'A': 'Africa', 'B': 'Africa',
        'S': 'Europe', 'T': 'Europe', 'U': 'Europe', 'V': 'Europe', 'W': 'Europe', 'X': 'Europe', 'Y': 'Europe', 'Z': 'Europe',
    }
    return mappings.get(wmi_char.upper(), 'Unknown')

def get_region_image_filename(region_name):
    """Converts a region name (e.g., 'North America') to a filename (e.g., 'north_america.png')."""
    if not region_name or region_name == 'Unknown':
        # Return a known placeholder filename if you have one, or None
        return None 
    
    # Convert "North America" -> "north_america.png"
    # Use re.sub to handle any non-alphanumeric characters just in case
    clean_name = re.sub(r'[^a-z0-9_]+', '', region_name.lower().replace(' ', '_'))
    return f'{clean_name}.png'

# --- END REGION MAPPING HELPERS ---


def decode_vin(vin):
    """Decode VIN using database"""
    vin = vin.upper().strip()

    # Basic validation
    if len(vin) != VIN_LENGTH:
        return {'error': f'VIN must be exactly {VIN_LENGTH} characters'}
    for char in INVALID_CHARS:
        if char in vin:
            return {'error': f'Invalid character "{char}" found'}
    if not all(c in VIN_CHARACTERS for c in vin):
        return {'error': 'VIN contains invalid characters'}

    # Check digit validation
    check_digit_valid = validate_check_digit(vin)
    if is_north_american(vin) and not check_digit_valid:
        return {'error': 'Check digit validation failed. This VIN is not valid.'}

    # Extract components
    wmi = vin[:3]
    region_code = vin[0]
    
    # 1. Manufacturer/Factory Lookup (WMI: first 3 characters)
    factory_entry = db.session.scalar(
        select(WmiFactory).filter_by(wmi=wmi).options(joinedload(WmiFactory.country))
    )
    
    # 2. General Region Info (Based on first VIN character using ISO 3780)
    general_region = map_vin_region_to_name(region_code)
    
    # Build initial result structure
    result = {
        'vin': vin,
        'wmi': wmi,
        'vds': vin[3:9],
        'vis': vin[9:17],
        'check_digit': vin[8],
        'check_digit_valid': check_digit_valid,
        'model_year_char': vin[9],
        'plant_code': vin[10],
        'serial_number': vin[11:17],
        
        # This is for the 'Region' box
        'region': general_region,
        'region_country': general_region, # Default country name is the region name
        'region_flag': get_region_image_filename(general_region) # Returns filename
    }

    # --- FACTORY/MANUFACTURER INFO (Based on 3-char WMI) ---
    if factory_entry:
        result['manufacturer'] = factory_entry.name 

        # 1. Determine Country/Flag for the specific Factory (WMI)
        if factory_entry.country:
            # Use Country entry linked to the WmiFactory
            factory_country_name = factory_entry.country.common_name
            factory_flag = factory_entry.country.flag_emoji
            factory_region = factory_entry.country.region 
            
            # This is also the best source for the main 'Country' field
            result['country'] = factory_country_name
            result['country_flag'] = factory_flag
            result['country_region'] = factory_region
            
        else:
            # Fallback if WmiFactory is found but not linked to a Country
            factory_country_name = factory_entry.region or 'Unknown Country'
            factory_flag = '🏭' # Placeholder
            factory_region = factory_entry.region or result.get('region', 'Unknown Factory Region')
            
            # Default the main 'Country' fields if no specific country link
            result['country'] = factory_country_name
            result['country_flag'] = factory_flag
            result['country_region'] = factory_region

        # ASSIGN FACTORY/WMI REGION FIELDS (The field you were debugging)
        result['factory_country'] = factory_country_name
        result['factory_flag'] = factory_flag
        result['factory_region'] = factory_region 
        
        # Get manufacturer logos
        logos = get_factory_logos(factory_id=factory_entry.id) 
        result['manufacturer_logos'] = logos if logos else []
        
    else:
        # Fallback for completely unknown WMI
        result['manufacturer'] = 'Unknown Manufacturer'
        result['manufacturer_logos'] = []
        
        # Set all factory-specific fields to Unknown
        result['factory_region'] = 'Unknown' 
        result['factory_country'] = 'Unknown'
        result['factory_flag'] = '🏳'
        
        # Default the main 'Country' fields to the general region lookup
        result['country'] = result.get('region_country', 'Unknown')
        result['country_flag'] = '🏳' # Use placeholder, not image filename
        result['country_region'] = result.get('region', 'Unknown')

    # Model year
    result['model_year'] = resolve_model_year(vin[9]) or 'Unknown'
    
    return result


def generate_vin():
    """Generate a random valid VIN"""
    # Get random factory
    factories = db.session.scalars(select(WmiFactory)).all()
    factory = random.choice(factories) if factories else None
    
    wmi = factory.wmi if factory else ''.join(random.choices(VIN_CHARACTERS, k=3))

    # VDS (positions 3-7)
    vds = ''.join(random.choices(VIN_CHARACTERS, k=5))

    # Model year (not in future)
    current_year = datetime.now().year
    valid_years = [k for k, v in MODEL_YEARS.items() if resolve_model_year(k) and resolve_model_year(k) <= current_year]
    model_year_char = random.choice(valid_years) if valid_years else 'L' # Fallback to L (2020)

    # Plant code
    plant_code = random.choice(VIN_CHARACTERS)

    # Serial number (6 digits)
    serial = ''.join(random.choices(DIGITS, k=6))

    # Build VIN with placeholder check digit
    vin_array = list(wmi + vds + '0' + model_year_char + plant_code + serial)

    # Compute and insert check digit
    check_digit = compute_check_digit(''.join(vin_array))
    vin_array[8] = check_digit

    return ''.join(vin_array)

# --- FLASK ROUTES ---

@bp.route('/')
def index():
    """Serve the main VIN Decoder/Generator page"""
    # Pass 'active_page' for navbar highlighting
    return render_template('index.html', active_page='decoder')

# --- NEW ROUTE ---
@bp.route('/factories')
def factories():
    """Serve the logo review/factories page"""
    # Pass 'active_page' for navbar highlighting
    return render_template('factories.html', active_page='factories')


# --- ASSET SERVING ROUTES ---

@bp.route('/img/logos/<path:filename>')
def serve_logo(filename):
    """Serve logos from the public/img/logos directory"""
    project_root = os.path.dirname(current_app.root_path)
    logo_dir = os.path.join(project_root, 'public', 'img', 'logos')
    return send_from_directory(logo_dir, filename)

@bp.route('/img/regions/<path:filename>')
def serve_region_image(filename):
    """Serve region images from the public/img/regions directory"""
    project_root = os.path.dirname(current_app.root_path)
    region_dir = os.path.join(project_root, 'public', 'img', 'regions')
    return send_from_directory(region_dir, filename)


# --- API ENDPOINTS ---

@bp.route('/api/decode', methods=['POST'])
def api_decode():
    """API endpoint for VIN decoding"""
    data = request.get_json()
    vin = data.get('vin', '')
    result = decode_vin(vin)
    return jsonify(result)

@bp.route('/api/generate', methods=['POST'])
def api_generate():
    """API endpoint for VIN generation"""
    vin = generate_vin()
    decoded = decode_vin(vin)
    return jsonify(decoded)

@bp.route('/api/factories/logos', methods=['GET'])
def api_factories_logos():
    """API endpoint for the factory review page"""
    query = text("""
        SELECT 
            wfc.id,
            wfc.wmi,
            wfc.name,
            COALESCE(c.common_name, wfc.region, 'Unknown') as country,
            GROUP_CONCAT(fl.logo_filename) as logos
        FROM wmi_factories wfc
        LEFT JOIN countries c ON wfc.country_id = c.id
        LEFT JOIN factory_logos fl ON wfc.id = fl.factory_id
        GROUP BY wfc.id
        ORDER BY wfc.name
    """)

    result = db.session.execute(query).fetchall()
    factories = []

    for row in result:
        factory_id, wmi, manufacturer, country, logos_str = row
        logos = logos_str.split(',') if logos_str else []

        factories.append({
            'id': factory_id,
            'wmi': wmi,
            'manufacturer': manufacturer,
            'country': country,
            'hasLogos': len(logos) > 0 and logos[0] != '',
            'logoCount': len(logos) if logos_str else 0,
            'logos': logos if logos_str else []
        })
    
    return jsonify(factories)

# This route was in your old file but the template wasn't provided.
# I'm keeping it, but linking it to the new factories.html for now.
@bp.route('/logo-review')
def logo_review():
    """Serve the logo review page"""
    # This just redirects to the /factories route
    from flask import redirect, url_for
    return redirect(url_for('main.factories'))