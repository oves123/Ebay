from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
import os
from dotenv import load_dotenv
import requests

app = FastAPI()

# Allow frontend to access API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv("C:/Users/Oves/Desktop/Ebay/ebay-mcp/.env")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
} if SUPABASE_KEY else {}

@app.get("/api/sweep")
def get_sweep_results():
    if not SUPABASE_URL:
        return {"data": [], "status": "Supabase not configured"}
        
    try:
        res = requests.get(f"{SUPABASE_URL}/rest/v1/deep_sweep_deals?select=*", headers=headers)
        if res.status_code == 200:
            data = res.json()
            # Map snake_case back to PascalCase for the React UI to consume seamlessly
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

@app.get("/api/live")
def get_live_snipes():
    if not SUPABASE_URL:
        return {"data": [], "status": "Supabase not configured"}
        
    try:
        # Order by id descending, limit 50
        res = requests.get(f"{SUPABASE_URL}/rest/v1/live_snipes?select=*&order=id.desc&limit=50", headers=headers)
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
