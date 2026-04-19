import os
from dotenv import load_dotenv
import httpx
from openai import OpenAI
from supabase import create_client, Client
from supabase.lib.client_options import SyncClientOptions


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set in .env file")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-5.4-mini"


BATCH_SIZE = 100  # For embedding generation
# Supabase PostgREST range() page size (max 1000 typical)
PAGE_SIZE = 1000
# Rough USD per 1M tokens for cost estimates in scripts (verify against OpenAI pricing for EMBEDDING_MODEL)
COST_PER_M_TOKEN = 0.02
EMBEDDING_RATE_LIMIT = 3000  # Requests per minute (OpenAI limit)
LLM_RATE_LIMIT = 500  # Requests per minute (varies by model)


SUPABASE_URL = os.getenv("SB_URL")
SUPABASE_KEY = os.getenv("SB_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SB_URL and SB_SECRET_KEY must be set in .env file")

# HTTP/2 over one long-lived connection can hit server stream limits during thousands of
# sequential PostgREST requests (e.g. embedding updates). Prefer HTTP/1.1 + pooled connections.
_supabase_http = httpx.Client(http2=False, timeout=httpx.Timeout(120.0))
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY,
    options=SyncClientOptions(httpx_client=_supabase_http),
)

API_BASE_URL = os.getenv("API_BASE_URL")
if not API_BASE_URL:
    raise ValueError("API_BASE_URL must be set in .env file")