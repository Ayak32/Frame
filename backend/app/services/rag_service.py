"""RAG service: retrieval, enrichment, prompt building, and LLM generation.

Sits above semantic_search and below any future tour/chat endpoint.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.config import supabase, openai_client, LLM_MODEL
from backend.app.services.semantic_search import search_objects



def fetch_object_row(object_id: str) -> Optional[Dict[str, Any]]:
    """Load one object by id (includes off-view rows; check ``is_on_view`` if needed)."""
    response = supabase.table("objects").select("*").eq("id", object_id).limit(1).execute()
    return response.data[0] if response.data else None


def _normalize_floor(f: Any) -> Optional[int]:
    if f is None:
        return None
    try:
        return int(f)
    except (TypeError, ValueError):
        return None



def _fetch_artist_context(creator_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not creator_id:
        return None
    response = (
        supabase.table("artists")
        .select("name, biography_text")
        .eq("id", creator_id)
        .limit(1)
        .execute()
    )
    return response.data[0] if response.data else None


def _fetch_visual_item_context(visual_item_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not visual_item_id:
        return None
    response = supabase.table("visual_items").select("*").eq("id", visual_item_id).limit(1).execute()
    return response.data[0] if response.data else None


def _fetch_gallery_coordinates(
    gallery_number: Optional[str],
    floor_number: Optional[Any],
) -> Optional[Dict[str, Any]]:
    fnum = _normalize_floor(floor_number)
    if gallery_number is None or fnum is None:
        return None
    g = str(gallery_number).strip()
    if not g:
        return None
    response = (
        supabase.table("galleries")
        .select("coordinates")
        .eq("gallery_number", g)
        .eq("floor_number", fnum)
        .limit(1)
        .execute()
    )
    return response.data[0].get("coordinates") if response.data else None


def _fetch_floor_plan_image_url(floor_number: Optional[Any]) -> Optional[str]:
    fn = _normalize_floor(floor_number)
    if fn is None:
        return None
    response = (
        supabase.table("floor_plans")
        .select("image_url")
        .eq("floor_number", fn)
        .order("ref")
        .limit(1)
        .execute()
    )
    return response.data[0].get("image_url") if response.data else None


def fetch_all_floor_plans() -> List[Dict[str, Any]]:
    """All floor plan rows for map UI: ordered by floor, then ref (stable if multiple per floor)."""
    response = (
        supabase.table("floor_plans")
        .select("ref, floor_number, image_url, width_px, height_px")
        .order("floor_number")
        .order("ref")
        .execute()
    )
    return response.data if response.data else []


def _enrich_object_row(object_row: Dict[str, Any]) -> Dict[str, Any]:
    """One RAG/API row. Artist fields exclude authority JSON blobs (not loaded for this path)."""
    artist_result = _fetch_artist_context(object_row.get("creator_id"))
    visual_item_result = _fetch_visual_item_context(object_row.get("visual_item_id"))
    gallery_coordinates = _fetch_gallery_coordinates(
        object_row.get("gallery_number"),
        object_row.get("floor_number"),
    )
    floor_plan_image_url = _fetch_floor_plan_image_url(object_row.get("floor_number"))

    return {
        "object": {
            "id": object_row.get("id"),
            "title": object_row.get("title"),
            "creator_name": object_row.get("creator_name"),
            "creator_id": object_row.get("creator_id"),
            "classification": object_row.get("classification"),
            "culture": object_row.get("culture"),
            "period": object_row.get("period"),
            "materials": object_row.get("materials"),
            "description": object_row.get("dimensions_text"),
            "provenance_text": object_row.get("provenance_text"),
            "credit_line": object_row.get("credit_line"),
            "audio_guide_transcript": object_row.get("audio_guide_transcript"),
            "image_url": object_row.get("image_url"),
            "gallery_number": object_row.get("gallery_number"),
            "public_location_string": object_row.get("public_location_string"),
            "gallery_base_number": object_row.get("gallery_base_number"),
            "case_number": object_row.get("case_number"),
            "floor_number": object_row.get("floor_number"),
            "floor_label": object_row.get("floor_label"),
        },
        "gallery_coordinates": gallery_coordinates,
        "floor_plan_image_url": floor_plan_image_url,
        "artist": {
            "name": artist_result.get("name"),
            "biography_text": artist_result.get("biography_text"),
        }
        if artist_result
        else None,
        "visual_items": [
            {
                "id": visual_item_result.get("id"),
                "style_classifications": visual_item_result.get("style_classifications"),
                "depicted_places": visual_item_result.get("depicted_places"),
                "subject_matter": visual_item_result.get("subject_matter"),
                "extracted_text": visual_item_result.get("extracted_text"),
            }
        ]
        if visual_item_result
        else [],
    }


def enrich_object_context(object_id: str) -> Optional[Dict[str, Any]]:
    """Full enriched context for one on-view object (for descriptions / detail API)."""
    row = fetch_object_row(object_id)
    if not row:
        return None
    return _enrich_object_row(row)


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve_objects_normalized(
    query: str,
    limit: int = 10,
    table: str = "objects",
    *,
    floor_number: Optional[int] = None,
    gallery_number: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Thin wrapper around semantic search — returns normalized hits."""
    results = search_objects(
        query,
        limit=limit,
        table=table,
        floor_number=floor_number,
        gallery_number=gallery_number,
    )
    return [
        {
            "id": obj["id"],
            "title": obj["title"],
            "creator_name": obj["creator_name"],
            "creator_id": obj["creator_id"],
            "classification": obj["classification"],
            "distance": obj["distance"],
            "similarity": obj["similarity"],
        }
        for obj in results
    ]


def retrieve_objects(
    query: str,
    limit: int = 10,
    table: str = "objects",
    *,
    floor_number: Optional[int] = None,
    gallery_number: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve objects and hydrate each with artist, visual-item, and audio context.

    Order matches semantic search: nearest embedding distance to the query first (most relevant).
    """
    retrieved_objects = retrieve_objects_normalized(
        query,
        limit=limit,
        table=table,
        floor_number=floor_number,
        gallery_number=gallery_number,
    )
    enriched = []

    for obj in retrieved_objects:
        object_row = fetch_object_row(obj["id"])
        if not object_row:
            continue

        base = _enrich_object_row(object_row)
        base["retrieval"] = {
            "distance": obj["distance"],
            "similarity": obj["similarity"],
        }
        enriched.append(base)

    return enriched


# ---------------------------------------------------------------------------
# Prompt building
# ---------------------------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = (
    "You are a knowledgeable guide at the Yale University Art Gallery. "
    "Answer the visitor's question using ONLY the provided object context. "
    "Cite objects by their bracketed number (e.g. [1]) when referencing them. "
    "If the context is insufficient, say so honestly."
)


def _format_list(values: Optional[list]) -> str:
    if not values:
        return ""
    return ", ".join(str(v) for v in values if v)


def build_user_prompt(query: str, context_objects: List[Dict[str, Any]]) -> str:
    """Format enriched context objects into a numbered, LLM-friendly prompt."""
    parts = []
    for i, ctx in enumerate(context_objects, 1):
        obj = ctx.get("object") or {}
        obj_id = obj.get("id")
        artist = ctx.get("artist") or {}
        vis_items = ctx.get("visual_items") or []
        vis = vis_items[0] if vis_items else {}




        lines = [f"[{i}] {obj.get('title', 'Untitled')}"]
        if obj_id:
            lines.append(f"  Object ID: {obj_id}")
        if obj.get("creator_name"):
            lines.append(f"  Artist: {obj['creator_name']}")
        if obj.get("classification"):
            lines.append(f"  Classification: {_format_list(obj['classification'])}")
        if obj.get("culture"):
            lines.append(f"  Culture: {obj['culture']}")
        if obj.get("period"):
            lines.append(f"  Period: {obj['period']}")
        if obj.get("materials"):
            lines.append(f"  Materials: {_format_list(obj['materials'])}")
        if obj.get("public_location_string"):
            lines.append(f"  Location String: {obj['public_location_string']}")
        if obj.get("gallery_number"):
            lines.append(f"  Gallery Number: {obj['gallery_number']}")
        if obj.get("gallery_base_number"):
            lines.append(f"  Gallery Base Number: {obj['gallery_base_number']}")
        if obj.get("case_number"):
            lines.append(f"  Case Number: {obj['case_number']}")
        if obj.get("floor_number") is not None:
            lines.append(f"  Floor Number: {obj['floor_number']}")
        if obj.get("floor_label"):
            lines.append(f"  Floor Label: {obj['floor_label']}")
        if obj.get("description"):
            lines.append(f"  Description: {obj['description']}")
        if obj.get("credit_line"):
            lines.append(f"  Credit Line: {obj['credit_line']}")
        if obj.get("provenance_text"):
            lines.append(f"  Provenance: {obj['provenance_text']}")
        if vis.get("style_classifications"):
            lines.append(f"  Style Classifications: {_format_list(vis['style_classifications'])}")
        if vis.get("subject_matter"):
            lines.append(f"  Subject Matter: {_format_list(vis['subject_matter'])}")
        if artist.get("biography_text"):
            lines.append(f"  Artist Biography: {artist['biography_text']}")
        if vis.get("extracted_text"):
            lines.append(f"  Visual Content: {vis['extracted_text']}")
        if obj.get("audio_guide_transcript"):
            lines.append(f"  Audio Guide Transcript: {obj['audio_guide_transcript']}")

        parts.append("\n".join(lines))

    objects_text = "\n\n".join(parts)
    if query and query.strip():
        return f"Question: {query}\n\nRelevant objects:\n\n{objects_text}"
    return f"Relevant objects:\n\n{objects_text}"



def call_llm(
    query: Optional[str],
    context_objects: List[Dict[str, Any]],
    system_prompt: Optional[str] = None,
    *,
    user_prompt: Optional[str] = None,
    response_format: Optional[Dict[str, Any]] = None,
    parse_json: bool = False,
) -> Dict[str, Any]:
    """Call the LLM using provided context objects.

    - If `user_prompt` is provided, it is used verbatim.
    - Otherwise, `query` is used to build the default user prompt (it is omitted if blank).
    - If `parse_json` is True, attempts to JSON-decode the model response and returns it as `parsed`.
    """
    if user_prompt is None:
        user_prompt = build_user_prompt(query or "", context_objects)

    create_kwargs: Dict[str, Any] = {
        "model": LLM_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt or DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    if response_format is not None:
        create_kwargs["response_format"] = response_format

    response = openai_client.chat.completions.create(**create_kwargs)

    answer = response.choices[0].message.content

    parsed: Any = None
    if parse_json:
        try:
            parsed = json.loads(answer)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM did not return valid JSON: {exc}") from exc

    return {
        "answer": answer,
        "parsed": parsed,
        "sources": [
            {
                "id": ctx["object"]["id"],
                "title": ctx["object"].get("title"),
                "similarity": (ctx.get("retrieval") or {}).get("similarity"),
            }
            for ctx in context_objects
            if ctx.get("object")
        ],
        "retrieved_objects": context_objects,
    }
