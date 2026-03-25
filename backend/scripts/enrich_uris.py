import sys
import time
from datetime import datetime
from typing import Set, Dict, Any, List, Optional
import os
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from supabase import create_client, Client
from dotenv import load_dotenv
from backend.scripts.uri_extractor import (extract_external_uris, extract_creator_uris, extract_visual_item_uris)
from backend.scripts.external_fetchers import (fetch_artist, fetch_visual_item, fetch_wikidata, fetch_getty_ulan, fetch_loc, extract_text_from_external_data)

load_dotenv()

SB_URL = os.getenv("SB_URL")
SB_SECRET_KEY = os.getenv("SB_SECRET_KEY")
if not SB_URL or not SB_SECRET_KEY:
    raise ValueError("SB_URL and SB_SECRET_KEY must be set in .env file")

supabase: Client = create_client(SB_URL, SB_SECRET_KEY)


def upsert_external_uri(uri: str, uri_type: str, data: Any, extracted_text: Optional[str]) -> None:
    """Upsert one row into external_uris (generic URI cache)."""
    row = {
        'uri': uri,
        'uri_type': uri_type,
        'data': data,
        'extracted_text': extracted_text or None,
        'last_fetched': datetime.now().isoformat()
    }
    supabase.table('external_uris').upsert(row).execute()


def process_creator_uri(creator_uri: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Process a single creator URI: fetch person record, extract external URIs, fetch external data.
    
    Args:
        creator_uri: The creator/person URI
        dry_run: If True, don't actually store data
    
    Returns:
        Dict with status and any errors
    """
    if dry_run:
        return {'status': 'would_fetch', 'uri': creator_uri}
    
    try:
        # Step 1: Fetch Yale person record
        person_data = fetch_artist(creator_uri)
        if person_data.get('error'):
            err = person_data['error'] or 'Fetch failed'
            return {'status': 'error', 'error': err, 'uri': creator_uri}
        
        # Step 2: Extract external URIs from person record
        external_uris = person_data.get('external_uris', [])
        
        # Step 3: Fetch external data (Wikidata, Getty, LoC)
        wikidata_id = None
        wikidata_data = None
        wikidata_for_text = None
        getty_ulan_id = None
        getty_ulan_data = None
        loc_id = None
        loc_data = None
        
        for ext_uri_info in external_uris:
            uri_type = ext_uri_info.get('type')
            uri = ext_uri_info.get('uri')
            
            if uri_type == 'wikidata':
                wikidata_id = uri.split('/')[-1]  # Extract Q123 from URI
                wikidata_result = fetch_wikidata(uri)
                if not wikidata_result.get('error'):
                    wikidata_data = wikidata_result.get('full_data')
                    wikidata_for_text = wikidata_result  # has description/biography for biography_text
                    wd_text = extract_text_from_external_data(
                        {'description': wikidata_result.get('description'), 'biography': wikidata_result.get('biography')},
                        'wikidata'
                    )
                    upsert_external_uri(uri, 'wikidata', wikidata_data, wd_text or None)
            
            elif uri_type == 'getty_ulan':
                getty_ulan_id = uri.split('/')[-1]  # Extract ID from URI
                getty_result = fetch_getty_ulan(uri)
                if not getty_result.get('error'):
                    getty_ulan_data = getty_result.get('full_data')
                    getty_text = extract_text_from_external_data(
                        {'name': getty_result.get('name'), 'biography': getty_result.get('biography')},
                        'getty_ulan'
                    )
                    upsert_external_uri(uri, 'getty_ulan', getty_ulan_data, getty_text or None)
            
            elif uri_type == 'loc':
                loc_id = uri.split('/')[-1]  # Extract ID from URI
                loc_result = fetch_loc(uri)
                if not loc_result.get('error'):
                    loc_data = loc_result.get('full_data')
                    loc_text = extract_text_from_external_data(
                        {'name': loc_result.get('name'), 'biography': loc_result.get('biography')},
                        'loc'
                    )
                    upsert_external_uri(uri, 'loc', loc_data, loc_text or None)
        
        # Step 4: Build biography text from all sources
        biography_parts = []
        if person_data.get('biography'):
            biography_parts.append(person_data['biography'])
        if wikidata_for_text:
            wikidata_text = extract_text_from_external_data(
                {'description': wikidata_for_text.get('description'), 'biography': wikidata_for_text.get('biography')},
                'wikidata'
            )
            if wikidata_text:
                biography_parts.append(wikidata_text)
        if getty_ulan_data:
            getty_text = extract_text_from_external_data(
                {'name': getty_ulan_data.get('name'), 'biography': getty_ulan_data.get('biography')},
                'getty_ulan'
            )
            if getty_text:
                biography_parts.append(getty_text)
        
        biography_text = ' '.join(biography_parts) if biography_parts else None
        
        # Step 5: Store in artists table (upsert will overwrite if exists)
        artist_record = {
            'id': creator_uri,
            'name': person_data.get('name'),
            'json_record': person_data.get('full_record'),
            'wikidata_id': wikidata_id,
            'wikidata_data': wikidata_data,
            'getty_ulan_id': getty_ulan_id,
            'getty_ulan_data': getty_ulan_data,
            'loc_id': loc_id,
            'loc_data': loc_data,
            'biography_text': biography_text,
            'last_fetched': datetime.now().isoformat()
        }
        
        supabase.table('artists').upsert(artist_record).execute()
        
        return {'status': 'success', 'uri': creator_uri}
    
    except Exception as e:
        err = str(e).strip() or f"{type(e).__name__}"
        return {'status': 'error', 'error': err, 'uri': creator_uri}

        

def process_visual_item_uri(visual_item_uri: str, object_id: str, dry_run: bool = False) -> Dict[str, Any]:
    """
    Process a single VisualItem URI: fetch VisualItem record, extract styles/places/subjects.
    
    Args:
        visual_item_uri: The VisualItem URI
        object_id: The parent object ID (for linking)
        dry_run: If True, don't actually store data
    
    Returns:
        Dict with status and any errors
    """
    if dry_run:
        return {'status': 'would_fetch', 'uri': visual_item_uri}
    
    try:
        # Fetch VisualItem record
        visual_item_data = fetch_visual_item(visual_item_uri)
        if visual_item_data.get('error'):
            err = visual_item_data['error'] or 'Fetch failed'
            return {'status': 'error', 'error': err, 'uri': visual_item_uri}
        
        # Store in visual_items table (upsert will overwrite if exists)
        visual_item_record = {
            'id': visual_item_uri,
            'object_id': object_id,
            'json_record': visual_item_data.get('full_record'),
            'style_classifications': visual_item_data.get('style_classifications', []),
            'depicted_places': visual_item_data.get('depicted_places', []),
            'subject_matter': visual_item_data.get('subject_matter', []),
            'extracted_text': visual_item_data.get('extracted_text'),
            'last_fetched': datetime.now().isoformat()
        }
        
        supabase.table('visual_items').upsert(visual_item_record).execute()
        
        return {'status': 'success', 'uri': visual_item_uri}
    
    except Exception as e:
        err = str(e).strip() or f"{type(e).__name__}"
        return {'status': 'error', 'error': err, 'uri': visual_item_uri}

PAGE_SIZE = 1000  # Supabase max per request


def enrich_on_view(dry_run: bool = False, limit: Optional[int] = None, start_from: int = 0):
    """
    Enrich on-view objects with external data.
    
    Args:
        dry_run: If True, don't actually store data
        limit: Maximum number of objects to process (None for all)
        start_from: Start from this object index (for resuming)
    """
    print("Starting enrichment of on-view objects...")
    
    processed_creator_uris: Set[str] = set()
    processed_visual_item_uris: Set[str] = set()
    stats = {
        'objects_processed': 0,
        'creators_fetched': 0,
        'creators_errors': 0,
        'visual_items_fetched': 0,
        'visual_items_errors': 0
    }
    
    offset = start_from
    while True:
        batch = (
            supabase.table('objects_on_view')
            .select('id, linked_art_json, creator_id')
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        ).data
        
        if not batch:
            if offset == start_from:
                print("No objects found")
            break
        
        for i, obj in enumerate(batch):
            if limit and stats['objects_processed'] >= limit:
                break
            n = stats['objects_processed'] + 1
            print(f"\n[{n}] Processing object: {obj.get('id', 'unknown')}")
            
            linked_art_json = obj.get('linked_art_json', {})
            object_id = obj.get('id')
            
            for creator_uri_info in extract_creator_uris(linked_art_json):
                creator_uri = creator_uri_info.get('uri')
                if not creator_uri or creator_uri in processed_creator_uris:
                    continue
                processed_creator_uris.add(creator_uri)
                print(f"  Processing creator: {creator_uri}")
                result = process_creator_uri(creator_uri, dry_run)
                if result['status'] == 'success':
                    stats['creators_fetched'] += 1
                elif result['status'] == 'error':
                    stats['creators_errors'] += 1
                    print(f"    Error: {result.get('error') or 'Unknown error'}")
                time.sleep(0.1)
            
            for visual_item_uri_info in extract_visual_item_uris(linked_art_json):
                visual_item_uri = visual_item_uri_info.get('uri')
                if not visual_item_uri or visual_item_uri in processed_visual_item_uris:
                    continue
                processed_visual_item_uris.add(visual_item_uri)
                print(f"  Processing VisualItem: {visual_item_uri}")
                result = process_visual_item_uri(visual_item_uri, object_id, dry_run)
                if result['status'] == 'success':
                    stats['visual_items_fetched'] += 1
                elif result['status'] == 'error':
                    stats['visual_items_errors'] += 1
                    print(f"    Error: {result.get('error') or 'Unknown error'}")
                time.sleep(0.1)
            
            stats['objects_processed'] += 1
            if stats['objects_processed'] % 10 == 0:
                print(f"\nProgress: {stats['objects_processed']} objects processed | {stats}")
        
        if limit and stats['objects_processed'] >= limit:
            break
        if len(batch) < PAGE_SIZE:
            break
        offset += len(batch)
    
    print("\n" + "="*50)
    print("Enrichment complete!")
    print(f"Final stats: {stats}")



def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Enrich objects with external URI data')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    parser.add_argument('--limit', type=int, help='Limit number of objects to process')
    parser.add_argument('--start-from', type=int, default=0, help='Start from this object index')
    parser.add_argument('--table', choices=['on_view', 'off_view', 'both'], default='on_view',
                       help='Which table to process')

    args = parser.parse_args()

    if args.dry_run:
        print("Dry Run mode. No data will be stored")
    if args.table in ['on_view', 'both']:
        enrich_on_view(dry_run=args.dry_run, limit=args.limit, start_from=args.start_from)
    
    if args.table in ['off_view', 'both']:
        # enrich_off_view(dry_run=args.dry_run, limit=args.limit, start_from=args.start_from)
        pass



if __name__ == "__main__":
    main()