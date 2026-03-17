import os
from dotenv import load_dotenv

from openai import OpenAI
from supabase import create_client, Client


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY must be set in .env file")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

EMBEDDING_MODEL = "text-embedding-3-small"
LLM_MODEL = "gpt-4o-mini"


BATCH_SIZE = 100  # For embedding generation
EMBEDDING_RATE_LIMIT = 3000  # Requests per minute (OpenAI limit)
LLM_RATE_LIMIT = 500  # Requests per minute (varies by model)


SUPABASE_URL = os.getenv("SB_URL")
SUPABASE_KEY = os.getenv("SB_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SB_URL and SB_SECRET_KEY must be set in .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)