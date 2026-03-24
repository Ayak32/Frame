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



def _fetch_object_row(object_id: str) -> Optional[Dict[str, Any]]:
    response = supabase.table("objects_on_view").select("*").eq("id", object_id).limit(1).execute()
    return response.data[0] if response.data else None


def _fetch_artist_context(creator_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not creator_id:
        return None
    response = supabase.table("artists").select("*").eq("id", creator_id).limit(1).execute()
    return response.data[0] if response.data else None


def _fetch_visual_item_context(visual_item_id: Optional[str]) -> Optional[Dict[str, Any]]:
    if not visual_item_id:
        return None
    response = supabase.table("visual_items").select("*").eq("id", visual_item_id).limit(1).execute()
    return response.data[0] if response.data else None


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve_objects_normalized(
    query: str,
    limit: int = 10,
    table: str = "objects_on_view",
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
    table: str = "objects_on_view",
    *,
    floor_number: Optional[int] = None,
    gallery_number: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve objects and hydrate each with artist, visual-item, and audio context."""
    retrieved_objects = retrieve_objects_normalized(
        query,
        limit=limit,
        table=table,
        floor_number=floor_number,
        gallery_number=gallery_number,
    )
    enriched = []

    for obj in retrieved_objects:
        object_row = _fetch_object_row(obj["id"])
        if not object_row:
            continue

        artist_result = _fetch_artist_context(object_row.get("creator_id"))
        visual_item_result = _fetch_visual_item_context(object_row.get("visual_item_id"))

        enriched.append({
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
                "audio_guide_transcript": object_row.get("audio_guide_transcript"),
                "linked_art_json": object_row.get("linked_art_json"),
                "gallery_number": object_row.get("gallery_number"),
                "location_string": object_row.get("location_string"),
                "gallery_base_number": object_row.get("gallery_base_number"),
                "case_number": object_row.get("case_number"),
                "floor_number": object_row.get("floor_number"),
                "floor_label": object_row.get("floor_label"),
            },
            "artist": {
                "name": artist_result.get("name"),
                "biography_text": artist_result.get("biography_text"),
                "wikidata_data": artist_result.get("wikidata_data"),
                "getty_ulan_data": artist_result.get("getty_ulan_data"),
                "loc_data": artist_result.get("loc_data"),
            } if artist_result else None,
            "visual_items": [
                {
                    "id": visual_item_result.get("id"),
                    "style_classifications": visual_item_result.get("style_classifications"),
                    "depicted_places": visual_item_result.get("depicted_places"),
                    "subject_matter": visual_item_result.get("subject_matter"),
                    "extracted_text": visual_item_result.get("extracted_text"),
                }
            ] if visual_item_result else [],
            "retrieval": {
                "distance": obj["distance"],
                "similarity": obj["similarity"],
            },
        })

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
        if obj.get("location_string"):
            lines.append(f"  Location String: {obj['location_string']}")
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
                "similarity": ctx["retrieval"]["similarity"],
            }
            for ctx in context_objects
            if ctx.get("object")
        ],
        "retrieved_objects": context_objects,
    }
