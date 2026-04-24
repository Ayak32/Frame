"""
Build embedding-ready text from object records, enriched with artist and VisualItem data.

Used by generate_embeddings.py. When include_external=True, looks up cached
artist (biography_text) and visual_items (extracted_text) from Supabase.
"""

import re
from typing import Dict, Any, List, Optional

_supabase = None

_AUDIO_GUIDE_EXCERPT_MAX = 2500


def _get_supabase():
    global _supabase
    if _supabase is None:
        import os
        from supabase import create_client
        from dotenv import load_dotenv
        load_dotenv()
        url, key = os.getenv("SB_URL"), os.getenv("SB_SECRET_KEY")
        if not url or not key:
            raise ValueError("SB_URL and SB_SECRET_KEY must be set for external lookups")
        _supabase = create_client(url, key)
    return _supabase


def _html_to_plain(text: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", text)
    return " ".join(plain.split())


def _format_value(value: Any) -> str:
    """Turn a field value into a single string. Lists become comma-separated."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(x).strip() for x in value if x is not None and str(x).strip())
    return str(value).strip()


def _add_line(parts: List[str], label: str, value: Any) -> None:
    """Append 'Label: value' to parts only if value is non-empty."""
    text = _format_value(value)
    if text:
        parts.append(f"{label}: {text}")


def _lookup_artist_biography(creator_id: Optional[str], sb) -> Optional[str]:
    """Return biography_text for this creator from artists table, or None."""
    if not creator_id:
        return None
    # Artists table may store id with or without .json
    ids_to_try = [creator_id, creator_id.rstrip("/") + ".json", creator_id.replace(".json", "")]
    for aid in ids_to_try:
        try:
            r = sb.table("artists").select("biography_text").eq("id", aid).limit(1).execute()
            if r.data and r.data[0].get("biography_text"):
                return r.data[0]["biography_text"]
        except Exception:
            continue
    return None


def _lookup_visual_content(object_id: Optional[str], sb) -> str:
    """Return combined extracted_text from all visual_items for this object."""
    if not object_id:
        return ""
    try:
        r = sb.table("visual_items").select("extracted_text").eq("object_id", object_id).execute()
        if not r.data:
            return ""
        texts = [row["extracted_text"] for row in r.data if row.get("extracted_text")]
        return " ".join(texts)
    except Exception:
        return ""


def _description_from_linked_art(linked_art_json: Optional[Dict]) -> str:
    """Pull description from referred_to_by[].content in Linked Art JSON."""
    if not linked_art_json or not isinstance(linked_art_json, dict):
        return ""
    parts = []
    for ref in linked_art_json.get("referred_to_by") or []:
        if isinstance(ref, dict) and ref.get("content"):
            parts.append(ref["content"])
    return " ".join(parts).strip() if parts else ""


def build_embedding_text_on_view(
    obj: Dict[str, Any],
    include_external: bool = True,
    supabase=None,
) -> str:
    """
    Build one string for embedding from an on-view object: object fields plus
    optional artist biography and VisualItem content from the database.
    """
    sb = supabase if supabase is not None else _get_supabase()
    parts: List[str] = []

    # Object fields
    _add_line(parts, "Title", obj.get("title"))
    _add_line(parts, "Artist", obj.get("creator_name"))

    # Enriched data from artists and visual_items tables
    if include_external:
        biography = _lookup_artist_biography(obj.get("creator_id"), sb)
        if biography:
            parts.append(f"Artist Biography: {biography}")
        visual_content = _lookup_visual_content(obj.get("id"), sb)
        if visual_content:
            parts.append(f"Visual Content: {visual_content}")

    # More object fields
    _add_line(parts, "Classification", obj.get("classification"))

    # Description: Linked Art referred_to_by content, else dimensions
    description = ""
    if obj.get("linked_art_json"):
        description = _description_from_linked_art(obj.get("linked_art_json")).strip()
    if not description:
        description = (obj.get("dimensions_text") or "").strip()
    if description:
        parts.append(f"Description: {description}")

    _add_line(parts, "Culture", obj.get("culture"))
    _add_line(parts, "Period", obj.get("period"))
    _add_line(parts, "Materials", obj.get("materials"))
    _add_line(parts, "Credit Line", obj.get("credit_line"))
    _add_line(parts, "Provenance", obj.get("provenance_text"))

    transcript = (obj.get("audio_guide_transcript") or "").strip()
    if transcript:
        plain = _html_to_plain(transcript)
        excerpt = plain[:_AUDIO_GUIDE_EXCERPT_MAX]
        if len(plain) > _AUDIO_GUIDE_EXCERPT_MAX:
            excerpt += "..."
        parts.append(f"Audio Guide Transcript (excerpt): {excerpt}")
    elif obj.get("audio_guide_url"):
        parts.append("Audio Guide: available (no transcript text in record)")

    return "\n".join(parts)

