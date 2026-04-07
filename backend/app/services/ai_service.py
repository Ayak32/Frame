import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.services.rag_service import build_user_prompt, call_llm, retrieve_objects, enrich_object_context

TOUR_SYSTEM_PROMPT = """You are a knowledgeable guide at the Yale University Art Gallery. Create a tour of the gallery using only the provided object context. If the user's query includes a cultural request (for example, "I'm interested in American portraiture"), prioritize objects from that cultural period. Similarly, if the user's query includes a particular medium (for example, "I'm interested in sculpture"), prioritize objects from that medium. Return the tour in the following JSON format. Object_id must be copied exactly from provided context; do not invent IDs: {
  "tour": [
    {"object_id": "...", "title": "...", "narrative": "...", "order": 1, "gallery_number": "..."},
    ...
  ]
}

Include one tour entry for every object in the numbered list ([1]…[N]); each object_id must match that block—no extras.
Set each stop's `order` to the same number as the object's block in the context list ([1]…[N]).

Narrative quality (apply to every stop equally): each stop's narrative must be at least four sentences and roughly the same length as the others—do not shorten later stops. Each narrative must state clearly how that object serves the visitor's query. Open by connecting to the query where the evidence allows; do not pad with generic filler.

Here is some additional context about art history that may be useful depending on the user's query:
- impressionism is a style of painting that emerged in the late 19th century in France. It is characterized by the use of bright colors and loose brushstrokes.
- impressionist artists include Claude Monet, Pierre-Auguste Renoir, Edgar Degas, Camille Pissarro, Berthe Morisot, Alfred Sisley, Gustave Caillebotte, Edouard Manet, Paul Cézanne, among others.
- Like their French counterparts, the American Impressionists each had their own distinct style, and depicted a range of subjects, from interior scenes to landscapes. In both France and America, classically Impressionist subjects emerged. Many American Impressionists painted the New England coastline, exploring the effect of light on water, as Monet had in France. The views they captured, however, were distinctly New World.
- American impressionist artist include John Singer Sargent, Childe Hassam, William Merritt Chase, Mary Cassatt, James McNeill Whistler, Joseph Pennell, Thomas Wilmer Dewing, Mary Nimmo Moran, Thomas Moran, among others
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


