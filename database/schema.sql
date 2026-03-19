
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- On-view objects (full records)
-- Extracted fields from Linked Art JSON for fast queries
CREATE TABLE IF NOT EXISTS objects_on_view (
    id TEXT PRIMARY KEY,  -- Full Linked Art URI (e.g., https://media.art.yale.edu/content/lux/obj/69.json)
    linked_art_json JSONB NOT NULL,  -- Complete Linked Art record
    title TEXT,  -- Extracted from _label
    creator_id TEXT,  -- Extracted from produced_by.part[].carried_out_by[].id
    creator_name TEXT,  -- Extracted from produced_by.part[].carried_out_by[]._label
    accession_number TEXT,  -- Acquisition number (e.g., "1832.3")
    system_number TEXT,  -- System-assigned number for URL (e.g., "69")
    classification TEXT[],  -- Array of classifications (e.g., ["Paintings", "portraits"])
    date_created TEXT,  -- From produced_by.timespan (e.g., "1786–1820")
    materials TEXT[],  -- Array from made_of (e.g., ["canvas", "oil paint"])
    dimensions_text TEXT,  -- Human-readable dimensions (e.g., "21 1/4 × 31 1/4 in.")
    culture TEXT,  -- Culture classification (e.g., "American")
    period TEXT,  -- Period classification (e.g., "18th century")
    gallery_location TEXT,  -- Gallery/room name (to be populated from gallery layout data)
    room_number TEXT,  -- Room identifier (e.g., "137", "131a", "137-13")
    location_string TEXT,  -- Full location description from CSV
    room_base_number INTEGER,  -- Numeric part of room number for filtering (e.g., 137 from "137-13")
    case_number INTEGER,  -- Case number if present (e.g., 13 from "137-13"), NULL if not applicable
    floor_number INTEGER,  -- Floor number (derived from room number)
    floor_label TEXT,  -- Human-readable floor label (e.g., "Lower Level", "First Floor", "1E", "Second Floor")
    coordinates JSONB,  -- Spatial coordinates {x, y} if available
    text_embedding vector(1536),  -- OpenAI ada-002 embedding for semantic search
    audio_guide_transcript TEXT,
    audio_guide_url TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Off-view objects (lightweight metadata for AI context)
CREATE TABLE IF NOT EXISTS objects_off_view (
    id TEXT PRIMARY KEY,  -- Full Linked Art URI
    title TEXT,  -- Extracted from _label
    creator_id TEXT,  -- Extracted from produced_by.part[].carried_out_by[].id
    creator_name TEXT,  -- Extracted from produced_by.part[].carried_out_by[]._label
    accession_number TEXT,  -- Acquisition number
    system_number TEXT,  -- System-assigned number
    date_created TEXT,  -- From produced_by.timespan
    type TEXT,  -- Object type (usually "HumanMadeObject")
    classification TEXT[],  -- Array of classifications
    related_object_ids TEXT[],  -- Links to related objects for context
    curatorial_text TEXT,  -- Museum descriptions for AI narratives
    materials TEXT[],  -- Materials array
    culture TEXT,  -- Culture classification
    period TEXT,  -- Period classification
    text_embedding vector(1536),  -- OpenAI ada-002 embedding
    audio_guide_transcript TEXT,
    audio_guide_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS artists (
    id TEXT PRIMARY KEY,
    name TEXT,
    json_record JSONB,
    wikidata_id TEXT,
    wikidata_data JSONB,
    getty_ulan_id TEXT,
    getty_ulan_data JSONB,
    loc_id TEXT,
    loc_data JSONB,
    biography_text TEXT,
    last_fetched TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS visual_items (
    id TEXT PRIMARY KEY,
    object_id TEXT,
    json_record JSONB,
    style_classifications TEXT[],
    depicted_places TEXT[],
    subject_matter TEXT[],
    extracted_text TEXT,
    last_fetched TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS external_uris (
    uri TEXT PRIMARY KEY,
    uri_type TEXT,
    data JSONB,
    extracted_text TEXT,
    last_fetched TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- Create indexes for fast queries
-- On-view objects indexes
CREATE INDEX IF NOT EXISTS idx_on_view_gallery ON objects_on_view(gallery_location);
CREATE INDEX IF NOT EXISTS idx_on_view_room ON objects_on_view(room_number);
CREATE INDEX IF NOT EXISTS idx_on_view_room_base ON objects_on_view(room_base_number);
CREATE INDEX IF NOT EXISTS idx_on_view_floor ON objects_on_view(floor_number);
CREATE INDEX IF NOT EXISTS idx_on_view_creator ON objects_on_view(creator_id);
CREATE INDEX IF NOT EXISTS idx_on_view_system_number ON objects_on_view(system_number);  -- Fast URL lookups
CREATE INDEX IF NOT EXISTS idx_on_view_accession ON objects_on_view(accession_number);  -- Historical queries
CREATE INDEX IF NOT EXISTS idx_on_view_classification ON objects_on_view USING GIN(classification);  -- Type filtering
CREATE INDEX IF NOT EXISTS idx_on_view_date ON objects_on_view(date_created);  -- Date range queries
CREATE INDEX IF NOT EXISTS idx_on_view_json ON objects_on_view USING GIN(linked_art_json);  -- JSON queries
CREATE INDEX IF NOT EXISTS idx_on_view_embedding ON objects_on_view USING hnsw(text_embedding vector_l2_ops);  -- Semantic search (L2 distance)
CREATE INDEX IF NOT EXISTS idx_on_view_has_audio ON objects_on_view(audio_guide_url) WHERE audio_guide_url IS NOT NULL;

-- Off-view objects indexes
CREATE INDEX IF NOT EXISTS idx_off_view_creator ON objects_off_view(creator_id);
CREATE INDEX IF NOT EXISTS idx_off_view_system_number ON objects_off_view(system_number);
CREATE INDEX IF NOT EXISTS idx_off_view_classification ON objects_off_view USING GIN(classification);
CREATE INDEX IF NOT EXISTS idx_off_view_date ON objects_off_view(date_created);
CREATE INDEX IF NOT EXISTS idx_off_view_text_search ON objects_off_view USING GIN(to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(curatorial_text, '')));  -- Full-text search
CREATE INDEX IF NOT EXISTS idx_off_view_embedding ON objects_off_view USING hnsw(text_embedding vector_l2_ops);  -- Semantic search (L2 distance)

-- artist indexes
CREATE INDEX IF NOT EXISTS idx_artist_id on artists(id);

-- visual items indexes
CREATE INDEX IF NOT EXISTS idx_visual_item_id on visual_items(id);
CREATE INDEX IF NOT EXISTS idx_visual_item_object_id on visual_items(object_id);
CREATE INDEX IF NOT EXISTS idx_visual_item_extracted_text on visual_items(extracted_text);

-- external uris indexes
CREATE INDEX IF NOT EXISTS idx_external_uri_uri on external_uris(uri);
CREATE INDEX IF NOT EXISTS idx_external_uri_uri_type on external_uris(uri_type);

-- semantic search helper
CREATE OR REPLACE FUNCTION match_objects(
    search_table TEXT,
    query_embedding vector(1536),
    match_count INTEGER DEFAULT 10
)
RETURNS TABLE (
    id TEXT,
    title TEXT,
    creator_name TEXT,
    creator_id TEXT,
    classification TEXT[],
    distance DOUBLE PRECISION
)
LANGUAGE plpgsql
STABLE
AS $$
BEGIN
    IF search_table NOT IN ('objects_on_view', 'objects_off_view') THEN
        RAISE EXCEPTION 'Unsupported search table: %', search_table;
    END IF;

    RETURN QUERY EXECUTE format(
        'SELECT
            id,
            title,
            creator_name,
            creator_id,
            classification,
            (text_embedding <=> $1) AS distance
         FROM %I
         WHERE text_embedding IS NOT NULL
         ORDER BY text_embedding <=> $1
         LIMIT $2',
        search_table
    )
    USING query_embedding, match_count;
END;
$$;

-- Gallery layout (for pathfinding)
CREATE TABLE IF NOT EXISTS galleries (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    floor_number INTEGER,
    coordinates JSONB,  -- {x, y} or {lat, lng}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Gallery connections (for pathfinding graph)
CREATE TABLE IF NOT EXISTS gallery_connections (
    id SERIAL PRIMARY KEY,
    from_gallery_id INTEGER REFERENCES galleries(id),
    to_gallery_id INTEGER REFERENCES galleries(id),
    distance_meters INTEGER,
    walk_time_seconds INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);