import csv
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

csv_file = "c:/Users/Oves/Desktop/Ebay/deep_sweep_results.csv"
print(f"Loading {csv_file}...")

all_valid_items = []
with open(csv_file, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        all_valid_items.append(row)

print(f"Loaded {len(all_valid_items)} total deals from CSV.")

seen_links = set()
payload = []
for item in all_valid_items:
    link = item.get("Link")
    if not link or link in seen_links: continue
    seen_links.add(link)
    
    # Parse price safely
    try:
        price = int(float(item.get("Price (USD)", 0)))
    except:
        price = 0
        
    payload.append({
        "query": item.get("Query", ""),
        "region": item.get("Region", ""),
        "title": item.get("Title", ""),
        "price": price,
        "time_left": item.get("Time Left", ""),
        "time_listed": "Unknown", # Not stored in CSV unfortunately, but not critical
        "gender": "Unknown", # We'll just infer or leave unknown
        "buying_options": item.get("Buying Options", ""),
        "condition": item.get("Condition", "Unknown"),
        "health": item.get("Health", "UNKNOWN"),
        "scrap_value": item.get("Scrap Value", "N/A"),
        "contacts": item.get("Off-Market Contacts", "None"),
        "seller": item.get("Seller", "Unknown"),
        "link": link,
        "excel_link": f'=HYPERLINK("{link}", "Open eBay")',
        "image_url": item.get("Image", "")
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
