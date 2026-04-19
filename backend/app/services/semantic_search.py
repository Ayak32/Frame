"""Semantic search helpers backed by Supabase + pgvector.

This module embeds a user query with OpenAI, then asks Supabase to run a
pgvector similarity search using a SQL RPC function (`match_objects`).

The database function performs `ORDER BY text_embedding <=> ...` and restricts
results to rows with ``is_on_view = true`` (see ``database/schema.sql``).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence
import sys
from pathlib import Path

# When this file is executed directly, add the project root so `backend.*`
# imports resolve the same way they do under `python -m`.
project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


from backend.app.config import EMBEDDING_MODEL, openai_client as default_openai_client, supabase as default_supabase
from backend.app.services.retrieval_query_expansion import expand_query_for_retrieval


VALID_SEARCH_TABLES = {"objects"}


def _validate_table_name(table: str) -> str:
    """Allow only the object tables supported by the SQL function."""
    if table not in VALID_SEARCH_TABLES:
        raise ValueError(f"Unsupported search table: {table}")
    return table



def _score_from_distance(distance: Optional[float]) -> Optional[float]:
    """Convert a distance into a simple 0-1-ish score for convenience."""
    if distance is None:
        return None
    try:
        return 1.0 / (1.0 + float(distance))
    except (TypeError, ValueError):
        return None


def create_query_embedding(
    query_text: str,
    *,
    client=None,
) -> List[float]:
    """Embed a query string using the same model as stored embeddings."""
    if not query_text or not query_text.strip():
        raise ValueError("query_text must be a non-empty string")

    openai_client = client or default_openai_client
    response = openai_client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=[query_text.strip()],
    )
    return response.data[0].embedding


def search_objects_by_embedding(
    query_embedding: Sequence[float],
    limit: int = 10,
    table: str = "objects",
    *,
    floor_number: Optional[int] = None,
    gallery_number: Optional[str] = None,
    supabase_client=None,
) -> List[Dict[str, Any]]:
    """
    Search for nearest rows to an embedding.

    This expects the database function:
    `match_objects(search_table, query_embedding, match_count, filter_floor_number, filter_gallery_number)`.
    """
    table = _validate_table_name(table)
    sb = supabase_client or default_supabase

    try:
        response = sb.rpc(
            "match_objects",
            {
                "search_table": table,
                "query_embedding": list(query_embedding),
                "match_count": limit,
                "filter_floor_number": floor_number,
                "filter_gallery_number": gallery_number,
            },
        ).execute()
    except Exception as exc:
        raise RuntimeError(
            "Semantic search requires the `match_objects` SQL function. "
            "Apply the semantic search migration in `database/migrate_add_semantic_search.sql` "
            "or add the same function to `database/schema.sql`."
        ) from exc

    results = response.data or []
    for row in results:
        row["similarity"] = _score_from_distance(row.get("distance"))
    return results


def search_objects(
    query_text: str,
    limit: int = 10,
    table: str = "objects",
    *,
    floor_number: Optional[int] = None,
    gallery_number: Optional[str] = None,
    openai_client=None,
    supabase_client=None,
    expand_retrieval_query: bool = True,
) -> List[Dict[str, Any]]:
    """
    Embed free text and return the closest objects in the chosen table.

    When ``expand_retrieval_query`` is True, the string sent to the embedding API may
    append a short synonym/entity list for known tour intents (see
    ``retrieval_query_expansion``). The caller's ``query_text`` is not modified;
    only the embedding step uses the expanded form.
    """
    text_for_embedding = (
        expand_query_for_retrieval(query_text) if expand_retrieval_query else query_text
    )
    query_embedding = create_query_embedding(text_for_embedding, client=openai_client)
    return search_objects_by_embedding(
        query_embedding,
        limit=limit,
        table=table,
        floor_number=floor_number,
        gallery_number=gallery_number,
        supabase_client=supabase_client,
    )



def get_related_objects(
    object_id: str,
    limit: int = 5,
    table: str = "objects",
    *,
    supabase_client=None,
) -> List[Dict[str, Any]]:
    """
    Find objects near an existing object in vector space.

    This uses the stored embedding of the source object, then searches for its nearest
    neighbors and filters the source object out of the results.
    """
    table = _validate_table_name(table)
    sb = supabase_client or default_supabase

    response = sb.table(table).select("id, text_embedding").eq("id", object_id).limit(1).execute()
    rows = response.data or []
    if not rows:
        return []

    source_embedding = rows[0].get("text_embedding")
    if not source_embedding:
        return []

    neighbors = search_objects_by_embedding(
        source_embedding,
        limit=limit + 1,
        table=table,
        supabase_client=sb,
    )
    return [row for row in neighbors if row.get("id") != object_id][:limit]


# if __name__ == "__main__":
#     results = search_objects("American portraiture", limit=5, table="objects")
#     print(results)