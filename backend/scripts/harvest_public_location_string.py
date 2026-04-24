import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import supabase
from backend.scripts.uri_extractor import extract_public_location_string

PAGE_SIZE = 1000

# postgrest-py: `.update()` returns a filter builder (`.eq()`, etc.), not a select
# builder — there is no `.select()` on that chain. Default returning is representation,
# so `.execute().data` still lists updated rows.


def upsert_public_location_string():
    offset = 0
    updated = 0
    update_zero_rows = 0
    errors = 0
    total_fetched = 0

    while True:
        response = (
            supabase.table('objects')
            .select('id, linked_art_json')
            .eq('is_on_view', True)
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
            public_location_string = extract_public_location_string(row.get("linked_art_json") or {})
            if not public_location_string:
                continue

            try:
                upd = (
                    supabase.table('objects')
                    .update({'public_location_string': public_location_string})
                    .eq('id', row['id'])
                    .execute()
                )
                data = upd.data or []
                if data:
                    updated += 1
                else:
                    update_zero_rows += 1
            except Exception:
                errors += 1

        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE

    print(
        f"Done. fetched={total_fetched} updated={updated} "
        f"no_url={no_url} zero_row_updates={update_zero_rows} errors={errors}"
    )


if __name__ == "__main__":
    upsert_public_location_string()
