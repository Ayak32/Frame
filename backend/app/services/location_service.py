import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import supabase

def get_objects_by_floor(floor_number: int) -> List[Dict[str, Any]]:
    """All on-view objects on the given floor."""
    response = (
        supabase.table("objects_on_view")
        .select("*")
        .eq("floor_number", floor_number)
        .execute()
    )
    return response.data or []


def get_objects_by_gallery(
    gallery_number: str, floor_number: Optional[int] = None
) -> List[Dict[str, Any]]:
    """Objects in a gallery. If floor_number is None, matches that gallery on any floor."""
    q = supabase.table("objects_on_view").select("*").eq("gallery_number", gallery_number)
    if floor_number is not None:
        q = q.eq("floor_number", floor_number)
    response = q.execute()
    return response.data or []


def get_objects_by_public_location_string(search_term: str) -> List[Dict[str, Any]]:
    """Substring search on public location_string (case-insensitive)."""
    pattern = f"%{search_term}%"
    response = (
        supabase.table("objects_on_view")
        .select("*")
        .ilike("public_location_string", pattern)
        .execute()
    )
    return response.data or []


def get_galleries_on_floor(floor_number: int) -> List[Dict[str, Any]]:
    """Gallery rows for one floor (gallery_number + metadata from galleries table)."""
    response = (
        supabase.table("galleries")
        .select("id, gallery_number, floor_number, coordinates")
        .eq("floor_number", floor_number)
        .execute()
    )
    return response.data or []
