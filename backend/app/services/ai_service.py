import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.services.rag_service import build_user_prompt, call_llm, retrieve_objects, enrich_object_context

TOUR_SYSTEM_PROMPT = """You are a knowledgeable guide at the Yale University Art Gallery.

The user message lists a fixed set of objects numbered [1] through [N]. Those objects are already chosen for this tour. Write one stop for each object in that same order—do not add, remove, or reorder stops.

Visitor alignment (prose only):
- When the visitor's question mentions culture, medium, movement, style, period, or subject matter, foreground that angle in each stop's narrative only when the object's block supports it (classification, period, materials, description, visual content, audio guide, location fields, etc.).
- If the link to the visitor's interest is weak or missing from the block, say so briefly and stay factual. Do not invent a stronger connection.

Factual grounding:
- Use only information that appears in each object's block (or is directly implied by those fields). Do not add artists' life dates, movements, subjects, or materials that are not supported there. Do not lean on general art-history knowledge to pad the answer.

Title:
- Set "title" to the object's title from its block, verbatim or as a short faithful shortening. Do not invent a new title.

gallery_number:
- If the block includes "Gallery Number:", copy that string into "gallery_number". If it is absent, use JSON null. Do not invent gallery numbers.

Narrative quality (every stop equally):
- At least four sentences per stop; keep lengths roughly similar across stops—do not shorten later entries.
- Each narrative should make clear how the object relates to the visitor's query when the evidence allows; avoid generic filler.

OUTPUT (strict):
- Return only valid JSON: no markdown code fences, no text before or after the object.
- Top level must be a single object with key "tour" (array). Each element must use exactly these snake_case keys: "object_id", "title", "narrative", "order", "gallery_number".
- Include exactly one entry per block [1]…[N]. Each "object_id" must match the "Object ID:" line in that block—no extras, no omissions, no substitutions.
- "order" must equal the bracket index (1 for [1], 2 for [2], etc.).

Example shape (structure only):
{"tour":[{"object_id":"...","title":"...","narrative":"...","order":1,"gallery_number":null}]}
"""


OBJECT_DESCRIPTION_SYSTEM_PROMPT = """You are a knowledgeable guide at the Yale University Art Gallery.

Create a museum-quality narrative about the single object in the provided context. Use ONLY facts supported by that object context (and the visitor/thematic framing in the user message when it asks you to emphasize an angle).

If the user message states a visitor interest or thematic threads for the tour, your narrative and key_facts should reflect that angle explicitly—explain how this object speaks to that interest when the metadata supports it; if the link is weak, say so briefly and stay factual.

Return ONLY valid JSON with this exact shape:
{
  "object_id": "...",
  "narrative": "...",
  "key_facts": ["..."]
}
"""


THEMATIC_SYSTEM_PROMPT = """You are a knowledgeable guide at the Yale University Art Gallery.

Identify and explain thematic connections between objects using ONLY the provided object context.

Return ONLY valid JSON with this exact shape:
{
  "theme": "...",
  "groups": [
    {"label": "...", "object_ids": ["..."], "explanation": "..."}
  ]
}
"""





def calulate_object_limit(minutes):
    return int(minutes / 6)


def thematic_hint_from_parsed(
    parsed: Optional[Dict[str, Any]],
    *,
    max_groups: int = 3,
    max_explanation_chars: int = 280,
) -> str:
    """Turn find_thematic_connections JSON into a short string for object-description framing."""
    if not parsed or not isinstance(parsed, dict):
        return ""
    groups = parsed.get("groups") or []
    lines: List[str] = []
    for g in groups[:max_groups]:
        if not isinstance(g, dict):
            continue
        label = (g.get("label") or "").strip()
        expl = (g.get("explanation") or "").strip()
        if len(expl) > max_explanation_chars:
            expl = expl[: max_explanation_chars - 1].rstrip() + "…"
        if label or expl:
            if label and expl:
                lines.append(f"- {label}: {expl}")
            elif label:
                lines.append(f"- {label}")
            else:
                lines.append(f"- {expl}")
    return "\n".join(lines)


def _object_description_user_query(
    framing_query: Optional[str],
    thematic_hint: Optional[str],
) -> Optional[str]:
    parts: List[str] = []
    fq = (framing_query or "").strip()
    th = (thematic_hint or "").strip()
    if fq:
        parts.append(f"Visitor interest: {fq}")
    if th:
        parts.append(
            "Thematic threads across objects in this tour (use for emphasis and tone only; "
            "do not invent facts not present in the object record below):\n" + th
        )
    if not parts:
        return None
    return "\n\n".join(parts)


def generate_tour_narrative_with_context(
    query: str,
    time_limit: int,
    floor_number: Optional[int] = None,
    gallery_number: Optional[str] = None,
) -> Dict[str, Any]:
    object_limit = calulate_object_limit(time_limit)
    retrieved_objects = retrieve_objects(
        query,
        limit=object_limit,
        floor_number=floor_number,
        gallery_number=gallery_number,
    )
    # Simple fallback: if strict filters yield too few candidates, relax filters.
    if (floor_number is not None or gallery_number is not None) and len(retrieved_objects) < object_limit:
        relaxed = retrieve_objects(query, limit=object_limit)
        if relaxed:
            retrieved_objects = relaxed

    n = len(retrieved_objects)
    user_prompt: Optional[str] = None
    if n:
        user_prompt = (
            f"There are {n} objects below (numbered [1]–[{n}]). "
            f"Return {n} tour entries; each entry must have the correct object_id and `order` equal to that object's block number.\n\n"
            + build_user_prompt(query, retrieved_objects)
        )

    result = call_llm(
        query=query,
        context_objects=retrieved_objects,
        system_prompt=TOUR_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        parse_json=True,
        response_format={"type": "json_object"},
    )
    return {"tour": result.get("parsed"), "retrieved_objects": result.get("retrieved_objects")}


def generate_tour_narrative(
    query,
    time_limit,
    floor_number: Optional[int] = None,
    gallery_number: Optional[str] = None,
):
    return generate_tour_narrative_with_context(
        query=query,
        time_limit=time_limit,
        floor_number=floor_number,
        gallery_number=gallery_number,
    )




def generate_object_description(
    object_id: str,
    *,
    framing_query: Optional[str] = None,
    thematic_hint: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Describe one on-view object using DB-enriched context (same shape as retrieve_objects)."""
    object_context = enrich_object_context(object_id)
    if not object_context:
        return None
    user_q = _object_description_user_query(framing_query, thematic_hint)
    result = call_llm(
        query=user_q,
        context_objects=[object_context],
        system_prompt=OBJECT_DESCRIPTION_SYSTEM_PROMPT,
        parse_json=True,
        response_format={"type": "json_object"},
    )
    return result.get("parsed")
    

def find_thematic_connections(
    user_query: str,
    retrieved_objects: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not retrieved_objects:
        return {"theme": user_query, "groups": []}

    result = call_llm(
        query=user_query,
        context_objects=retrieved_objects,
        system_prompt=THEMATIC_SYSTEM_PROMPT,
        parse_json=True,
        response_format={"type": "json_object"},
    )
    return result.get("parsed")


