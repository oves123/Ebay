import os
import requests
from dotenv import load_dotenv

load_dotenv("c:/Users/Oves/Desktop/Ebay/ebay-mcp/.env")

url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Prefer": "count=exact",
    "Range-Unit": "items",
    "Range": "0-0"
}

res = requests.get(f"{url}/rest/v1/deep_sweep_deals?select=id", headers=headers)
print("Supabase Count:", res.headers.get("content-range", "").split("/")[-1])
