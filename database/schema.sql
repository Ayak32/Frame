
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Museum objects (on or off view). Harvest sets is_on_view from Linked Art.
-- Extracted fields from Linked Art JSON for fast queries
CREATE TABLE IF NOT EXISTS objects (
    id TEXT PRIMARY KEY,  -- Full Linked Art URI (e.g., https://media.art.yale.edu/content/lux/obj/69.json)
    is_on_view BOOLEAN NOT NULL DEFAULT true,  -- From Yale "On view" linguistic object
    linked_art_json JSONB NOT NULL,  -- Complete Linked Art record
    title TEXT,  -- Extracted from _label
    creator_id TEXT,  -- Extracted from produced_by.part[].carried_out_by[].id
    creator_name TEXT,  -- Extracted from produced_by.part[].carried_out_by[]._label
    visual_item_id TEXT,
    accession_number TEXT,  -- Acquisition number (e.g., "1832.3")
    system_number TEXT,  -- System-assigned number for URL (e.g., "69")
    classification TEXT[],  -- Array of classifications (e.g., ["Paintings", "portraits"])
    date_created TEXT,  -- From produced_by.timespan (e.g., "1786–1820")
    materials TEXT[],  -- Array from made_of (e.g., ["canvas", "oil paint"])
    dimensions_text TEXT,  -- Human-readable dimensions (e.g., "21 1/4 × 31 1/4 in.")
    culture TEXT,  -- Culture classification (e.g., "American")
    period TEXT,  -- Period classification (e.g., "18th century")
    image_url TEXT,  -- URL of the image of the object
    gallery_number TEXT,  -- Gallery identifier (e.g., "137", "131a", "137-13")
    public_location_string TEXT,  -- Full location description from linked art json
    private_location_string TEXT,  -- Full location description from CSV
    gallery_base_number INTEGER,  -- Numeric part of gallery number for filtering (e.g., 137 from "137-13")
    case_number INTEGER,  -- Case number if present (e.g., 13 from "137-13"), NULL if not applicable
    floor_number INTEGER,  -- Floor number (derived from gallery number)
    floor_label TEXT,  -- Human-readable floor label (e.g., "Lower Level", "First Floor", "1E", "Second Floor")
    text_embedding vector(1536),  -- OpenAI ada-002 embedding for semantic search
    provenance_text TEXT,  -- LinguisticObject classified as Provenance (referred_to_by)
    credit_line TEXT,  -- LinguisticObject classified as Credit Line
    audio_guide_transcript TEXT,
    audio_guide_url TEXT,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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

-- Gallery layout (for pathfinding / map overlay)
-- Uniqueness is (floor_number, gallery_number): same gallery label may exist on different floors.
CREATE TABLE IF NOT EXISTS galleries (
    id SERIAL PRIMARY KEY,
    gallery_number TEXT NOT NULL,
    floor_number INTEGER,
    coordinates JSONB,  -- normalized { nx, ny, floor_number, ... } or legacy {x, y}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT galleries_floor_gallery_unique UNIQUE (floor_number, gallery_number)
);

CREATE TABLE floor_plans (
    id              SERIAL PRIMARY KEY,
    ref             TEXT NOT NULL UNIQUE,   -- e.g. 'floor2_plan_v1'; matches JSON ref / app bundle id
    floor_number    INTEGER NOT NULL,
    image_url       TEXT NOT NULL,          -- Supabase Storage or CDN URL; or NULL if app-bundled only
    width_px        INTEGER,                -- optional: intrinsic image size at digitization time
    height_px       INTEGER,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);



-- objects indexes
CREATE INDEX IF NOT EXISTS idx_gallery_number ON objects(gallery_number);
CREATE INDEX IF NOT EXISTS idx_gallery_base ON objects(gallery_base_number);
-- Composite: match_objects (floor + gallery), get_objects_by_gallery(..., floor_number=...),
-- and get_objects_by_floor (left-prefix on floor_number). Replaces a standalone floor-only index.
CREATE INDEX IF NOT EXISTS idx_objects_floor_gallery ON objects(floor_number, gallery_number);
CREATE INDEX IF NOT EXISTS idx_creator ON objects(creator_id);
CREATE INDEX IF NOT EXISTS idx_system_number ON objects(system_number);  -- Fast URL lookups
CREATE INDEX IF NOT EXISTS idx_accession ON objects(accession_number);  -- Historical queries
CREATE INDEX IF NOT EXISTS idx_classification ON objects USING GIN(classification);  -- Type filtering
-- date_created is free-text (e.g. "1786–1820"), not a real date type — btree is only useful for exact/sort, not ranges.
CREATE INDEX IF NOT EXISTS idx_date ON objects(date_created);
-- Embedding backfill for on-view rows only (see generate_embeddings.py).
CREATE INDEX IF NOT EXISTS idx_objects_needs_embedding ON objects(id) WHERE text_embedding IS NULL AND is_on_view = true;
CREATE INDEX IF NOT EXISTS idx_objects_is_on_view ON objects(is_on_view);
CREATE INDEX IF NOT EXISTS idx_embedding ON objects USING hnsw(text_embedding vector_cosine_ops);  -- Semantic search (cosine distance)
CREATE INDEX IF NOT EXISTS idx_has_audio ON objects(audio_guide_url) WHERE audio_guide_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_visual_item_id ON objects(visual_item_id);

-- artist indexes
CREATE INDEX IF NOT EXISTS idx_artist_id on artists(id);

-- visual items indexes
CREATE INDEX IF NOT EXISTS idx_visual_item_id on visual_items(id);
CREATE INDEX IF NOT EXISTS idx_visual_item_object_id on visual_items(object_id);
CREATE INDEX IF NOT EXISTS idx_visual_item_extracted_text on visual_items(extracted_text);


-- floor plans indexes
CREATE INDEX IF NOT EXISTS idx_floor_plan_ref on floor_plans(ref);

-- semantic search helper
CREATE OR REPLACE FUNCTION match_objects(
    search_table TEXT,
    query_embedding vector(1536),
    match_count INTEGER DEFAULT 10,
    filter_floor_number INTEGER DEFAULT NULL,
    filter_gallery_number TEXT DEFAULT NULL
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
DECLARE
    filter_sql TEXT := 'WHERE text_embedding IS NOT NULL AND is_on_view = true';
BEGIN
    IF search_table NOT IN ('objects') THEN
        RAISE EXCEPTION 'Unsupported search table: %', search_table;
    END IF;

    -- Visitor-facing search: on-view only; optional floor/gallery filters.
    IF search_table = 'objects' THEN
        filter_sql := filter_sql
            || ' AND ($3 IS NULL OR floor_number = $3)'
            || ' AND ($4 IS NULL OR gallery_number = $4)';
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
         %s
         ORDER BY text_embedding <=> $1
         LIMIT $2',
        search_table,
        filter_sql
    )
    USING query_embedding, match_count, filter_floor_number, filter_gallery_number;
END;
$$;

