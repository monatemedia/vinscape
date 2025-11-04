import sqlite3
import os

DB_PATH = "./instance/vin.db"

def inspect_database():
    """Inspect and display complete database schema and sample data"""
    
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 80)
    print("DATABASE SCHEMA INSPECTION")
    print("=" * 80)
    print()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Found {len(tables)} table(s): {', '.join(tables)}")
    print()
    
    for table in tables:
        print("=" * 80)
        print(f"TABLE: {table}")
        print("=" * 80)
        
        # Get table schema
        cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
        schema = cursor.fetchone()[0]
        print("\nCREATE TABLE statement:")
        print("-" * 80)
        print(schema)
        print()
        
        # Get column info
        cursor.execute(f"PRAGMA table_info({table})")
        columns = cursor.fetchall()
        print("Columns:")
        print("-" * 80)
        for col in columns:
            col_id, name, col_type, not_null, default, pk = col
            pk_str = " [PRIMARY KEY]" if pk else ""
            null_str = " NOT NULL" if not_null else ""
            default_str = f" DEFAULT {default}" if default else ""
            print(f"  {name}: {col_type}{pk_str}{null_str}{default_str}")
        print()
        
        # Get foreign keys
        cursor.execute(f"PRAGMA foreign_key_list({table})")
        foreign_keys = cursor.fetchall()
        if foreign_keys:
            print("Foreign Keys:")
            print("-" * 80)
            for fk in foreign_keys:
                fk_id, seq, ref_table, from_col, to_col, on_update, on_delete, match = fk
                print(f"  {from_col} -> {ref_table}({to_col})")
            print()
        
        # Get row count
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row_count = cursor.fetchone()[0]
        print(f"Total rows: {row_count}")
        print()
        
        # Get sample data (first 5 rows)
        if row_count > 0:
            cursor.execute(f"SELECT * FROM {table} LIMIT 5")
            rows = cursor.fetchall()
            col_names = [description[0] for description in cursor.description]
            
            print("Sample data (first 5 rows):")
            print("-" * 80)
            
            # Print column headers
            print(" | ".join(col_names))
            print("-" * 80)
            
            # Print rows
            for row in rows:
                print(" | ".join(str(val) if val is not None else "NULL" for val in row))
            print()
        
        print()
    
    conn.close()
    
    print("=" * 80)
    print("INSPECTION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    inspect_database()