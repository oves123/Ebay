import json
import os
import requests
from dotenv import load_dotenv

load_dotenv("c:/Users/Oves/Desktop/Ebay/ebay-mcp/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

print("Loading deep_sweep_results.json...")
with open("c:/Users/Oves/Desktop/Ebay/deep_sweep_results.json", "r", encoding="utf-8") as f:
    all_valid_items = json.load(f)

print(f"Loaded {len(all_valid_items)} total deals.")

seen_links = set()
payload = []
for item in all_valid_items:
    link = item["Link"]
    if link in seen_links: continue
    seen_links.add(link)
    payload.append({
        "query": item["Query"],
        "region": item["Region"],
        "title": item["Title"],
        "price": item["Price"],
        "time_left": item["TimeLeft"],
        "time_listed": item["TimeListed"],
        "gender": item["Gender"],
        "buying_options": item["BuyingOptions"],
        "condition": item["Condition"],
        "health": item["Health"],
        "scrap_value": item["ScrapValue"],
        "contacts": item["Contacts"],
        "seller": item["Seller"],
        "link": item["Link"],
        "excel_link": item["ExcelLink"],
        "image_url": item["ImageUrl"]
    })

print(f"Deduped down to {len(payload)} unique deals.")

print("Clearing old Supabase data...")
requests.delete(f"{SUPABASE_URL}/rest/v1/deep_sweep_deals?id=gt.0", headers=headers)

batch_size = 1000
for i in range(0, len(payload), batch_size):
    batch = payload[i:i+batch_size]
    res = requests.post(f"{SUPABASE_URL}/rest/v1/deep_sweep_deals", headers=headers, json=batch)
    if res.status_code in (200, 201):
        print(f"Pushed batch {i//batch_size + 1}")
    else:
        print(f"Error pushing batch {i//batch_size + 1}: {res.text}")

print("DONE!")
