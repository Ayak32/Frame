"""
Qualitative sanity checks for ai_service.

Run:
  cd Project && python backend/scripts/qualitative_test_ai_service.py

This script exercises:
- generate_tour_narrative
- generate_object_description (for the first tour stop)
- find_thematic_connections

It is not a unit test; it prints results so you can eyeball coherence.
"""

import os
from pathlib import Path
import sys
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


from backend.app.config import openai_client, LLM_MODEL, SUPABASE_URL, SUPABASE_KEY


# Prevent import-time config errors; you should still provide real keys
# via your environment/.env when actually running against Supabase + OpenAI.


os.environ.setdefault("OPENAI_API_KEY", openai_client.api_key)
os.environ.setdefault("SB_URL", SUPABASE_URL)
os.environ.setdefault("SB_SECRET_KEY", SUPABASE_KEY)

import backend.app.services.ai_service as ai_service


def main():
    query = "a tour about bright colors"
    time_limit_minutes = 60  # 1 hour

    print("=== Tour generation ===")
    tour_result = ai_service.generate_tour_narrative_with_context(
        query=query,
        time_limit=time_limit_minutes,
    )
    print(tour_result.get("tour"))

    tour = tour_result.get("tour")
    if not tour or "tour" not in tour or not tour["tour"]:
        print("No tour stops returned; skipping description/thematics.")
        return

    first_stop = tour["tour"][0]
    first_id = first_stop.get("object_id")
    print("\n=== First stop description ===")

    # Use the exact same retrieved context objects as tour generation.
    context_objects = tour_result.get("retrieved_objects") or []
    object_context = next(
        (ctx for ctx in context_objects if (ctx.get("object") or {}).get("id") == first_id),
        None,
    )

    if not object_context:
        print(f"Could not find enriched context for object_id={first_id}; skipping.")
        return

    description = ai_service.generate_object_description(object_context)
    print(description)

    print("\n=== Thematic connections ===")
    thematics = ai_service.find_thematic_connections(
        theme="bright colors",
        limit=10,
        context_objects=context_objects,
    )
    print(thematics)


if __name__ == "__main__":
    main()

