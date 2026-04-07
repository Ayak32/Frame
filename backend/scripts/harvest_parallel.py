import os
import json
import asyncio
import aiohttp
import sys
import time
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


# Number of concurrent API requests
MAX_CONCURRENT_REQUESTS = 64

# Number of objects to batch before writing to database
BATCH_SIZE = 50  

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


    # Public location string
    public_location_string = None
    for ref in linked_art_json.get('referred_to_by', []):
        if ref.get('type') == 'LinguisticObject':
            content = ref.get('content', '')
            classified_as = ref.get('classified_as', [])
            for cls in classified_as:
                if isinstance(cls, dict):
                    if cls.get('id') == 'http://vocab.getty.edu/aat/300133046':
                        public_location_string = content
                        break
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

def is_art_object_url(url: str) -> bool:
    """Check if URL points to an actual art object (not VisualItem, Dimension, Set, etc.)"""
    return '/obj/' in url

async def fetch_linked_art_object(session: aiohttp.ClientSession, object_id: str, semaphore: asyncio.Semaphore) -> Optional[Dict[str, Any]]:
    """Fetch full linked art record asynchronously"""
    async with semaphore:  # Limit concurrent requests
        try:
            async with session.get(object_id, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            # Don't print every error to avoid spam - only log if it's not a common error
            error_msg = str(e) if str(e) else type(e).__name__
            if "404" not in error_msg and "timeout" not in error_msg.lower():
                print(f"Error fetching {object_id}: {error_msg}")
            return None
        except Exception as e:
            error_msg = str(e) if str(e) else type(e).__name__
            print(f"Error fetching {object_id}: {error_msg}")
            return None

async def process_object(session: aiohttp.ClientSession, object_id: str, semaphore: asyncio.Semaphore) -> Optional[Dict[str, Any]]:
    """Process a single object: fetch, extract, and return data"""
    # Skip if not an art object
    if not is_art_object_url(object_id):
        return None
    
    # Fetch object (no existence check - upsert handles duplicates efficiently)
    linked_art_json = await fetch_linked_art_object(session, object_id, semaphore)
    if not linked_art_json:
        return None
    
    # Verify it's a HumanMadeObject
    if linked_art_json.get('type') != 'HumanMadeObject':
        return None
    
    # Extract fields
    fields = extract_object_fields(linked_art_json)
    
    return {
        'linked_art_json': linked_art_json,
        'fields': fields,
        'is_on_view': is_on_view(linked_art_json)
    }

def write_batch_to_db(batch: List[Dict[str, Any]]):
    """Write a batch of objects to database"""
    on_view_batch = []
    off_view_batch = []
    
    for item in batch:
        fields = item['fields']
        linked_art_json = item['linked_art_json']
        
        if item['is_on_view']:
            on_view_batch.append({
                'id': fields['id'],
                'linked_art_json': linked_art_json,
                **{k: v for k, v in fields.items() if k not in ['id', 'type']}
            })
        else:
            off_view_batch.append({
                'id': fields['id'],
                **{k: v for k, v in fields.items() if k not in ['id', 'dimensions_text']}
            })
    
    # Write batches
    if on_view_batch:
        try:
            supabase.table("objects_on_view").upsert(on_view_batch).execute()
        except Exception as e:
            print(f"Error inserting on-view batch: {e}")
    
    if off_view_batch:
        try:
            supabase.table("objects_off_view").upsert(off_view_batch).execute()
        except Exception as e:
            print(f"Error inserting off-view batch: {e}")
    
    return len(on_view_batch), len(off_view_batch)

async def process_change_page(session: aiohttp.ClientSession, page_url: str, semaphore: asyncio.Semaphore) -> tuple[int, int]:
    """Process a single change page asynchronously"""
    print(f"Processing {page_url}...")
    
    try:
        async with session.get(page_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
            response.raise_for_status()
            page_data = await response.json()
    except Exception as e:
        error_msg = str(e) if str(e) else type(e).__name__
        print(f"Error fetching page {page_url}: {error_msg}")
        return (0, 0)
    
    items = page_data.get('orderedItems', [])
    object_ids = [item.get('object', {}).get('id') for item in items if item.get('object', {}).get('id')]
    
    # Process all objects concurrently
    tasks = [process_object(session, obj_id, semaphore) for obj_id in object_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Filter out None and exceptions
    processed_objects = [r for r in results if r is not None and not isinstance(r, Exception)]
    
    # Count exceptions for logging
    exception_count = sum(1 for r in results if isinstance(r, Exception))
    if exception_count > 0:
        print(f"  {exception_count} objects had processing errors")
    
    # Write in batches
    on_view_count = 0
    off_view_count = 0
    
    if processed_objects:
        for i in range(0, len(processed_objects), BATCH_SIZE):
            batch = processed_objects[i:i + BATCH_SIZE]
            on_view, off_view = write_batch_to_db(batch)
            on_view_count += on_view
            off_view_count += off_view
    
    skipped_count = len(object_ids) - len(processed_objects)
    if skipped_count > 0:
        print(f"  Skipped {skipped_count} items (non-objects or fetch errors)")
    
    return (on_view_count, off_view_count)

def get_page_url_by_number(page_num: int) -> str:
    """Get the URL for a specific page number (e.g., changes-017.json)"""
    return f"{DISCOVERY_BASE}/changes-{page_num:03d}.json"

async def harvest_all_async(start_page: Optional[int] = None):
    """
    Harvest all objects from discovery API using async/await for parallelization
    
    Args:
        start_page: Page number to start from (e.g., 17 for changes-017.json). 
                   If None, starts from the beginning.
    """
    print("Starting parallel harvest...")
    if start_page:
        print(f"Resuming from page {start_page}")
    
    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    
    async with aiohttp.ClientSession() as session:
        # Get collection info
        try:
            async with session.get(COLLECTION_URL, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                collection = await response.json()
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
        else:
            current_page = first_page
        
        total_on_view = 0
        total_off_view = 0
        page_number = start_page if start_page else 1
        
        while current_page:
            print(f"\n--- Processing page {page_number} ({current_page}) ---")
            start_time = time.time()
            
            on_view, off_view = await process_change_page(session, current_page, semaphore)
            total_on_view += on_view
            total_off_view += off_view
            
            elapsed = time.time() - start_time
            print(f"Page {page_number} complete: {on_view} on-view, {off_view} off-view (took {elapsed:.1f}s)")
            print(f"Total new objects this run: {total_on_view} on-view, {total_off_view} off-view")
            
            # Get next page
            try:
                async with session.get(current_page, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    response.raise_for_status()
                    page_data = await response.json()
                    next_page = page_data.get('next', {}).get('id')
                    current_page = next_page
                    page_number += 1
            except Exception as e:
                print(f"Error getting next page: {e}")
                print(f"Last successful page was {page_number - 1}")
                print(f"You can resume from page {page_number} by running:")
                print(f"  python scripts/harvest_parallel.py --start-page {page_number}")
                break
    
    print(f"\nHarvest complete")
    print(f"Total new objects added: {total_on_view} on-view, {total_off_view} off-view")

def main():
    """Main entry point"""
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
    
    asyncio.run(harvest_all_async(start_page=start_page))

if __name__ == "__main__":
    main()
