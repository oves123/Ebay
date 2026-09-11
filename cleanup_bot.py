import os
import requests
import concurrent.futures
from dotenv import load_dotenv

def check_if_sold(item):
    """
    Fetches the eBay URL to check if the listing is ended, sold, or out of stock.
    Returns the item_id if it should be deleted, otherwise None.
    """
    url = item.get("link")
    if not url:
        return item.get("id")

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=10)
        
        # If page doesn't exist, it's gone
        if res.status_code == 404:
            return item.get("id")
            
        html = res.text.lower()
        
        # Common eBay "Ended" or "Sold" phrases in HTML
        ended_phrases = [
            "this listing was ended",
            "this item is out of stock",
            "bidding has ended on this item",
            "this item is no longer available"
        ]
        
        if any(phrase in html for phrase in ended_phrases):
            return item.get("id")
            
    except Exception as e:
        print(f"Error checking {url}: {e}")
        
    return None

def run_cleanup():
    load_dotenv("ebay-mcp/.env")
    
    supabase_url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
    supabase_key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")
    
    if not supabase_url or not supabase_key:
        print("Missing Supabase credentials.")
        return
        
    print("Fetching live_snipes for cleanup...")
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}",
        "Content-Type": "application/json"
    }
    
    res = requests.get(f"{supabase_url}/rest/v1/live_snipes?select=id,link", headers=headers)
    
    if res.status_code != 200:
        print(f"Error fetching from Supabase: {res.text}")
        return
        
    items = res.json()
    print(f"Found {len(items)} items to verify.")
    
    items_to_delete = []
    
    # Check URLs in parallel (max 10 to avoid eBay rate limits)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_if_sold, items)
        for item_id in results:
            if item_id:
                items_to_delete.append(item_id)
                
    if items_to_delete:
        print(f"Deleting {len(items_to_delete)} sold/ended items...")
        # Supabase bulk delete
        delete_url = f"{supabase_url}/rest/v1/live_snipes?id=in.({','.join(map(str, items_to_delete))})"
        del_res = requests.delete(delete_url, headers=headers)
        if del_res.status_code in (200, 204):
            print("Successfully cleaned up sold items!")
        else:
            print(f"Error deleting items: {del_res.text}")
    else:
        print("No sold items found. Database is clean!")

if __name__ == "__main__":
    print("=======================================")
    print("= EBAY CLEANUP BOT (SOLD ITEM HUNTER) =")
    print("=======================================")
    run_cleanup()
