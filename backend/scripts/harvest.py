import os
import json
import requests
import time
import sys
from typing import Dict, Any, List, Optional
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SB_URL = os.getenv("SB_URL")
SB_PUBLISHABLE_KEY = os.getenv("SB_PUBLISHABLE_KEY")
SB_SECRET_KEY = os.getenv("SB_SECRET_KEY")

supabase: Client = create_client(SB_URL, SB_SECRET_KEY)

DISCOVERY_BASE = "https://media.art.yale.edu/discovery/lux-full"
COLLECTION_URL = f"{DISCOVERY_BASE}/collection.json"

def is_on_view(linked_art_record: Dict[str, Any]) -> bool:
    """Check if object is on view"""
    referred_to_by = linked_art_record.get('referred_to_by', [])

    for ref in referred_to_by:
        if ref.get('type') == 'LinguisticObject':
            content = ref.get('content', '')
            classified_as = ref.get('classified_as', [])
            for cls in classified_as:
                if isinstance(cls, dict):
                    if cls.get('id') == 'http://vocab.getty.edu/aat/300133046':
                        if 'On view' in content:
                            return True
    return False


def extract_object_fields(linked_art_json: Dict[str, Any]) -> Dict[str, Any]:
    """Extract all fields from Linked Art JSON"""
    # Title
    title = linked_art_json.get('_label')
    
    # Creator
    creator_id = None
    creator_name = None
    produced_by = linked_art_json.get('produced_by', {})
    if produced_by:
        parts = produced_by.get('part', [])
        for part in parts:
            carried_by = part.get('carried_out_by', [])
            if carried_by:
                creator = carried_by[0]
                creator_id = creator.get('id')
                creator_name = creator.get('_label', '').replace('Artist: ', '')
                break

    # Accession and System numbers
    accession_number = None
    system_number = None
    for identifier in linked_art_json.get('identified_by', []):
        if identifier.get('type') == 'Identifier':
            content = identifier.get('content')
            classified_as = identifier.get('classified_as', [])
            for cls in classified_as:
                label = cls.get('_label', '')
                if label == 'Accession Number':
                    accession_number = content
                elif label == 'System-Assigned Number':
                    system_number = content

    # Classification
    classifications = [c.get('_label') for c in linked_art_json.get('classified_as', []) 
                      if c.get('_label')]

    # Date
    date_created = None
    if produced_by and 'timespan' in produced_by:
        timespan = produced_by['timespan']
        identified_by = timespan.get('identified_by', [])
        if identified_by:
            date_created = identified_by[0].get('content')

    # Materials
    materials = [m.get('_label') for m in linked_art_json.get('made_of', []) 
                if m.get('_label')]

    # Dimensions, Culture, Period
    dimensions_text = None
    culture = None
    period = None
    for ref in linked_art_json.get('referred_to_by', []):
        if ref.get('type') == 'LinguisticObject':
            content = ref.get('content', '')
            classified_as = ref.get('classified_as', [])
            for cls in classified_as:
                label = cls.get('_label', '')
                if label == 'Dimensions':
                    dimensions_text = content
                elif label == 'Culture':
                    culture = content
                elif label == 'Period':
                    period = content

    # Audio guide
    audio_guide_transcript = None
    audio_guide_url = None
    for ref in linked_art_json.get('referred_to_by', []):
        if ref.get('type') == 'LinguisticObject':
            content = ref.get('content', '')
            classified_as = ref.get('classified_as', [])
            for cls in classified_as:
                label = cls.get('_label', '')
                if label == 'Audioguide Transcript':
                    audio_guide_transcript = content
                    audio_guide_url = ref.get('_audioguide_url')
                    break

    # Type
    object_type = linked_art_json.get('type')

    return {
        'id': linked_art_json.get('id'),
        'title': title,
        'creator_id': creator_id,
        'creator_name': creator_name,
        'accession_number': accession_number,
        'system_number': system_number,
        'classification': classifications,
        'date_created': date_created,
        'materials': materials,
        'dimensions_text': dimensions_text if dimensions_text else None,
        'culture': culture,
        'period': period,
        'type': object_type,
        'audio_guide_transcript': audio_guide_transcript,
        'audio_guide_url': audio_guide_url,
    }

def fetch_linked_art_object(object_id: str, retries: int = 3) -> Optional[Dict[str, Any]]:
    """Fetch full linked art record with retry logic"""
    for attempt in range(retries):
        try:
            response = requests.get(object_id, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt < retries - 1:
                wait_time = (attempt + 1) * 5  # Exponential backoff: 5s, 10s, 15s
                print(f"Error fetching {object_id} (attempt {attempt + 1}/{retries}), retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"Error fetching {object_id} after {retries} attempts: {e}")
                return None
    return None


def is_art_object_url(url: str) -> bool:
    """Check if URL points to an actual art object (not VisualItem, Dimension, Set, etc.)"""
    return '/obj/' in url

def object_exists_in_db(object_id: str) -> bool:
    """Check if object already exists in either table"""
    try:
        # Check on-view table
        result = supabase.table("objects_on_view").select("id").eq("id", object_id).limit(1).execute()
        if result.data:
            return True
        # Check off-view table
        result = supabase.table("objects_off_view").select("id").eq("id", object_id).limit(1).execute()
        return len(result.data) > 0
    except Exception as e:
        # If check fails, assume it doesn't exist and process it
        return False

def process_change_page(page_url: str, skip_existing: bool = True) -> tuple[int, int]:
    """Process a single change page, return (on_view_count, off_view_count)"""
    print(f"Processing {page_url}...")
    
    try:
        response = requests.get(page_url, timeout=30)
        response.raise_for_status()
        page_data = response.json()
    except Exception as e:
        print(f"Error fetching page {page_url}: {e}")
        return (0,0)

    items = page_data.get('orderedItems', [])
    on_view_count = 0
    off_view_count = 0
    skipped_count = 0
    already_exists_count = 0

    for item in items:
            object_id = item.get('object', {}).get('id')
            if not object_id:
                    continue
            
            # Only process art objects, skip VisualItems, Dimensions, Sets, etc.
            if not is_art_object_url(object_id):
                skipped_count += 1
                continue
            
            # Skip if already exists (optional optimization)
            if skip_existing and object_exists_in_db(object_id):
                already_exists_count += 1
                continue
            
            # fetch full object record
            linked_art_json = fetch_linked_art_object(object_id)
            if not linked_art_json:
                continue
            
            # Small delay to be respectful to API
            time.sleep(0.1)

            # Double-check: ensure it's actually a HumanMadeObject
            if linked_art_json.get('type') != 'HumanMadeObject':
                skipped_count += 1
                continue

            fields = extract_object_fields(linked_art_json)

            if is_on_view(linked_art_json):
                # store in objects_on_view
                try:
                    supabase.table("objects_on_view").upsert({
                        'id': fields['id'], 
                        'linked_art_json': linked_art_json,
                         **{k: v for k, v in fields.items() if k not in ['id', 'type']}
                         }).execute()
                    on_view_count += 1
                except Exception as e:
                    print(f"Error inserting on-view object {object_id}: {e}")

            else:
                # store in objects_off_view
                # Note: objects_off_view has a 'type' column but NOT 'dimensions_text'
                try:
                    supabase.table("objects_off_view").upsert({
                        'id': fields['id'],
                        **{k: v for k, v in fields.items() if k not in ['id', 'dimensions_text']}
                        }).execute()
                    off_view_count += 1
                except Exception as e:
                    print(f"Error inserting off-view object {object_id}: {e}")
            
            if (on_view_count + off_view_count) % 100 == 0:
                print(f"Processed {on_view_count + off_view_count} new objects...")
    
    if skipped_count > 0:
        print(f"Skipped {skipped_count} non-object items (VisualItems, Dimensions, Sets, etc.)")
    if already_exists_count > 0:
        print(f"Skipped {already_exists_count} objects that already exist in database")
    
    return (on_view_count, off_view_count)

def get_page_url_by_number(page_num: int) -> Optional[str]:
    """Get the URL for a specific page number (e.g., changes-017.json)"""
    return f"{DISCOVERY_BASE}/changes-{page_num:03d}.json"

def harvest_all(start_page: Optional[int] = None, skip_existing: bool = True):
    """
    Harvest all objects from discovery API
    
    Args:
        start_page: Page number to start from (e.g., 17 for changes-017.json). 
                   If None, starts from the beginning.
        skip_existing: If True, skip objects that already exist in the database
    """
    print("starting harvest...")
    if start_page:
        print(f"Resuming from page {start_page}")

    try:
        response = requests.get(COLLECTION_URL, timeout=30)
        response.raise_for_status()
        collection = response.json()
    except Exception as e:
        print(f"Error fetching collection: {e}")
        return
    
    first_page = collection.get('first', {}).get('id')
    last_page = collection.get('last', {}).get('id')
    
    if not first_page or not last_page:
        print("Could not find first/last pages")
        return
    
    print(f"Collection range: {first_page} to {last_page}")
    
    # Start from specified page or first page
    if start_page:
        current_page = get_page_url_by_number(start_page)
        if not current_page:
            print(f"Invalid start page: {start_page}")
            return
    else:
        current_page = first_page
    
    total_on_view = 0
    total_off_view = 0
    page_number = start_page if start_page else 1

    while current_page:
        print(f"\n--- Processing page {page_number} ({current_page}) ---")
        on_view, off_view = process_change_page(current_page, skip_existing=skip_existing)
        total_on_view += on_view
        total_off_view += off_view
        
        print(f"Page {page_number} complete: {on_view} on-view, {off_view} off-view")
        print(f"Total new objects this run: {total_on_view} on-view, {total_off_view} off-view")
        
        # Get next page
        try:
            response = requests.get(current_page, timeout=30)
            response.raise_for_status()
            page_data = response.json()
            next_page = page_data.get('next', {}).get('id')
            current_page = next_page
            page_number += 1
            
            # Small delay between pages
            if current_page:
                time.sleep(0.5)
        except Exception as e:
            print(f"Error getting next page: {e}")
            print(f"Last successful page was {page_number - 1}")
            print(f"You can resume from page {page_number} by running:")
            print(f"  python scripts/harvest.py --start-page {page_number}")
            break
    
    print(f"\nHarvest complete")
    print(f"Total new objects added: {total_on_view} on-view, {total_off_view} off-view")


if __name__ == "__main__":
    # Parse command line arguments
    start_page = None
    if len(sys.argv) > 1:
        if "--start-page" in sys.argv:
            idx = sys.argv.index("--start-page")
            if idx + 1 < len(sys.argv):
                try:
                    start_page = int(sys.argv[idx + 1])
                except ValueError:
                    print("Error: --start-page requires a number")
                    sys.exit(1)
    
    harvest_all(start_page=start_page, skip_existing=True)