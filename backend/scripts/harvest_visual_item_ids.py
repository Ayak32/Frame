import sys
import time
import argparse
from typing import Optional, List, Dict, Any, Tuple

from pathlib import Path
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import supabase
from backend.app.services.uri_extractor import extract_visual_item_uris

PAGE_SIZE = 1000

def upsert_visual_item_id():
    offset = 0
    updated = 0
    total_fetched = 0

    while True:
        response = (
            supabase.table('objects_on_view')
            .select('id, linked_art_json')
            .order('id')
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        rows = response.data or []
        total_fetched += len(rows)
        print(f"Fetched {len(rows)} objects (total so far: {total_fetched})")

        if not rows:
            break

        for row in rows:
            visual_item_uris = extract_visual_item_uris(row.get('linked_art_json') or {})
            if not visual_item_uris:
                continue

            visual_item_id = visual_item_uris[0].get('uri', '')
            if not visual_item_id:
                continue

            supabase.table('objects_on_view').update({
                'visual_item_id': visual_item_id
            }).eq('id', row['id']).execute()
            updated += 1

        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    print(f"Done. Updated {updated} of {total_fetched} objects with visual_item_id")

    print(f"Updated {updated} objects with visual_item_id")

if __name__ == "__main__":
    upsert_visual_item_id()