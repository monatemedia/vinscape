# app/routes.py

from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app
from app import db # Import the database object initialized in __init__.py
from app.models.country import Country
from app.models.wmi_region import WmiRegion # Corrected model name
from app.models.wmi_factory import WmiFactory # Corrected model name
from app.models.factory_logo import FactoryLogo # New logo model
from sqlalchemy import text, func, select
import random
from datetime import datetime
import os
import sys

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
    
    # Use the FactoryLogo model and relationship rather than raw SQL text
    # This assumes the FactoryLogo model is imported and defined correctly.
    
    logos = db.session.scalars(
        select(FactoryLogo.logo_filename).filter(FactoryLogo.factory_id == factory_id)
    ).all()
    
    return logos

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

    # Check digit validation (required for North American VINs)
    check_digit_valid = validate_check_digit(vin)
    if is_north_american(vin) and not check_digit_valid:
        # Note: If North American, the VIN is generally considered invalid if check digit fails
        return {'error': 'Check digit validation failed. This VIN is not valid.'}

    # Extract components
    wmi = vin[:3]
    country_code = vin[:2]
    region_code = vin[0]

    # Look up in database (using correct model names and efficient loading)
    # Using WmiRegion model, which holds the single-character code
    region_entry = db.session.scalar(select(WmiRegion).filter_by(code=region_code))
    
    # Country lookup by WMI prefix (old WmiCountryCode is now part of WmiRegion)
    # We'll use the region code's country for the first two digits (e.g., JA -> Japan)
    # For a WMI prefix lookup, we use the WmiFactory table.
    country_entry = None
    factory_entry = db.session.scalar(
        select(WmiFactory).filter_by(wmi=wmi).options(db.joinedload(WmiFactory.country))
    )

    # Build response
    result = {
        'vin': vin,
        'wmi': wmi,
        'vds': vin[3:9],
        'vis': vin[9:17],
        'check_digit': vin[8],
        'check_digit_valid': check_digit_valid,
        'model_year_char': vin[9],
        'plant_code': vin[10],
        'serial_number': vin[11:17]
    }

    # Region info (Based on the first character)
    if region_entry and region_entry.country:
        result['region'] = region_entry.country.region
        result['region_country'] = region_entry.country.common_name
        result['region_flag'] = region_entry.country.flag_emoji
    else:
        result['region'] = 'Unknown'
        result['region_country'] = 'Unknown'
        result['region_flag'] = '🏳'
        
    # Country info (Based on WMI Prefix/Factory Country)
    if factory_entry and factory_entry.country:
        result['country'] = factory_entry.country.common_name
        result['country_flag'] = factory_entry.country.flag_emoji
        result['country_region'] = factory_entry.country.region
    else:
        # Fallback to region country if factory is unknown
        result['country'] = result.get('region_country', 'Unknown')
        result['country_flag'] = result.get('region_flag', '🏳')
        result['country_region'] = result.get('region', 'Unknown')


    # Factory/Manufacturer info
    if factory_entry:
        result['manufacturer'] = factory_entry.name
        
        # 1. Determine Factory Country/Flag
        factory_country_name = factory_entry.country.common_name if factory_entry.country else factory_entry.region
        factory_flag = factory_entry.country.flag_emoji if factory_entry.country else '🏭'
        
        # 2. Determine Factory Region (Priority: Country Region > WMI Factory Region)
        if factory_entry.country:
            # Use Country's Region
            factory_region = factory_entry.country.region
        else:
            # Fallback to WMI Factory's raw region field
            factory_region = factory_entry.region if factory_entry.region else 'Unknown Factory Region'

        # ASSIGN ALL CALCULATED FIELDS TO THE RESULT DICTIONARY
        result['factory_country'] = factory_country_name
        result['factory_flag'] = factory_flag
        result['factory_region'] = factory_region  # <-- MUST BE PRESENT
        
        # Get manufacturer logos
        logos = get_factory_logos(factory_entry.id)
        result['manufacturer_logos'] = logos if logos else []
    else:
        # Fallback for unknown manufacturer
        result['manufacturer'] = 'Unknown Manufacturer'
        result['manufacturer_logos'] = []
        result['factory_region'] = 'Unknown' # The frontend fallback
        result['factory_country'] = 'Unknown'
        result['factory_flag'] = '🏳'

    # Model year
    result['model_year'] = resolve_model_year(vin[9]) or 'Unknown'

    # --- INSERT DEBUG PRINT STATEMENT HERE ---
    print(f"DEBUG: Factory Region Calculated Value: {result.get('factory_region')}")
    # -----------------------------------------

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
    return render_template('index.html')

@bp.route('/img/logos/<path:filename>')
def serve_logo(filename):
    """Serve logos from the public/img/logos directory"""
    
    # CRITICAL FIX: Go up one directory from the app root to get to the project root,
    # then append the relative path to the public/img/logos directory.
    
    # 1. Get the absolute path to the project root (parent of current_app.root_path)
    project_root = os.path.dirname(current_app.root_path)
    
    # 2. Construct the absolute path to the logos directory
    logo_dir = os.path.join(project_root, 'public', 'img', 'logos')
    
    # 3. Serve the file
    return send_from_directory(logo_dir, filename)

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
    """Get all factories with their logo status (for potential logo-review page)"""
    # Use the logic from the old project, slightly adapted for SQLAlchemy 2.0+
    
    # We must use raw SQL for the GROUP_CONCAT which is SQLite specific and complex 
    # to translate to ORM easily when dealing with multiple joins/aggregations.
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


@bp.route('/logo-review')
def logo_review():
    """Serve the logo review page (not implemented in this HTML, but the route is here)"""
    return render_template('logo-review.html')