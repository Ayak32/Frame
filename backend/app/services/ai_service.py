import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.services.rag_service import call_llm, retrieve_objects

TOUR_SYSTEM_PROMPT= """You are a knowledgeable guide at the Yale University Art Gallery. Create a tour of the gallery using only the provided object context. If the user's query includes a cultural request (for example, "I'm interested in American portraiture"), prioritize objects from that cultural period. Return the tour in the following JSON format. Object_id must be copied exactly from provided context; do not invent IDs: {
  "tour": [
    {"object_id": "...", "title": "...", "narrative": "...", "order": 1, "room_number": "..."},
    ...
  ]
}
"""


OBJECT_DESCRIPTION_SYSTEM_PROMPT = """You are a knowledgeable guide at the Yale University Art Gallery.

Create a museum-quality narrative paragraph about the single object using ONLY the provided object context.

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





def calulate_object_limit(time_limit):
    return int(time_limit / 4)


# def _validate_and_repair_tour_ids(
#     tour_payload: Optional[Dict[str, Any]],
#     retrieved_objects: List[Dict[str, Any]],
# ) -> Dict[str, Any]:
#     if not tour_payload:
#         return {"tour": []}

#     allowed_ids = {
#         str((ctx.get("object") or {}).get("id"))
#         for ctx in retrieved_objects
#         if (ctx.get("object") or {}).get("id") is not None
#     }
#     id_by_title = {
#         ((ctx.get("object") or {}).get("title") or "").strip().lower(): str((ctx.get("object") or {}).get("id"))
#         for ctx in retrieved_objects
#         if (ctx.get("object") or {}).get("id") is not None
#     }

#     repaired_stops: List[Dict[str, Any]] = []
#     for stop in tour_payload.get("tour", []):
#         if not isinstance(stop, dict):
#             continue

#         candidate_id = stop.get("object_id")
#         candidate_id_str = str(candidate_id) if candidate_id is not None else None

#         if candidate_id_str in allowed_ids:
#             stop["object_id"] = candidate_id_str
#             repaired_stops.append(stop)
#             continue

    #     title_key = (stop.get("title") or "").strip().lower()
    #     canonical_id = id_by_title.get(title_key)
    #     if canonical_id:
    #         stop["object_id"] = canonical_id
    #         repaired_stops.append(stop)

    # repaired = dict(tour_payload)
    # repaired["tour"] = repaired_stops
    # return repaired


def generate_tour_narrative_with_context(
    query: str,
    time_limit: int,
    use_external: bool = True,
) -> Dict[str, Any]:
    object_limit = calulate_object_limit(time_limit)
    retrieved_objects = retrieve_objects(query, limit=object_limit)

    result = call_llm(
        query=query,
        context_objects=retrieved_objects,
        system_prompt=TOUR_SYSTEM_PROMPT,
        parse_json=True,
        response_format={"type": "json_object"},
    )
    return {"tour": result.get("parsed"), "retrieved_objects": result.get("retrieved_objects")}


def generate_tour_narrative(query, time_limit, use_external=True):
    return generate_tour_narrative_with_context(
        query=query,
        time_limit=time_limit,
        use_external=use_external,
    ).get("tour")




def generate_object_description(object_context):
    result = call_llm(
        query=None,
        context_objects=[object_context],
        system_prompt=OBJECT_DESCRIPTION_SYSTEM_PROMPT,
        parse_json=True,
        response_format={"type": "json_object"},
    )
    return result.get("parsed")
    

def find_thematic_connections(
    theme: str,
    limit: int = 10,
    *,
    context_objects: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    # Prefer using the exact same context objects the tour generation used.
    # This avoids mismatches caused by re-retrieval producing a different set.
    if context_objects is None:
        context_objects = retrieve_objects(theme, limit=limit)

    if not context_objects:
        return {"theme": theme, "groups": []}

    result = call_llm(
        query=theme,
        context_objects=context_objects,
        system_prompt=THEMATIC_SYSTEM_PROMPT,
        parse_json=True,
        response_format={"type": "json_object"},
    )
    return result.get("parsed")


