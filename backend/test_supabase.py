from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("SB_URL")
key = os.getenv("SB_PUBLISHABLE_KEY")

if not url or not key:
    print("Error: Missing Supabase credentials!")
    print("   Please set SB_URL and SB_PUBLISHABLE_KEY in your .env file")
    exit(1)

supabase: Client = create_client(url, key)

# Test query - read-only operation
try:
    response = supabase.table("objects").select("*").limit(1).execute()
    print("Connected to Supabase!")
    print(f"Successfully queried objects table")
    print(f" Found {len(response.data)} row(s)")
except Exception as e:
    print(f"Error querying Supabase: {e}")
