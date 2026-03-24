"""
Import gallery coordinate CSVs (Figma-style exports) into Supabase.

Required columns (header row):
  floor_number, gallery_number, nx, ny, anchor, ref

Optional extra columns (ignored for DB; keep in CSV for your own records if you want):
  imageW, imageH, point_x, point_y

Stored JSON is lean: nx/ny/anchor/ref (+ floor_number for self-contained payloads).
point_x/point_y are redundant with nx/ny; image dimensions belong on `floor_plans` (width_px,
height_px) keyed by `ref`, not repeated on every gallery row.

`floor_plans` is NOT touched here — insert those rows manually in Supabase so `ref` matches the CSV.

Run from Project/:
  python -m backend.scripts.import_gallery_coordinates "/path/to/Gallery Coordinates - floor1.csv"
  python -m backend.scripts.import_gallery_coordinates floor1.csv floor2.csv --dry-run
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import supabase

REQUIRED_COLUMNS = (
    "floor_number",
    "gallery_number",
    "nx",
    "ny",
    "anchor",
    "ref",
)


def _row_coordinates(row: Dict[str, str]) -> Dict[str, Any]:
    """Build JSON for galleries.coordinates (no duplicate pixel/size fields — use floor_plans for W×H)."""
    fn = int(row["floor_number"])
    return {
        "floor_number": fn,
        "nx": float(row["nx"]),
        "ny": float(row["ny"]),
        "anchor": row["anchor"].strip(),
        "ref": row["ref"].strip(),
    }


def _normalize_gallery_number(raw: str) -> str:
    return raw.strip()


def load_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = set(REQUIRED_COLUMNS) - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path}: missing columns: {sorted(missing)}")
        return [dict(r) for r in reader]


def upsert_galleries(rows: List[Dict[str, str]], dry_run: bool) -> int:
    count = 0
    for row in rows:
        gn = _normalize_gallery_number(row["gallery_number"])
        if not gn:
            print(f"Skip row with empty gallery_number: {row}", file=sys.stderr)
            continue
        floor_number = int(row["floor_number"])
        coords = _row_coordinates(row)
        payload = {
            "gallery_number": gn,
            "floor_number": floor_number,
            "coordinates": coords,
        }
        if dry_run:
            print(f"[dry-run] galleries upsert: {json.dumps(payload, default=str)}")
            count += 1
            continue
        supabase.table("galleries").upsert(
            payload,
            on_conflict="floor_number,gallery_number",
        ).execute()
        count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import gallery coordinate CSVs into galleries.coordinates (not floor_plans)."
    )
    parser.add_argument(
        "csv_files",
        nargs="+",
        type=Path,
        help="One or more CSV paths",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print payloads only; do not write to Supabase.",
    )
    args = parser.parse_args()

    all_rows: List[Dict[str, str]] = []
    for p in args.csv_files:
        if not p.is_file():
            print(f"Not found: {p}", file=sys.stderr)
            sys.exit(1)
        all_rows.extend(load_csv_rows(p))

    n = upsert_galleries(all_rows, dry_run=args.dry_run)
    print(f"Processed {n} gallery row(s) from {len(args.csv_files)} file(s).")


if __name__ == "__main__":
    main()
