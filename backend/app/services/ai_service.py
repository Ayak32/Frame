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
    {"object_id": "...", "title": "...", "narrative": "...", "order": 1, "gallery_number": "..."},
    ...
  ]
}

Here is some additional context about art history that may be useful depending on the user's query:
- impressionism is a style of painting that emerged in the late 19th century in France. It is characterized by the use of bright colors and loose brushstrokes.
- impressionist artists include Claude Monet, Pierre-Auguste Renoir, Edgar Degas, Camille Pissarro, Berthe Morisot, Alfred Sisley, Gustave Caillebotte, Edouard Manet, Paul Cézanne, among others.
- Like their French counterparts, the American Impressionists each had their own distinct style, and depicted a range of subjects, from interior scenes to landscapes. In both France and America, classically Impressionist subjects emerged. Many American Impressionists painted the New England coastline, exploring the effect of light on water, as Monet had in France. The views they captured, however, were distinctly New World.
- American impressionist artist include John Singer Sargent, Childe Hassam, William Merritt Chase, Mary Cassatt, James McNeill Whistler, Joseph Pennell, Thomas Wilmer Dewing, Mary Nimmo Moran, Thomas Moran, among others
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


