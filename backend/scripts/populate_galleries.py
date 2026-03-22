"""
Populate `galleries` from distinct (floor_number, gallery_number) on `objects_on_view`.
Skips rows with empty gallery_number. Safe to re-run: only inserts missing pairs.
"""
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import supabase

PAGE_SIZE = 1000


def _pairs_from_objects() -> set:
    pairs: set = set()
    offset = 0
    while True:
        res = (
            supabase.table("objects_on_view")
            .select("gallery_number, floor_number")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        rows = res.data or []
        for row in rows:
            raw = row.get("gallery_number")
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                continue
            num = raw.strip() if isinstance(raw, str) else str(raw)
            pairs.add((row.get("floor_number"), num))
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return pairs


def _pairs_in_galleries() -> set:
    existing: set = set()
    offset = 0
    while True:
        res = (
            supabase.table("galleries")
            .select("floor_number, gallery_number")
            .range(offset, offset + PAGE_SIZE - 1)
            .execute()
        )
        rows = res.data or []
        for row in rows:
            existing.add((row.get("floor_number"), row.get("gallery_number")))
        if len(rows) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return existing


def main() -> None:
    from_objects = _pairs_from_objects()
    if not from_objects:
        print("No (floor_number, gallery_number) pairs found on objects_on_view.")
        return

    already = _pairs_in_galleries()
    missing = [(fl, gn) for fl, gn in from_objects if (fl, gn) not in already]
    missing.sort(key=lambda t: (t[0] is None, t[0] if t[0] is not None else 0, t[1]))

    if not missing:
        print(f"All {len(from_objects)} pairs already in galleries. Nothing to insert.")
        return

    batch = 200
    inserted = 0
    for i in range(0, len(missing), batch):
        chunk = [
            {"gallery_number": gn, "floor_number": fl, "coordinates": None}
            for fl, gn in missing[i : i + batch]
        ]
        supabase.table("galleries").insert(chunk).execute()
        inserted += len(chunk)

    print(
        f"Inserted {inserted} gallery row(s). "
        f"Distinct pairs on objects: {len(from_objects)}, already in galleries: {len(already)}."
    )


if __name__ == "__main__":
    main()
