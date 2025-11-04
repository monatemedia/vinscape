import json
import requests
from bs4 import BeautifulSoup
from pathlib import Path

# Configuration
DATA_DIR = Path("public_data_sources")
OUTPUT_FILE = DATA_DIR / "wmi_factory_codes.json"
HTML_CACHE_FILE = DATA_DIR / "wmi_wikipedia_page.html"
WIKI_URL = "https://en.wikibooks.org/wiki/Vehicle_Identification_Numbers_(VIN_codes)/World_Manufacturer_Identifier_(WMI)"

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

def parse_wmi_factory_table(html_content):
    """Parse the WMI factory codes table"""
    print("\n🔍 Parsing WMI Factory Codes table...")

    soup = BeautifulSoup(html_content, 'html.parser')

    # Find the "List of Many WMIs" section by its ID, which is more reliable
    # target_heading_element will be the <h3> tag inside the mw-heading3 div
    target_heading_element = soup.find(id='List_of_Many_WMIs')
    
    if not target_heading_element:
        print("❌ Could not find 'List of Many WMIs' section ID")
        return []

    # The <table> we want is a sibling of the parent <div> of the heading,
    # and it appears after the <p> tag that follows the heading.
    # The parent is the <div> with class mw-heading mw-heading3.
    # We start searching from the sibling *after* the heading's parent div.
    start_point = target_heading_element.parent
    print(f"✓ Found section starting point: {start_point.name} tag")

    # Find the table after this start_point
    table = None
    current = start_point

    # Look through next siblings to find the table.
    # The structure is: <div> (heading) -> <p> (text) -> <table> (data)
    while current:
        current = current.find_next_sibling()
        
        # We are looking for the wikitable class, which is a key identifier.
        # This is more robust than just checking for 'table'.
        if current and current.name == 'table' and 'wikitable' in current.get('class', []):
            table = current
            break
            
        # Stop looking if we hit the next major section heading
        if current and current.name in ['h2', 'h3']:
            break

    if not table:
        print("❌ Could not find table after 'List of Many WMIs' heading")
        # Debug: show what the next few siblings are
        debug_sibling = start_point.find_next_sibling()
        if debug_sibling:
             print(f"Debug: Next sibling is a <{debug_sibling.name}> tag.")
             if debug_sibling.name == 'p':
                 table_check = debug_sibling.find_next_sibling()
                 if table_check:
                    print(f"Debug: Sibling after <p> is a <{table_check.name}> tag.")

        return []

    print(f"✓ Found table with {len(table.find_all('tr'))} rows")

    # Parse the table (rest of your logic is good)
    wmi_codes = []
    rows = table.find_all('tr')
    
    # Skip header row
    data_rows = rows[1:] if len(rows) > 1 else rows

    for row in data_rows:
        cells = row.find_all(['td', 'th'])
        
        # Need exactly 2 cells: WMI and Manufacturer
        if len(cells) < 2:
            continue
            
        wmi = cells[0].get_text(strip=True)
        manufacturer = cells[1].get_text(strip=True)
        
        # Skip empty rows
        if not wmi or not manufacturer:
            continue
            
        # Standardize key names to lowercase for the internal data structure
        # (though the prompt output uses PascalCase, lowercase is standard for Python dict keys)
        wmi_codes.append({
            "WMI": wmi, # Changing back to match desired output casing
            "Manufacturer": manufacturer # Changing back to match desired output casing
        })

    print(f"✓ Extracted {len(wmi_codes)} WMI factory codes")
    return wmi_codes

def save_json(data, filepath):
    """Save data to JSON file"""
    filepath.parent.mkdir(exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Saved {len(data)} codes to {filepath}")

def display_statistics(codes):
    """Display statistics about the parsed codes"""
    print("\n" + "="*50)
    print("📊 Statistics:")
    print(f"Total WMI codes: {len(codes)}")

    # Show first few examples
    print("\nFirst 10 entries:")
    for code in codes[:10]:
        # FIX: Changed 'wmi' to 'WMI' and 'manufacturer' to 'Manufacturer'
        print(f"  {code['WMI']}: {code['Manufacturer'][:60]}...") 

    # Count by first letter
    first_letters = {}
    for code in codes:
        # FIX: Changed 'wmi' to 'WMI'
        if code['WMI']:
            first_letter = code['WMI'][0]
            first_letters[first_letter] = first_letters.get(first_letter, 0) + 1
            
    print(f"\nDistribution by first character:")
    for letter in sorted(first_letters.keys()):
        print(f"  {letter}: {first_letters[letter]} codes")
        
    print("="*50)
    
def main():
    """Main execution function"""
    print("🚀 Starting WMI Factory Codes extraction...\n")
    
    try:
        # Fetch or load cached page
        html_content = fetch_page_content()
        
        # Parse table
        wmi_codes = parse_wmi_factory_table(html_content)
        
        if not wmi_codes:
            print("\n❌ No codes extracted. Please check the page structure.")
            return
        
        # Save to JSON
        save_json(wmi_codes, OUTPUT_FILE)
        
        # Display statistics
        display_statistics(wmi_codes)
        
        print("\n✅ WMI factory codes extracted successfully!")
        print(f"\n💡 Tip: The HTML page is cached at {HTML_CACHE_FILE}")
        print("   All scripts can reuse this cache without making new requests.")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()