"""
Batch generate and store OpenAI embeddings for objects.

Uses text_extractor to build enriched text (with artist and VisualItem data when available),
then calls OpenAI embeddings API and writes vectors to Supabase. Supports resume (skip
objects that already have an embedding), dry-run, and progress/cost reporting.

Verify before a full run:
  1. Run tests: python backend/scripts/test_generate_embeddings.py (from project root, venv active)
  2. Dry run:  python -m backend.embeddings.generate_embeddings --dry-run --no-skip-existing
  3. One object: --limit 1 --no-skip-existing then check Supabase that text_embedding is set

Resume after a crash or Ctrl-C:
  • Default (omit --no-skip-existing): only rows with NULL text_embedding are selected, so
    anything already written is skipped automatically — just run the same command again.
  • Full re-embed (--no-skip-existing): pass --start-offset N where N is the last "Embedded N
    objects" line from the log (may re-embed up to one batch twice if the failure was mid-batch).
"""

import sys
import time
import random
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple

import httpx


project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()
from backend.app.config import openai_client, EMBEDDING_MODEL, supabase, BATCH_SIZE, PAGE_SIZE, COST_PER_M_TOKEN
from backend.embeddings.text_extractor import build_embedding_text_on_view


def get_supabase():
    return supabase


def count_tokens_approx(text: str) -> int:
    """Rough token count (chars / 4). For cost estimation only."""
    return max(1, len(text) // 4)


def _select_columns(table: str) -> str:
    """Columns needed for text extraction (``table`` reserved for future multi-table use)."""
    return (
        "id, title, creator_id, creator_name, classification, culture, period, materials, "
        "linked_art_json, provenance_text, credit_line, audio_guide_url, audio_guide_transcript, "
        "dimensions_text"
    )


def fetch_objects(
    supabase,
    table: str,
    skip_existing: bool,
    offset: int = 0,
    *,
    page_cap: Optional[int] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """Fetch a page of objects. If skip_existing, only rows where text_embedding IS NULL.
    Returns (list of rows, num_rows_from_server) so caller can advance offset correctly when
    we filter in Python. Uses order('id') for stable pagination.
    page_cap: max rows to request this page (capped at PAGE_SIZE). None means full PAGE_SIZE."""
    cap = PAGE_SIZE if page_cap is None else min(PAGE_SIZE, max(0, page_cap))
    if cap <= 0:
        return ([], 0)
    columns = _select_columns(table)
    if skip_existing:
        columns = columns + ", text_embedding"
    query = supabase.table(table).select(columns)
    if table == "objects":
        query = query.eq("is_on_view", True)
    if skip_existing:
        query = query.is_("text_embedding", "null")
    query = query.order("id").range(offset, offset + cap - 1)
    r = query.execute()
    data = r.data or []
    num_from_server = len(data)
    if skip_existing and data:
        # Keep only rows that actually have null text_embedding (server .is_() is often ignored for vector columns)
        data = [row for row in data if row.get("text_embedding") is None]
        for row in data:
            row.pop("text_embedding", None)
    return (data, num_from_server)


def build_texts_for_objects(
    objects: List[Dict],
    table: str,
    supabase,
    include_external: bool = True,
) -> List[tuple]:
    """Return list of (object_id, text) for each object. Skips objects that yield empty text."""
    builder = build_embedding_text_on_view
    out = []
    for obj in objects:
        text = builder(obj, include_external=include_external, supabase=supabase).strip()
        if not text:
            text = obj.get("title") or obj.get("id") or ""  # fallback so we don't skip
        out.append((obj["id"], text))
    return out


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Call OpenAI embeddings API for a batch of texts. Returns list of vectors."""
    if not texts:
        return []
    r = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
    # Preserve order by index
    by_index = {e.index: e.embedding for e in r.data}
    return [by_index[i] for i in range(len(texts))]


_SUPABASE_WRITE_RETRIES = 6
_SUPABASE_WRITE_BASE_DELAY = 0.4
_TRANSIENT_HTTP = (
    httpx.RemoteProtocolError,
    httpx.ConnectError,
    httpx.ReadTimeout,
    httpx.WriteTimeout,
    ConnectionError,
)


def update_embeddings(supabase, table: str, id_embedding_pairs: List[tuple]) -> None:
    """Write embeddings to Supabase (one update per row). Retries transient HTTP failures."""
    for obj_id, embedding in id_embedding_pairs:
        last_err: Optional[BaseException] = None
        for attempt in range(_SUPABASE_WRITE_RETRIES):
            try:
                supabase.table(table).update({"text_embedding": embedding}).eq("id", obj_id).execute()
                last_err = None
                break
            except _TRANSIENT_HTTP as e:
                last_err = e
                delay = _SUPABASE_WRITE_BASE_DELAY * (2**attempt) + random.uniform(0, 0.2)
                time.sleep(delay)
        if last_err is not None:
            raise last_err


def run_table(
    table: str,
    supabase,
    *,
    limit: Optional[int] = None,
    skip_existing: bool = True,
    dry_run: bool = False,
    include_external: bool = True,
    start_offset: int = 0,
) -> None:
    total_processed = 0
    total_tokens = 0
    offset = max(0, start_offset)

    print(f"Table: {table} (skip_existing={skip_existing}, dry_run={dry_run}, batch_size={BATCH_SIZE})")
    if start_offset:
        print(f"  start_offset={start_offset} (ordered by id; use after a failed --no-skip-existing run)")
    print()

    while True:
        if limit is not None:
            page_cap = limit - total_processed
            if page_cap <= 0:
                break
        else:
            page_cap = None
        requested = PAGE_SIZE if page_cap is None else min(PAGE_SIZE, page_cap)
        batch, num_from_server = fetch_objects(
            supabase, table, skip_existing, offset, page_cap=page_cap
        )
        if not batch:
            if num_from_server > 0:
                offset += num_from_server
                continue
            print("  Fetched 0 rows (none missing embedding?).")
            break

        print("  Fetched %d objects (from %d on server). Building text (Supabase lookups per object)..." % (len(batch), num_from_server))
        sys.stdout.flush()

        if limit is not None and total_processed >= limit:
            break

        id_text_pairs = build_texts_for_objects(batch, table, supabase, include_external)
        if not id_text_pairs:
            offset += num_from_server
            continue

        print("  Built text for %d objects. Embedding..." % len(id_text_pairs))
        sys.stdout.flush()

        if limit is not None:
            remaining = limit - total_processed
            id_text_pairs = id_text_pairs[:remaining]

        ids = [x[0] for x in id_text_pairs]
        texts = [x[1] for x in id_text_pairs]

        # Process in chunks of BATCH_SIZE for OpenAI
        for i in range(0, len(texts), BATCH_SIZE):
            chunk_ids = ids[i : i + BATCH_SIZE]
            chunk_texts = texts[i : i + BATCH_SIZE]
            tokens = sum(count_tokens_approx(t) for t in chunk_texts)
            total_tokens += tokens

            if dry_run:
                total_processed += len(chunk_ids)
                cost = (total_tokens / 1_000_000) * COST_PER_M_TOKEN
                print(f"  [dry run] Would embed {len(chunk_ids)} objects (~{tokens} tokens). Running total: {total_processed} objects, ~{total_tokens} tokens, ~${cost:.4f}")
                continue

            embeddings = get_embeddings(chunk_texts)
            id_embedding_pairs = list(zip(chunk_ids, embeddings))
            update_embeddings(supabase, table, id_embedding_pairs)
            total_processed += len(chunk_ids)
            print(f"  Embedded {total_processed} objects so far (~${(total_tokens/1_000_000)*COST_PER_M_TOKEN:.4f} est.)")
            time.sleep(0.1)  # gentle rate limit

        if limit is not None and total_processed >= limit:
            break
        if num_from_server < requested:
            break
        offset += num_from_server

    if dry_run and total_processed > 0:
        cost = (total_tokens / 1_000_000) * COST_PER_M_TOKEN
        print(f"\n  Dry run total: {total_processed} objects, ~{total_tokens} tokens, ~${cost:.4f} USD")
    elif total_processed == 0:
        print(f"\n  No objects to process. (If skip_existing=True, every row may already have an embedding. Try --no-skip-existing to re-embed.)")
    else:
        print(f"\n  Done. {total_processed} objects updated.")


def main():
    parser = argparse.ArgumentParser(description="Generate and store OpenAI embeddings for object tables")
    parser.add_argument("--table", choices=["on_view"], default="on_view", help="Which table(s) to process")
    parser.add_argument("--limit", type=int, default=None, help="Max objects to process (default: all)")
    parser.add_argument("--no-skip-existing", action="store_true", help="Re-embed even if text_embedding is already set")
    parser.add_argument(
        "--start-offset",
        type=int,
        default=0,
        metavar="N",
        help="Skip first N rows of the ordered result (PostgREST range). For resuming after "
        "--no-skip-existing failed: use last printed 'Embedded N objects' count.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not call OpenAI or update DB; show counts and cost estimate")
    parser.add_argument("--no-external", action="store_true", help="Do not include artist/VisualItem data in embedding text")
    args = parser.parse_args()

    print("generate_embeddings: starting (dry_run=%s, table=%s)" % (args.dry_run, args.table))
    sys.stdout.flush()

    try:
        supabase = get_supabase()
    except Exception as e:
        print("Error initializing clients: %s" % e)
        sys.exit(1)

    tables = []
    if args.table == "on_view":
        tables.append("objects")

    for table in tables:
        try:
            run_table(
                table,
                supabase,
                limit=args.limit,
                skip_existing=not args.no_skip_existing,
                dry_run=args.dry_run,
                include_external=not args.no_external,
                start_offset=args.start_offset,
            )
        except Exception as e:
            print("Error processing %s: %s" % (table, e))
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
