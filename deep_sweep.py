import csv
import json
import time
import requests
from datetime import datetime, timezone
import sys
import os
import re
import concurrent.futures

from ebay_mcp.browse import EbayBrowseClient
from ebay_mcp.config import load_config
from dotenv import load_dotenv

load_dotenv("c:/Users/Oves/Desktop/Ebay/ebay-mcp/.env")

# -------------------------------------------------------------------------
# CONFIGURATION V3 (Ending Soonest & Global Arbitrage)
# -------------------------------------------------------------------------
GLOBAL_MIN_PRICE_USD = 50.0
GLOBAL_MAX_PRICE_USD = 700.0

MARKETPLACES = ["EBAY_US"]

CURRENCY_RATES_TO_USD = {
    "USD": 1.0,
    "GBP": 1.3,
    "EUR": 1.1,
    "AUD": 0.65,
    "CAD": 0.75
}

def to_usd(value, currency):
    return value * CURRENCY_RATES_TO_USD.get(currency, 1.0)

# Categories and their maximum price limits
SEARCH_BUCKETS = {
    # High-End Luxury Targets
    "Rolex": 700,
    "Patek Philippe": 700,
    "Audemars Piguet": 700,
    "Vacheron Constantin": 700,
    "Jaeger-LeCoultre": 700,
    "Breguet": 700,
    "Blancpain": 700,
    
    # Mid-Tier & Vintage Grails
    "Omega": 700,
    "Tudor": 700,
    "Cartier": 700,
    "IWC": 700,
    "Vintage Heuer": 700,
    "Universal Geneve": 700,
    "Zenith El Primero": 700,
    "Girard-Perregaux": 700,
    
    # Sleeping Giants
    "Vintage Longines": 700,
    "Wittnauer": 700,
    "Vintage Seiko Diver": 700,
    "Grand Seiko": 700,
    "King Seiko": 700,
    "Vintage Breitling": 700,
    "Movado M95": 700,
    "Vintage Enicar": 700,
    "Bulova Spaceview": 700,
    "Favre-Leuba": 700,
    "Record": 700,
    "Elgin": 700,
    "Mido": 700,
    
    # Fast Movers & Entry
    "Tissot PRX": 700,
    "Seiko SKX": 700,
    "Hamilton Khaki": 700,

    # The Global Nets (Massive Generic Sweeps)
    "vintage watch": 700,
    "vintage wrist watch": 700,
    "mens vintage watch": 700,
    "antique watch": 700,
    "retro mens watch": 700,
    
    # Movement Types
    "vintage automatic watch": 700,
    "vintage mechanical watch": 700,
    "vintage hand wind watch": 700,
    "old mechanical watch": 700,
    "vintage quartz watch": 700,
    "vintage battery watch": 700,
    
    # Styles & Origins
    "vintage diver": 700,
    "vintage chronograph": 700,
    "vintage military watch": 700,
    "swiss vintage watch": 700,
    "solid gold vintage watch": 700,
    "14k vintage watch": 700,
    "18k vintage watch": 700,
    
    # Condition/Flipping SEO terms
    "estate watch": 700,
    "untested vintage watch": 700,
    "vintage watch repair": 700,
    "as is vintage watch": 700,
    "vintage project watch": 700,
    
    # Lot sweeps
    "Watchmaker lot": 700,
    "Vintage watch lot": 700,
    "Estate watch lot": 700,
    "Drawer of old watches": 700,
    "Junk drawer watch": 700
}

# -------------------------------------------------------------------------
# V6 SNIPER BRAIN INJECTION
# -------------------------------------------------------------------------
EXCLUDE_KEYWORDS = [
    "fake", "replica", "homage", "style", "box only", "empty box", 
    "aftermarket", "booklet", "booklets", "catalog", "catalogs", "catalogue", "catalogues",
    "brochure", "brochures", "instructions", "clone",
    "flag", "stand", "dealer display", "magazine", "advertisement", 
    "sign", "poster", "pen", "hat", "shirt", "wallet", "umbrella", 
    "perfume", "fragrance", "cufflinks", "pillow",
    "link", "links", "bracelet", "clasp", "buckle", "band", "strap",
    "keychain", "key chain", "key holder", "scale model", "model kit",
    "photoetched", "toy", "plane", "car", "parts only", "dial only",
    "case only", "movement only", "book", "manual", "glasses", "sunglasses",
    "google", "goggle", "goggles", "watch movement", "watch dial", 
    "watch case", "watch parts", "watch part", "spare part", "spare parts",
    "movement for", "dial for", "case for", "parts for", "watch crown",
    "winding crown", "watch crystal", "bezel insert", "watch box",
    "paperweight", "display pad", "display tray", "balance staff",
    "mainspring", "folder", "pouch", "rubber belt", "leather belt",
    "watch belt", "belt for", "balance complete", "balance wheel",
    "back cover", "case back", "caseback", "minute hand", "hour hand",
    "watch hand", "watch hands", "hand for", "hands for", "second hand",
    "catalogs", "books", "swatch", "moonswatch", "cap", "baseball cap",
    "bezel only", "insert only", "pusher for", "pushers for",
    "bezel for", "insert for", "crown for", "bracelet for",
    "strap for", "band for", "link for", "links for", "crystal for",
    "oscillating weight", "rotor", "winding weight", "barrel", "weight for",
    "accessory", "accessories", "merchandise", "novelty", "watch bracelet",
    "watch strap", "watch band", "watch bezel", "watch pusher", "watch insert",
    "watch rotor", "movement parts", "movement part", "bazzel", "bazzle",
    "bracelete", "bracelets", "watchmaker tools", "watchmaker stock",
    "watchmaker parts", "watch tool", "watch tools", "watch cabinet",
    "watchmaker cabinet", "watch bench", "watchmaker bench", "lathe",
    "metal drawers", "watchmaker estate", "clock", "clocks", "wall clock",
    "alarm clock", "smartwatch", "apple watch", "fitbit", "pocket watch",
    "pocket watches", "pendant watch", "pendant watches"
]

GOLD_KEYWORDS = ["14k", "18k", "solid gold", "9k", "10k"]
RUNNING_KEYWORDS = ["running", "working", "keeps time", "runs"]
BROKEN_KEYWORDS = ["untested", "not running", "for parts", "repair", "not working"]
LADIES_KEYWORDS = ["ladies", "womens", "women"]

GENERIC_VALIDATORS = ["watch", "vintage", "mens", "womens", "ladies", "lot", "estate"]
VALID_MODELS = {
    # User's provided lists
    "rolex": ["oyster", "oyster perpetual", "oyster perpetual date", "date", "datejust", "day-date", "air-king", "explorer", "explorer ii", "submariner", "gmt-master", "daytona", "milgauss", "sea-dweller", "oysterquartz", "precision", "cellini", "bubbleback"],
    "omega": ["speedmaster", "seamaster", "seamaster 300", "seamaster de ville", "seamaster cosmic", "constellation", "constellation pie pan", "genève", "geneve", "de ville", "dynamic", "railmaster", "ranchero", "flightmaster", "chronostop", "memomatic", "cosmic", "genève dynamic"],
    "cartier": ["tank", "tank louis cartier", "tank américaine", "tank française", "must de cartier", "santos", "panthère", "baignoire", "crash", "tortue", "cintrée"],
    "jaeger-lecoultre": ["reverso", "memovox", "geophysic", "futurematic", "atmos", "master", "polaris", "duoplan", "powermatic", "dress watches", "perpetual calendars", "jlc"],
    "iwc": ["portugieser", "ingenieur", "mark series", "mark", "pilot", "aquatimer", "da vinci", "portofino", "dress watches", "yacht club", "schaffhausen"],
    "breguet": ["type xx", "type xxi", "classique", "marine", "perpetual calendar", "tourbillon", "repeater", "dress watches"],
    "longines": ["conquest", "flagship", "ultra-chron", "admiral", "record", "legend diver", "skin diver", "dolcevita", "vintage chronographs", "flyback chronographs", "flyback"],
    "universal geneve": ["polerouter", "polerouter date", "compax", "tri-compax", "uni-compax", "aero-compax", "space-compax", "white shadow", "golden shadow", "microtor", "cabriolet", "ug"],
    "girard-perregaux": ["gyromatic", "chronometer hf", "laureato", "ferrari", "vintage dress watches", "chronographs"],
    "seiko": ["grand seiko", "king seiko", "lord matic", "seiko 5", "presmatic", "lord marvel", "marvel", "crown", "sportsmatic", "bell-matic", "62mas", "6105", "6159", "6215", "6138", "6139", "5717", "5719", "bullhead", "pogue", "6306", "6309", "6139 pogue", "6138 bullhead", "turtle", "alpinist", "skx", "willard"],
    "hamilton": ["ventura", "electric", "khaki heritage", "khaki", "railroad watches", "chronographs", "dress watches", "military watches"],
    "elgin": ["dress watches", "railroad watches", "military", "pocket watches", "a-11"],
    "mido": ["commander", "ocean star", "multifort", "powerwind", "datoday"],
    "enicar": ["sherpa", "sherpa super dive", "sherpa graph", "star jewels", "ultrasonic", "guide"],
    "favre-leuba": ["raider", "bathy", "sea raider", "deep blue", "bivouac", "sea chief"],
    "record": ["datofix", "calendomatic", "dress watches", "chronographs", "dirty dozen"],
    "wittnauer": ["chronograph", "professional", "geneve", "electro-chron", "242t"],
    
    # Missing Heavy Hitters added by AI
    "tudor": ["submariner", "ranger", "snowflake", "oyster prince", "pelagos", "black bay", "chronograph", "tiger", "montecarlo"],
    "patek philippe": ["calatrava", "nautilus", "aquanaut", "gondolo", "ellipse", "complications"],
    "audemars piguet": ["royal oak", "offshore", "millenary", "jules audemars"],
    "vacheron constantin": ["patrimony", "traditionnelle", "overseas", "historiques", "fiftysix"],
    "blancpain": ["fifty fathoms", "bathyscaphe", "villeret", "leman", "air command"],
    "zenith": ["el primero", "defy", "captain", "elite", "port royal", "respirator", "stellina"],
    "heuer": ["autavia", "carrera", "monaco", "camaro", "silverstone", "bundeswehr", "calculator"],
    "tissot": ["prx", "seastar", "visodate", "chronograph", "navigator", "t-touch", "pr 516"],
    "bulova": ["spaceview", "accutron", "chronograph", "lunar pilot", "snorkel", "oceanographer"],
    "movado": ["m95", "museum", "datron", "calendoplan", "super sub sea"]
}

def is_model_locked(full_text, brand):
    validators = VALID_MODELS.get(brand, []) + [brand]
    return any(re.search(r'\b' + re.escape(v) + r'\b', full_text) for v in validators)

# -------------------------------------------------------------------------
# V6: OFF-MARKET SCANNER & SCRAP VALUE ENGINE
# -------------------------------------------------------------------------
def get_gold_scrap_value(full_text):
    if re.search(r'\b18k\b', full_text): return 720
    elif re.search(r'\b14k\b', full_text): return 552
    elif re.search(r'\b(?:10k|9k)\b', full_text): return 384
    elif "solid gold" in full_text: return 500
    return 0

def find_contact_info(text):
    phone_pattern = r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    phones = re.findall(phone_pattern, text)
    emails = re.findall(email_pattern, text)
    return phones + emails

def check_health(full_text):
    if any(k in full_text for k in RUNNING_KEYWORDS):
        return "RUNNING"
    if any(k in full_text for k in BROKEN_KEYWORDS):
        return "BROKEN/UNTESTED"
    return "UNKNOWN"

def format_buying_options(options_list):
    tags = []
    if "FIXED_PRICE" in options_list: tags.append("Buy It Now")
    if "AUCTION" in options_list: tags.append("Bidding")
    if "BEST_OFFER" in options_list: tags.append("Accepts Offers")
    return ", ".join(tags)

def extract_gender(full_text):
    if re.search(r'\b(womens|women\'s|women|ladies|lady|ladys)\b', full_text):
        return "Womens"
    elif re.search(r'\b(mens|men\'s|men)\b', full_text):
        return "Mens"
    return "Unisex"

def parse_time_listed(creation_date_str):
    if not creation_date_str:
        return "Unknown"
    try:
        creation_date_str = creation_date_str.replace('Z', '+00:00')
        creation_time = datetime.fromisoformat(creation_date_str)
        now = datetime.now(timezone.utc)
        time_since = now - creation_time
        
        days = time_since.days
        if days == 0:
            hours = time_since.seconds // 3600
            if hours == 0:
                mins = time_since.seconds // 60
                return f"{mins}m ago"
            return f"{hours}h ago"
        elif days < 7:
            return f"{days}d ago"
        else:
            return creation_time.strftime("%b %d, %Y")
    except Exception:
        return "Parse Error"

def calculate_time_left(end_date_str):
    if not end_date_str:
        return "Unknown"
    try:
        end_date_str = end_date_str.replace('Z', '+00:00')
        end_time = datetime.fromisoformat(end_date_str)
        now = datetime.now(timezone.utc)
        time_left = end_time - now
        
        hours, remainder = divmod(int(time_left.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        
        if hours < 0:
            return "Ended"
        elif hours > 48:
            return f"{hours // 24} days"
        else:
            return f"{hours}h {minutes}m"
    except Exception:
        return "Parse Error"

def fetch_market_data(client, query, price_limit, market):
    try:
        cat_id = None if "lot" in query.lower() else "31387"
        valid_items = []
        
        # Deep Sweep: Pull 1,000 items per bucket instead of 100
        for offset in range(0, 1000, 100):
            try:
                # V3 UPGRADE: sort="endingSoonest", pagination via offset
                data = client.search(query, limit=100, offset=offset, sort="endingSoonest", filter="itemLocationCountry:US", category_ids=cat_id, marketplace=market)
                items = data.get("itemSummaries", [])
                
                if not items:
                    break # No more results for this query
                    
                for item in items:
                    price_dict = item.get("price", {})
                    try:
                        raw_price = float(price_dict.get("value", 999999))
                        currency = price_dict.get("currency", "USD")
                    except:
                        continue
                        
                    price_usd = to_usd(raw_price, currency)
                        
                    if price_usd < GLOBAL_MIN_PRICE_USD or price_usd > GLOBAL_MAX_PRICE_USD or price_usd > price_limit:
                        continue
                        
                    title = item.get("title", "Unknown Title")
                    short_desc = item.get("shortDescription", "")
                    title_lower = title.lower()
                    
                    full_text = f"{title_lower} {short_desc.lower()}"
                    
                    # 1. The Accessory Nuke
                    if any(re.search(r'\b' + re.escape(junk) + r'\b', full_text) for junk in EXCLUDE_KEYWORDS):
                        continue
                        
                    # 1.5 The Lonely Accessory Rule (ABSOLUTE)
                    lonely_parts = ["box", "movement", "movements", "dial", "dials", "case", "cases", "bracelet", "bracelets", "strap", "straps", "band", "bands", "parts", "part", "staff", "staffs", "belt", "belts", "cover", "covers", "hand", "hands", "balance", "caliber", "cal", "pusher", "pushers", "insert", "inserts", "bezel", "bezels", "crown", "crowns", "rotor", "weight", "barrel", "wheels", "gears", "pinions", "springs", "stems", "crystals", "clasps", "buckles", "links", "drawer", "drawers"]
                    if any(re.search(r'\b' + p + r'\b', title_lower) for p in lonely_parts):
                        if not re.search(r'\bwatch(?:es)?\b', title_lower):
                            continue
                        
                    # 2. Modern Ladies Filter
                    if any(re.search(r'\b' + re.escape(l) + r'\b', full_text) for l in LADIES_KEYWORDS):
                        if not re.search(r'\bvintage\b', full_text) and not any(re.search(r'\b' + brand + r'\b', full_text) for brand in ["rolex", "omega", "cartier", "tudor"]):
                            continue
                            
                    # 3. Model Lock
                    query_brand = query.split()[0].lower()
                    if query_brand in VALID_MODELS:
                        if not is_model_locked(full_text, query_brand):
                            continue
                            
                    # Extract V6 Data
                    buying_options = format_buying_options(item.get("buyingOptions", []))
                    health = check_health(full_text)
                    scrap = get_gold_scrap_value(full_text)
                    contacts = ", ".join(find_contact_info(full_text))
                    
                    time_left = calculate_time_left(item.get("itemEndDate"))
                    time_listed = parse_time_listed(item.get("itemCreationDate"))
                    gender = extract_gender(full_text)
                    
                    raw_url = item.get("itemWebUrl", "")
                    excel_hyperlink = f'=HYPERLINK("{raw_url}", "Open eBay")' if raw_url else ""
                    
                    image_url = item.get("image", {}).get("imageUrl", "")
                    
                    valid_items.append({
                        "Query": query,
                        "Region": market,
                        "Title": title,
                        "Price": int(price_usd),
                        "TimeLeft": time_left,
                        "TimeListed": time_listed,
                        "Gender": gender,
                        "BuyingOptions": buying_options,
                        "Condition": item.get("condition", "Unknown"),
                        "Health": health,
                        "ScrapValue": f"${scrap}" if scrap else "N/A",
                        "Contacts": contacts if contacts else "None",
                        "Seller": item.get("seller", {}).get("username", "Unknown"),
                        "Link": raw_url,
                        "ExcelLink": excel_hyperlink,
                        "ImageUrl": image_url
                    })
            except Exception:
                break
                
        return valid_items
    except Exception as e:
        print(f"API Error on {query} ({market}): {e}")
        return []

# -------------------------------------------------------------------------
# MAIN DEEP SWEEP (V4 HYPER-DRIVE ENGINE)
# -------------------------------------------------------------------------
def run_deep_sweep():
    print("=====================================================")
    print("= EBAY DEEP SWEEP V4 (HYPER-DRIVE MULTI-THREADING)  =")
    print("=====================================================")
    
    client = EbayBrowseClient(load_config())
    
    # Pre-fetch OAuth token so multiple threads don't hit the auth server simultaneously
    client._get_token()
    
    tasks = []
    for query, price_limit in SEARCH_BUCKETS.items():
        for market in MARKETPLACES:
            tasks.append((query, price_limit, market))
            
    print(f">>> Firing {len(tasks)} parallel global API requests...")
    
    all_valid_items = []
    
    start_time = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_market_data, client, q, limit, m): (q, m) for q, limit, m in tasks}
        
        for future in concurrent.futures.as_completed(futures):
            q, m = futures[future]
            try:
                results = future.result()
                if results:
                    all_valid_items.extend(results)
                    print(f"  -> Found {len(results)} deals for {q.upper()} in {m}")
            except Exception as e:
                pass
                
    elapsed = time.time() - start_time
    
    csv_file = "C:\\Users\\Oves\\Desktop\\Ebay\\deep_sweep_results.csv"
    json_file = "C:\\Users\\Oves\\Desktop\\Ebay\\deep_sweep_results.json"
    print(f"\nWriting {len(all_valid_items)} total deals to {csv_file} and {json_file}")
    
    # Write JSON
    with open(json_file, mode="w", encoding="utf-8") as f:
        json.dump(all_valid_items, f, indent=4)
    
    # Write CSV
    with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Query", "Region", "Title", "Price (USD)", "Time Left", "Buying Options", "Condition", "Health", "Scrap Value", "Off-Market Contacts", "Seller", "Link", "Image"])
        for item in all_valid_items:
            writer.writerow([
                item["Query"], item["Region"], item["Title"], item["Price"], item["TimeLeft"],
                item["BuyingOptions"], item["Condition"], item["Health"], item["ScrapValue"],
                item["Contacts"], item["Seller"], item["ExcelLink"], item["ImageUrl"]
            ])
                
    print("=====================================================")
    print(f"Deep Sweep Complete! Swept the globe in {elapsed:.1f} seconds.")
    
    # PUSH TO SUPABASE
    supabase_url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
    supabase_key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")
    if supabase_url and supabase_key:
        print("\n>>> Pushing deals to Supabase Cloud Database...")
        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json"
        }
        
        # 1. Clear existing deals in the table
        res_del = requests.delete(f"{supabase_url}/rest/v1/deep_sweep_deals?id=gt.0", headers=headers)
        if res_del.status_code not in (200, 204):
            print("Failed to clear old Supabase data:", res_del.text)
            
        # 2. Format payload to match snake_case SQL schema
        payload = []
        for item in all_valid_items:
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
            
        # 3. Insert in batches of 1000
        batch_size = 1000
        for i in range(0, len(payload), batch_size):
            batch = payload[i:i+batch_size]
            res = requests.post(f"{supabase_url}/rest/v1/deep_sweep_deals", headers=headers, json=batch)
            if res.status_code not in (200, 201):
                print(f"Error inserting batch into Supabase: {res.text}")
        
        print(">>> Successfully pushed to Cloud!")
        
    print(f"\nLocal backups saved to: {csv_file}")

if __name__ == "__main__":
    run_deep_sweep()
