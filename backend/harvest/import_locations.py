"""
Import location data from CSV file into objects table.

CSV format expected:
- system_number
- accession_number
- LocationString
- Room

Example row:
57591	1988.35.1.1-.5	Art Gallery (OYAG), OYAG, 334 AD-Cont	334
"""

import os
import csv
import re
import sys
from typing import Dict, Optional, Tuple
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SB_URL = os.getenv("SB_URL")
SB_SECRET_KEY = os.getenv("SB_SECRET_KEY")

if not SB_URL or not SB_SECRET_KEY:
    raise ValueError("SB_URL and SB_SECRET_KEY must be set in .env file")

supabase: Client = create_client(SB_URL, SB_SECRET_KEY)


def parse_room_number(room_str: str) -> Tuple[Optional[int], Optional[str], Optional[int]]:
    """
    Parse room number string into components.
    
    Examples:
    - "137" -> (137, None, None)
    - "131a" -> (131, "a", None)
    - "231ab" -> (231, "ab", None)
    - "137-13" -> (137, None, 13)
    - "131a-5" -> (131, "a", 5)
    
    Returns:
        Tuple of (room_base_number, room_suffix, case_number)
    """
    if not room_str or not room_str.strip():
        return (None, None, None)
    
    room_str = room_str.strip()
    
    # Check for case number (format: room-case)
    case_match = re.match(r'^(\d+[a-z]*)-(\d+)$', room_str, re.IGNORECASE)
    if case_match:
        room_part = case_match.group(1)
        case_num = int(case_match.group(2))
        
        # Extract base number and suffix from room part
        room_match = re.match(r'^(\d+)([a-z]*)$', room_part, re.IGNORECASE)
        if room_match:
            base_num = int(room_match.group(1))
            suffix = room_match.group(2).lower() if room_match.group(2) else None
            return (base_num, suffix, case_num)
    
    # Check for room with suffix only (format: room+suffix)
    room_match = re.match(r'^(\d+)([a-z]+)$', room_str, re.IGNORECASE)
    if room_match:
        base_num = int(room_match.group(1))
        suffix = room_match.group(2).lower()
        return (base_num, suffix, None)
    
    # Plain number
    try:
        base_num = int(room_str)
        return (base_num, None, None)
    except ValueError:
        return (None, None, None)


def derive_floor_info(room_base_number: Optional[int]) -> Tuple[Optional[int], Optional[str]]:
    """
    Derive floor number and floor label from room base number.
    
    Rules:
    - < 100: Lower Level (floor_number = 0)
    - 100-150: First Floor (floor_number = 1)
    - 150-199: 1E (floor_number = 1, but special label)
    - 200s: Second Floor (floor_number = 2)
    - 300s: Third Floor (floor_number = 3)
    - 400s: Fourth Floor (floor_number = 4)
    
    Returns:
        Tuple of (floor_number, floor_label)
    """
    if room_base_number is None:
        return (None, None)
    
    if room_base_number < 100:
        return (0, "Lower Level")
    elif 100 <= room_base_number < 150:
        return (1, "First Floor")
    elif 150 <= room_base_number < 200:
        return (1, "1E")  # Special section accessible from second floor
    elif 200 <= room_base_number < 300:
        return (2, "Second Floor")
    elif 300 <= room_base_number < 400:
        return (3, "Third Floor")
    elif 400 <= room_base_number < 500:
        return (4, "Fourth Floor")
    else:
        # For rooms >= 500, default to floor 4 or handle as needed
        return (4, "Fourth Floor")


def format_room_number(room_base_number: Optional[int], room_suffix: Optional[str], 
                       case_number: Optional[int]) -> Optional[str]:
    """
    Format room number components back into a string.
    
    Examples:
    - (137, None, None) -> "137"
    - (131, "a", None) -> "131a"
    - (137, None, 13) -> "137-13"
    - (131, "a", 5) -> "131a-5"
    """
    if room_base_number is None:
        return None
    
    room_str = str(room_base_number)
    if room_suffix:
        room_str += room_suffix
    if case_number is not None:
        room_str += f"-{case_number}"
    
    return room_str


def import_locations_from_csv(csv_path: str, dry_run: bool = False):
    """
    Import location data from CSV file.
    
    Args:
        csv_path: Path to CSV file
        dry_run: If True, only print what would be updated without making changes
    """
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found: {csv_path}")
        return
    
    print(f"Reading location data from {csv_path}...")
    
    updates = []
    errors = []
    not_found = []
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        # Try to detect delimiter (tab or comma)
        sample = f.read(1024)
        f.seek(0)
        delimiter = '\t' if '\t' in sample else ','
        
        reader = csv.DictReader(f, delimiter=delimiter)
        
        # Normalize column names (handle case and whitespace)
        fieldnames = [name.strip().lower() for name in reader.fieldnames]
        reader.fieldnames = fieldnames
        
        required_fields = ['system_number', 'accession_number', 'locationstring', 'room']
        missing_fields = [f for f in required_fields if f not in fieldnames]
        
        if missing_fields:
            print(f"Error: Missing required columns: {missing_fields}")
            print(f"Found columns: {fieldnames}")
            return
        
        row_count = 0
        for row in reader:
            row_count += 1
            system_number = row.get('system_number', '').strip()
            accession_number = row.get('accession_number', '').strip()
            private_location_string = row.get('private_location_string', '').strip()
            room = row.get('room', '').strip()
            
            if not system_number:
                errors.append(f"Row {row_count}: Missing system_number")
                continue
            
            # Parse room number
            room_base_number, room_suffix, case_number = parse_room_number(room)
            gallery_number = format_room_number(room_base_number, room_suffix, case_number)
            
            # Derive floor info
            floor_number, floor_label = derive_floor_info(room_base_number)
            
            update_data = {
                'system_number': system_number,
                'gallery_number': gallery_number,
                'private_location_string': private_location_string if private_location_string else None,
                'room_base_number': room_base_number,
                'case_number': case_number,
                'floor_number': floor_number,
                'floor_label': floor_label,
            }
            
            updates.append(update_data)
    
    print(f"\nProcessed {row_count} rows from CSV")
    print(f"Found {len(updates)} valid location records")
    
    if dry_run:
        print("\n=== DRY RUN MODE - No changes will be made ===\n")
        for update in updates[:100]:  # Show first 5 as examples
            print(f"Would update system_number {update['system_number']}:")
            print(f"  Gallery: {update['gallery_number']}")
            print(f"  Floor: {update['floor_number']} ({update['floor_label']})")
            print(f"  Location: {update['private_location_string']}")
            print()
        if len(updates) > 5:
            print(f"... and {len(updates) - 5} more updates")
        return
    
    # Update database
    print("\nUpdating database...")
    updated_count = 0
    not_found_count = 0
    error_count = 0
    
    for update in updates:
        system_num = update['system_number']
        try:
            # Find object by system_number
            result = supabase.table("objects").select("id, system_number").eq("system_number", system_num).limit(1).execute()
            
            if not result.data:
                not_found.append(system_num)
                not_found_count += 1
                continue
            
            # Update the object
            update_dict = {k: v for k, v in update.items() if k != 'system_number'}
            supabase.table("objects").update(update_dict).eq("system_number", system_num).execute()
            updated_count += 1
            
            if updated_count % 100 == 0:
                print(f"Updated {updated_count} objects...")
                
        except Exception as e:
            errors.append(f"Error updating system_number {system_num}: {e}")
            error_count += 1
    
    print(f"\n=== Import Complete ===")
    print(f"Successfully updated: {updated_count} objects")
    print(f"Not found in database: {not_found_count} objects")
    print(f"Errors: {error_count} objects")
    
    if not_found and len(not_found) <= 20:
        print(f"\nObjects not found in database (first 20):")
        for sn in not_found[:20]:
            print(f"  - {sn}")
    elif not_found:
        print(f"\n{len(not_found)} objects not found in database (showing first 10):")
        for sn in not_found[:10]:
            print(f"  - {sn}")
    
    if errors and len(errors) <= 10:
        print(f"\nErrors encountered:")
        for error in errors:
            print(f"  - {error}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_locations.py <csv_file> [--dry-run]")
        print("\nExample:")
        print("  python import_locations.py locations.csv")
        print("  python import_locations.py locations.csv --dry-run")
        sys.exit(1)
    
    csv_path = sys.argv[1]
    dry_run = "--dry-run" in sys.argv
    
    import_locations_from_csv(csv_path, dry_run=dry_run)
