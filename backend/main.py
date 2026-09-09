from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import threading
import sys
import concurrent.futures
from dotenv import load_dotenv
import requests

# Add the root directory to sys.path so we can import sniper
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sniper import start_sniper_bot

app = FastAPI()

@app.on_event("startup")
def startup_event():
    print("Spawning 24/7 Sniper Bot Thread...")
    thread = threading.Thread(target=start_sniper_bot, daemon=True)
    thread.start()

# Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# load .env for local dev; on Render, env vars are injected automatically
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")

def get_headers():
    key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json"
    }

@app.get("/api/sweep")
def get_sweep_results():
    if not SUPABASE_URL:
        return {"data": [], "status": "Supabase not configured"}
        
    try:
        url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
        
        mapped_data = []
        limit = 1000
        headers = get_headers()
        
        # First, fetch one row with exact count to know how many we need
        count_res = requests.get(f"{url}/rest/v1/deep_sweep_deals?select=id&limit=1", headers=headers)
        # In PostgREST, getting exact count requires Prefer: count=exact, let's just do a quick count request
        count_headers = headers.copy()
        count_headers["Prefer"] = "count=exact"
        count_req = requests.head(f"{url}/rest/v1/deep_sweep_deals", headers=count_headers)
        total_count = int(count_req.headers.get("Content-Range", "0-0/0").split("/")[-1])
        
        if total_count == 0:
            return {"data": [], "count": 0}
            
        def fetch_chunk(offset):
            res = requests.get(f"{url}/rest/v1/deep_sweep_deals?select=*&limit={limit}&offset={offset}", headers=headers)
            if res.status_code == 200:
                return res.json()
            return []

        offsets = list(range(0, total_count, limit))
        all_raw_data = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            results = executor.map(fetch_chunk, offsets)
            for chunk in results:
                all_raw_data.extend(chunk)
                
        # Map snake_case back to PascalCase for the React UI to consume seamlessly
        for item in all_raw_data:
            mapped_data.append({
                "Query": item.get("query"),
                "Region": item.get("region"),
                "Title": item.get("title"),
                "Price": item.get("price"),
                "TimeLeft": item.get("time_left"),
                "TimeListed": item.get("time_listed"),
                "Gender": item.get("gender"),
                "BuyingOptions": item.get("buying_options"),
                "Condition": item.get("condition"),
                "Health": item.get("health"),
                "ScrapValue": item.get("scrap_value"),
                "Contacts": item.get("contacts"),
                "Seller": item.get("seller"),
                "Link": item.get("link"),
                "ExcelLink": item.get("excel_link"),
                "ImageUrl": item.get("image_url")
            })
                
        return {"data": mapped_data, "count": len(mapped_data)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/live")
def get_live_snipes():
    if not SUPABASE_URL:
        return {"data": [], "status": "Supabase not configured"}
        
    try:
        url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
        res = requests.get(f"{url}/rest/v1/live_snipes?select=*&order=id.desc&limit=50", headers=get_headers())
        if res.status_code == 200:
            data = res.json()
            mapped_data = []
            for item in data:
                mapped_data.append({
                    "Query": item.get("query"),
                    "Region": item.get("region"),
                    "Title": item.get("title"),
                    "Price": item.get("price"),
                    "TimeLeft": item.get("time_left"),
                    "TimeListed": item.get("time_listed"),
                    "Gender": item.get("gender"),
                    "BuyingOptions": item.get("buying_options"),
                    "Condition": item.get("condition"),
                    "Health": item.get("health"),
                    "ScrapValue": item.get("scrap_value"),
                    "Contacts": item.get("contacts"),
                    "Seller": item.get("seller"),
                    "Link": item.get("link"),
                    "ExcelLink": item.get("excel_link"),
                    "ImageUrl": item.get("image_url")
                })
            return {"data": mapped_data, "count": len(mapped_data)}
        else:
            return {"error": f"Supabase error: {res.text}"}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
