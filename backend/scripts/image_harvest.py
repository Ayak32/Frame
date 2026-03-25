import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import supabase
from backend.scripts.uri_extractor import extract_image_url

PAGE_SIZE = 1000

# postgrest-py: `.update()` returns a filter builder (`.eq()`, etc.), not a select
# builder — there is no `.select()` on that chain. Default returning is representation,
# so `.execute().data` still lists updated rows.


def upsert_image_url():
    offset = 0
    updated = 0
    no_url = 0
    update_zero_rows = 0
    errors = 0
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
            image_url = extract_image_url(row.get("linked_art_json") or {})
            if not image_url:
                no_url += 1
                continue

            try:
                upd = (
                    supabase.table('objects_on_view')
                    .update({'image_url': image_url})
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
    upsert_image_url()
