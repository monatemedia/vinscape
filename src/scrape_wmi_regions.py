import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# Configuration
DATA_DIR = Path("public_data_sources")
OUTPUT_FILE = DATA_DIR / "wmi_region_codes.json"
HTML_CACHE_FILE = DATA_DIR / "wmi_wikipedia_page.html"
WIKI_URL = "https://en.wikibooks.org/wiki/Vehicle_Identification_Numbers_(VIN_codes)/World_Manufacturer_Identifier_(WMI)"

# Valid VIN characters in order (excluding I, O, Q)
VIN_CHARACTERS = [
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 
    'N', 'P', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    '1', '2', '3', '4', '5', '6', '7', '8', '9', '0'
]

# Column headers in order (second character of WMI)
COLUMN_HEADERS = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'J', 'K', 'L', 'M', 'N', 'P', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z', '1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

def fetch_page_content():
    """Fetch the Wikipedia page content or load from cache"""
    
    # Check if cached version exists
    if HTML_CACHE_FILE.exists():
        print(f"✓ Loading cached HTML from {HTML_CACHE_FILE}")
        with open(HTML_CACHE_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    
    print(f"📥 Fetching page from {WIKI_URL}...")
    try:
        # Add headers to avoid 403 Forbidden
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        response = requests.get(WIKI_URL, headers=headers, timeout=30)
        response.raise_for_status()
        print("✓ Page fetched successfully")
        
        # Cache the HTML for future use
        DATA_DIR.mkdir(exist_ok=True)
        with open(HTML_CACHE_FILE, 'w', encoding='utf-8') as f:
            f.write(response.text)
        print(f"💾 Cached HTML to {HTML_CACHE_FILE}")
        
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching page: {e}")
        raise

def is_header_row(row):
    """Check if a row is a header row (first cell is empty/whitespace)"""
    cells = row.find_all(['td', 'th'])
    if not cells:
        return False
    
    first_cell = cells[0]
    text = first_cell.get_text(strip=True)
    
    # Header rows have empty first cell or just nbsp
    return text == '' or text == '\xa0' or text == ' '

def format_range(start_char, end_char, row_letter):
    """Format a range string like 'AA-AH' or single 'BC'"""
    start = f"{row_letter}{start_char}"
    end = f"{row_letter}{end_char}"
    
    if start == end:
        return start
    return f"{start}-{end}"

def normalize_country_name(country):
    """Normalize country names to match countries.json"""
    replacements = {
        'Swaziland': 'Eswatini',
        'UAE': 'United Arab Emirates',
        'Dom. Rep.': 'Dominican Republic',
        'Bosnia & Herzogovina': 'Bosnia and Herzegovina',
        'Bosnia & Herzegovina': 'Bosnia and Herzegovina',
    }
    
    # Remove formatting like (former East Germany), <small> tags, etc.
    # First, clean up HTML small tags and their content
    country = country.split('<small>')[0].strip()
    
    return replacements.get(country, country)

def parse_wmi_region_table(html_content):
    """Parse the WMI regions table by filling an array of 2-char WMI codes."""
    print("\n🔍 Parsing WMI Regions table...")

    soup = BeautifulSoup(html_content, 'html.parser')
    tables = soup.find_all('table', {'class': 'wikitable'})

    if len(tables) < 2:
        print("❌ Could not find enough tables on page")
        return []

    target_table = tables[1]
    
    # 33 columns (A-Z, 1-9, 0)
    COLUMN_COUNT = len(COLUMN_HEADERS) 
    
    # NEW: Array to hold the country name for every possible WMI code
    # We will fill this and then merge ranges at the end.
    wmi_map = {} 
    
    # Dictionary to track cells claimed by a rowspan
    # Key: col_index (0-32), Value: (country_name, remaining_rowspan, colspan)
    claimed_cells = {}

    rows = target_table.find_all('tr')
    
    for row_index, row in enumerate(rows):
        
        if is_header_row(row):
            continue

        cells = row.find_all(['td', 'th'])
        
        # Skip rows with no content cells
        if len(cells) < 2 and not claimed_cells:
            continue

        # First cell is the row letter (A, B, C, etc.)
        row_letter = cells[0].get_text(strip=True) if cells else None

        if not row_letter or len(row_letter) > 1:
            continue

        # --- PHASE 1: Populate current row's countries, handling rowspans ---
        col_cursor = 0
        cell_cursor = 1
        new_claimed_cells = {}
        
        # We need to fill 33 columns (0 to 32)
        while col_cursor < COLUMN_COUNT:
            country = None
            colspan = 1
            rowspan = 1
            
            # 1. Check if the current column is claimed by a rowspan from a previous row
            if col_cursor in claimed_cells:
                # This column is claimed. Get its data.
                country, rowspan_count, colspan = claimed_cells[col_cursor]
                
                # Decrement the rowspan count for the next row's iteration
                new_claimed_cells[col_cursor] = (country, rowspan_count - 1, colspan)
                
            # 2. If the column is NOT claimed, read the next actual cell in the current row
            elif cell_cursor < len(cells):
                cell = cells[cell_cursor]
                
                colspan = int(cell.get('colspan', 1))
                rowspan = int(cell.get('rowspan', 1))
                country = cell.get_text(strip=True)
                
                # If this cell spans multiple rows, add it to claimed_cells
                if rowspan > 1:
                    # Note: The actual content should only be in the leftmost cell of the span.
                    if country:
                         new_claimed_cells[col_cursor] = (country, rowspan - 1, colspan)

                cell_cursor += 1
            
            # 3. If a country was determined (either claimed or from a new cell)
            if country:
                country = normalize_country_name(country)
                country = country.replace('<small>', '').replace('</small>', '')
                country = country.split('(')[0].strip()

                # Fill all the spanned WMI codes for this entry
                for i in range(col_cursor, col_cursor + colspan):
                    wmi_code = row_letter + COLUMN_HEADERS[i]
                    wmi_map[wmi_code] = country
            
            # Move column cursor forward
            col_cursor += colspan
        
        # --- PHASE 2: Update the claimed_cells for the next row ---
        # Only keep claims that have a remaining rowspan count > 0
        claimed_cells = {
            k: v for k, v in new_claimed_cells.items() if v[1] > 0
        }

    # --- PHASE 3: Convert the wmi_map (code: country) into grouped ranges ---
    print("\n✓ Consolidating codes into ranges...")
    
    wmi_rules = []
    current_country = None
    current_range_start = None
    
    # Iterate through all possible codes in order
    all_rows = [c[0] for c in wmi_map.keys()]
    unique_rows = sorted(list(set(all_rows)), key=lambda x: VIN_CHARACTERS.index(x))
    
    for row in unique_rows:
        codes_in_row = sorted([k for k in wmi_map.keys() if k.startswith(row)], 
                              key=lambda x: COLUMN_HEADERS.index(x[1]))
                              
        current_country = None
        current_range_start = None
        
        for code in codes_in_row:
            country = wmi_map.get(code)
            
            # If the country changes (or this is the first code in the row)
            if country != current_country:
                # 1. Finalize the previous range (if one exists)
                if current_country and current_range_start:
                    range_str = format_range(
                        current_range_start[1], # start_char
                        code[1],               # end_char (The code BEFORE the new one)
                        row                    # row_letter
                    )
                    # Correct the end_char to be the one *before* the current code
                    prev_char_index = COLUMN_HEADERS.index(code[1]) - 1
                    if prev_char_index >= 0:
                         range_str = format_range(current_range_start[1], COLUMN_HEADERS[prev_char_index], row)
                    
                    wmi_rules.append({"range": range_str, "country": current_country})
                    
                # 2. Start a new range
                current_country = country
                current_range_start = code
                
            # If this is the last code in the row, finalize the range
            if code == codes_in_row[-1]:
                 if current_country and current_range_start:
                    range_str = format_range(
                        current_range_start[1], # start_char
                        code[1],               # end_char
                        row                    # row_letter
                    )
                    wmi_rules.append({"range": range_str, "country": current_country})


    print(f"✓ Extracted {len(wmi_rules)} WMI region mappings")
    return wmi_rules

def save_json(data, filepath):
    """Save data to JSON file"""
    filepath.parent.mkdir(exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved {len(data)} rules to {filepath}")

def display_statistics(rules):
    """Display statistics about the parsed rules"""
    print("\n" + "="*50)
    print("📊 Statistics:")
    print(f"Total rules: {len(rules)}")
    
    # Count by country
    country_counts = {}
    for rule in rules:
        country = rule['country']
        country_counts[country] = country_counts.get(country, 0) + 1
    
    print(f"\nUnique countries/regions: {len(country_counts)}")
    print("\nTop 10 countries by rule count:")
    sorted_countries = sorted(country_counts.items(), key=lambda x: x[1], reverse=True)
    for country, count in sorted_countries[:10]:
        print(f"  {country}: {count} rules")
    
    print("="*50)

def main():
    """Main execution function"""
    print("🚀 Starting WMI Region Codes extraction...\n")
    
    try:
        # Fetch or load cached page
        html_content = fetch_page_content()
        
        # Parse table
        wmi_rules = parse_wmi_region_table(html_content)
        
        if not wmi_rules:
            print("\n❌ No rules extracted. Please check the page structure.")
            return
        
        # Save to JSON
        save_json(wmi_rules, OUTPUT_FILE)
        
        # Display statistics
        display_statistics(wmi_rules)
        
        print("\n✅ WMI region codes extracted successfully!")
        print(f"\n💡 Tip: The HTML page is cached at {HTML_CACHE_FILE}")
        print("   You can reuse it for other scraping tasks without making new requests.")
        print("   Delete the cache file if you want to fetch a fresh copy.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()