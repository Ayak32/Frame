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

# Concurrent object fetches. Too high (e.g. 64) often triggers "Connection reset by peer" from
# media.art.yale.edu. Override with env HARVEST_MAX_CONCURRENT if needed.
MAX_CONCURRENT_REQUESTS = max(1, int(os.getenv("HARVEST_MAX_CONCURRENT", "46")))

FETCH_RETRIES = 4
FETCH_BACKOFF_SEC = 2.0
DEFAULT_HEADERS = {
    "User-Agent": "Thesis-LUX-Harvest/1.0 (Yale collection crawl; respectful concurrency)",
    "Accept": "application/json",
}

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

    # referred_to_by: dimensions, culture, period, provenance, credit line, access/on-view string, audioguide
    dimensions_text = None
    culture = None
    period = None
    provenance_text = None
    credit_line = None
    public_location_string = None
    audio_guide_transcript = None
    audio_guide_url = None

    for ref in linked_art_json.get('referred_to_by', []):
        if ref.get('type') != 'LinguisticObject':
            continue
        content = ref.get('content', '')
        for cls in ref.get('classified_as', []) or []:
            if not isinstance(cls, dict):
                continue
            label = cls.get('_label', '')
            cid = cls.get('id')
            if label == 'Dimensions':
                dimensions_text = content
            elif label == 'Culture':
                culture = content
            elif label == 'Period':
                period = content
            elif label == 'Provenance':
                provenance_text = content
            elif label == 'Credit Line':
                credit_line = content
            elif label == 'Audioguide Transcript':
                audio_guide_transcript = content
                audio_guide_url = ref.get('_audioguide_url')
            elif cid == 'http://vocab.getty.edu/aat/300133046':
                public_location_string = content

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
        'provenance_text': provenance_text if provenance_text else None,
        'credit_line': credit_line if credit_line else None,
        'public_location_string': public_location_string if public_location_string else None,
        'audio_guide_transcript': audio_guide_transcript,
        'audio_guide_url': audio_guide_url,
    }

def is_art_object_url(url: str) -> bool:
    """Check if URL points to an actual art object (not VisualItem, Dimension, Set, etc.)"""
    return '/obj/' in url

async def fetch_linked_art_object(session: aiohttp.ClientSession, object_id: str, semaphore: asyncio.Semaphore) -> Optional[Dict[str, Any]]:
    """Fetch full linked art record. Retries on resets/timeouts (server often drops bursty traffic)."""
    timeout = aiohttp.ClientTimeout(total=60)
    last_err: Optional[BaseException] = None
    async with semaphore:
        for attempt in range(FETCH_RETRIES):
            try:
                async with session.get(object_id, timeout=timeout) as response:
                    response.raise_for_status()
                    return await response.json()
            except aiohttp.ClientResponseError as e:
                last_err = e
                if e.status == 404:
                    return None
                if attempt < FETCH_RETRIES - 1:
                    await asyncio.sleep(FETCH_BACKOFF_SEC * (2**attempt))
                continue
            except (aiohttp.ClientError, asyncio.TimeoutError, OSError, ConnectionResetError) as e:
                last_err = e
                if attempt < FETCH_RETRIES - 1:
                    await asyncio.sleep(FETCH_BACKOFF_SEC * (2**attempt))
                continue
            except Exception as e:
                last_err = e
                break
    if last_err:
        err_msg = str(last_err).strip() or type(last_err).__name__
        if "404" not in err_msg and "timeout" not in err_msg.lower():
            print(f"Error fetching {object_id} after {FETCH_RETRIES} attempts: {err_msg}")
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

def _row_from_processed_item(item: Dict[str, Any]) -> Dict[str, Any]:
    fields = item["fields"]
    return {
        "id": fields["id"],
        "is_on_view": item["is_on_view"],
        "linked_art_json": item["linked_art_json"],
        **{k: v for k, v in fields.items() if k not in ["id", "type"]},
    }


EXISTING_ID_CHUNK = 30  # keep PostgREST URL size reasonable (long object URIs)


def write_batch_to_db(batch: List[Dict[str, Any]]) -> tuple[int, int]:
    """Write a batch: upsert **on-view** rows (insert or replace); for **off-view**, only
    ``UPDATE`` rows that already exist (set ``is_on_view`` false and refresh JSON). Never
    insert a new row for an object that is only off-view.

    Returns (on_view_upserted, off_view_existing_updated).
    """
    on_rows: List[Dict[str, Any]] = []
    off_items: List[Dict[str, Any]] = []
    for item in batch:
        if item["is_on_view"]:
            on_rows.append(_row_from_processed_item(item))
        else:
            off_items.append(item)

    # Dedupe by id within batch (last wins)
    if on_rows:
        by_id = {r["id"]: r for r in on_rows}
        on_rows = list(by_id.values())

    on_n = 0
    if on_rows:
        try:
            supabase.table("objects").upsert(on_rows).execute()
            on_n = len(on_rows)
        except Exception as e:
            print(f"Error upserting on-view object batch: {e}")
            return (0, 0)

    off_updated = 0
    if not off_items:
        return (on_n, off_updated)

    off_by_id = {item["fields"]["id"]: item for item in off_items}
    off_ids = list(off_by_id.keys())

    existing: set = set()
    for i in range(0, len(off_ids), EXISTING_ID_CHUNK):
        chunk = off_ids[i : i + EXISTING_ID_CHUNK]
        try:
            r = supabase.table("objects").select("id").in_("id", chunk).execute()
            for row in r.data or []:
                existing.add(row["id"])
        except Exception as e:
            print(f"Error resolving existing ids for off-view updates: {e}")

    for oid in off_ids:
        if oid not in existing:
            continue
        item = off_by_id[oid]
        row = _row_from_processed_item(item)
        row["is_on_view"] = False
        try:
            upd = supabase.table("objects").update(row).eq("id", oid).execute()
            data = upd.data
            if data:
                off_updated += len(data) if isinstance(data, list) else 1
        except Exception as e:
            print(f"Error updating off-view object {oid}: {e}")

    return (on_n, off_updated)

async def process_change_page(session: aiohttp.ClientSession, page_url: str, semaphore: asyncio.Semaphore) -> tuple[int, int]:
    """Process a single change page. Returns (on_view_upserted, off_view_existing_updated)."""
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
            on_n, off_n = write_batch_to_db(batch)
            on_view_count += on_n
            off_view_count += off_n
    
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
    print(f"Concurrent object fetches capped at {MAX_CONCURRENT_REQUESTS} (set HARVEST_MAX_CONCURRENT to change).")
    if start_page:
        print(f"Resuming from page {start_page}")
    
    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    total_on_view = 0
    total_off_view = 0

    connector = aiohttp.TCPConnector(
        limit=max(32, MAX_CONCURRENT_REQUESTS * 2),
        limit_per_host=MAX_CONCURRENT_REQUESTS,
        ttl_dns_cache=300,
    )
    async with aiohttp.ClientSession(connector=connector, headers=DEFAULT_HEADERS) as session:
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
        
        page_number = start_page if start_page else 1
        
        while current_page:
            print(f"\n--- Processing page {page_number} ({current_page}) ---")
            start_time = time.time()
            
            on_view, off_view = await process_change_page(session, current_page, semaphore)
            total_on_view += on_view
            total_off_view += off_view
            
            elapsed = time.time() - start_time
            print(
                f"Page {page_number} complete: {on_view} on-view upserts, "
                f"{off_view} off-view updates of existing rows (took {elapsed:.1f}s)"
            )
            print(
                f"Totals this run: {total_on_view} on-view upserts, "
                f"{total_off_view} off-view updates (skipped new off-view)"
            )
            
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
    print(
        f"Total: {total_on_view} on-view upserts, {total_off_view} off-view updates "
        f"(existing rows only; new off-view objects not inserted)"
    )

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
