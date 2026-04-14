from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

project_root = Path(__file__).resolve().parents[3]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from backend.app.services.ai_service import (
    generate_tour_narrative,
    find_thematic_connections,
    thematic_hint_from_parsed,
    generate_object_description,
)
from backend.app.services.rag_service import fetch_all_floor_plans

app = FastAPI()


class TourRequest(BaseModel):
    """`query` is untrusted visitor text; keep length bounded for cost and abuse control."""

    query: str = Field(..., min_length=1, max_length=2000)
    time_limit: int
    floor_number: Optional[int] = None
    gallery_number: Optional[str] = None


class TourResponse(BaseModel):
    tour: List[Dict[str, Any]]
    themes: str
    retrieved_objects: List[Dict[str, Any]]


class FloorPlanItem(BaseModel):
    ref: str
    floor_number: int
    image_url: str
    width_px: Optional[int] = None
    height_px: Optional[int] = None


class FloorPlansResponse(BaseModel):
    floor_plans: List[FloorPlanItem]

class ObjectDescriptionRequest(BaseModel):
    object_id: str
    query: str = ""
    themes: str = ""


class ObjectDescriptionResponse(BaseModel):
    object_id: str
    narrative: str
    key_facts: List[str] = Field(default_factory=list)


def _stops_from_parsed(parsed: Any) -> List[Dict[str, Any]]:
    if isinstance(parsed, dict):
        stops = parsed.get("tour")
        if isinstance(stops, list):
            return [s for s in stops if isinstance(s, dict)]
    return []


@app.post("/tour", response_model=TourResponse)
async def generate_tour(request: TourRequest):
    topic = " ".join(request.query.split())
    if not topic:
        raise HTTPException(status_code=422, detail="Query cannot be empty or whitespace-only")
    user_query = f"A tour about {topic}"

    print(f"user_query: {user_query}")
    response = generate_tour_narrative(
        user_query,
        request.time_limit,
        request.floor_number,
        request.gallery_number,
    )
    parsed = response.get("tour")
    retrieved_objects = response.get("retrieved_objects") or []
    if not isinstance(retrieved_objects, list):
        retrieved_objects = []

    thematics_parsed = find_thematic_connections(topic, retrieved_objects)
    themes = thematic_hint_from_parsed(thematics_parsed)
    return TourResponse(
        tour=_stops_from_parsed(parsed),
        themes=themes,
        retrieved_objects=retrieved_objects,
    )


@app.get("/floor-plans", response_model=FloorPlansResponse)
async def get_floor_plans():
    rows = fetch_all_floor_plans()
    return FloorPlansResponse(floor_plans=[FloorPlanItem(**row) for row in rows])


@app.post("/objects/description", response_model=ObjectDescriptionResponse)
async def describe_object(body: ObjectDescriptionRequest):
    desc = generate_object_description(
        body.object_id,
        framing_query=body.query.strip() or None,
        thematic_hint=body.themes.strip() or None,
    )
    if not desc:
        raise HTTPException(status_code=404, detail="Object not found or not on view")
    return ObjectDescriptionResponse(
        object_id=str(desc.get("object_id") or body.object_id),
        narrative=str(desc.get("narrative") or ""),
        key_facts=list(desc.get("key_facts") or []),
    )


@app.get("/health")
async def health_check():
    return {"status": "ok"}
