import json
import time
import winsound
import webbrowser
from datetime import datetime
import sys
import subprocess
import threading
import queue
import re

from ebay_mcp.browse import EbayBrowseClient
from ebay_mcp.config import load_config

# -------------------------------------------------------------------------
# CONFIGURATION V4 - GLOBAL ARBITRAGE & ESTATE HUNTER
# -------------------------------------------------------------------------
POLL_DELAY_SECONDS = 17 
MAX_AUTO_OPENS_PER_MIN = 2

GLOBAL_MIN_PRICE_USD = 50.0
GLOBAL_MAX_PRICE_USD = 700.0

# Brand-Specific Ceilings (Overrides the $700 Global Max)
BRAND_LIMITS_USD = {
    "rolex": 3500,
    "patek": 5000,
    "audemars": 5000,
    "vacheron": 4000,
    "iwc": 1500,
    "jaeger-lecoultre": 2000,
    "jlc": 2000,
    "breguet": 2000,
    "omega": 1200,
    "tudor": 1200,
    "cartier": 1200,
    "heuer": 1000,
    "zenith": 1500,
    "breitling": 1000,
    "girard-perregaux": 800,
    "longines": 400,
    "wittnauer": 300,
    "movado": 800,
    "blancpain": 1000,
    "enicar": 300,
    "bulova": 250,
    "tissot": 200,
    "seiko": 200,
    "hamilton": 200,
    "valjoux": 400,
    "lemania": 300,
    "universal geneve": 800,
}

# -------------------------------------------------------------------------
# MULTI-REGION ARBITRAGE (Targeted Scans)
# -------------------------------------------------------------------------
# We prioritize US for major brands, but scan globally for hidden/generic lots
TARGETS = [
    # US Primary Targets
    ("Rolex", "EBAY_US"), ("Omega", "EBAY_US"), ("Tudor", "EBAY_US"), ("Seiko", "EBAY_US"),
    ("Cartier", "EBAY_US"), ("Patek Philippe", "EBAY_US"), ("Audemars Piguet", "EBAY_US"),
    ("IWC", "EBAY_US"), ("Jaeger-LeCoultre", "EBAY_US"), ("Breguet", "EBAY_US"),
    ("Blancpain", "EBAY_US"), ("Zenith", "EBAY_US"), ("Girard-Perregaux", "EBAY_US"),
    ("Universal Geneve", "EBAY_US"), ("Longines", "EBAY_US"), ("Hamilton", "EBAY_US"),
    ("Elgin", "EBAY_US"), ("Mido", "EBAY_US"), ("Favre-Leuba", "EBAY_US"), ("Record", "EBAY_US"),
    ("Enicar", "EBAY_US"), ("Wittnauer", "EBAY_US"), ("Bulova", "EBAY_US"), ("Tissot", "EBAY_US"),
    # Misspellings (Hidden gems)
    ("Omiga", "EBAY_US"), ("Rollex", "EBAY_US"), ("Breightling", "EBAY_US"),
    
    # Generic SEO & Hidden Gems
    ("Vintage watch", "EBAY_US"),
    ("Vintage wrist watch", "EBAY_US"),
    ("Mens vintage watch", "EBAY_US"),
    ("Antique watch", "EBAY_US"),
    ("Retro mens watch", "EBAY_US"),
    
    # Movement Types
    ("Vintage automatic watch", "EBAY_US"),
    ("Vintage mechanical watch", "EBAY_US"),
    ("Vintage hand wind watch", "EBAY_US"),
    ("Old mechanical watch", "EBAY_US"),
    ("Vintage quartz watch", "EBAY_US"),
    ("Vintage battery watch", "EBAY_US"),
    
    # Styles & Origins
    ("Vintage diver", "EBAY_US"),
    ("Vintage chronograph", "EBAY_US"),
    ("Vintage military watch", "EBAY_US"),
    ("Swiss vintage watch", "EBAY_US"),
    ("Solid gold vintage watch", "EBAY_US"),
    ("14k vintage watch", "EBAY_US"),
    ("18k vintage watch", "EBAY_US"),
    
    # Condition/Flipping SEO terms
    ("Estate watch", "EBAY_US"),
    ("Untested vintage watch", "EBAY_US"),
    ("Vintage watch repair", "EBAY_US"),
    ("As is vintage watch", "EBAY_US"),
    ("Vintage project watch", "EBAY_US"),
    
    # Lot sweeps
    ("Watchmaker lot", "EBAY_US"),
    ("Vintage watch lot", "EBAY_US"),
    ("Estate watch lot", "EBAY_US"),
    ("Drawer of old watches", "EBAY_US"),
    ("Junk drawer watch", "EBAY_US")
]

# Crude Currency Conversion to USD for filtering UK/German listings
CURRENCY_RATES_TO_USD = {
    "USD": 1.0,
    "GBP": 1.3,
    "EUR": 1.1,
    "AUD": 0.65,
    "CAD": 0.75
}

def to_usd(value, currency):
    return value * CURRENCY_RATES_TO_USD.get(currency, 1.0)

# -------------------------------------------------------------------------
# THE ACCESSORY NUKE
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

# -------------------------------------------------------------------------
# THE MODEL-LOCK SYSTEM
# -------------------------------------------------------------------------
GENERIC_VALIDATORS = ["watch", "vintage", "mens", "womens", "ladies", "lot", "estate"]

VALID_MODELS = {
    "rolex": ["oyster", "datejust", "day-date", "air-king", "explorer", "submariner", "gmt-master", "daytona", "milgauss", "sea-dweller", "oysterquartz", "precision", "cellini", "bubbleback"],
    "omega": ["speedmaster", "seamaster", "constellation", "genève", "geneve", "de ville", "dynamic", "railmaster", "ranchero", "flightmaster", "chronostop", "memomatic", "cosmic"],
    "cartier": ["tank", "américaine", "française", "must de cartier", "santos", "panthère", "baignoire", "crash", "tortue", "cintrée"],
    "jaeger-lecoultre": ["reverso", "memovox", "geophysic", "futurematic", "atmos", "master", "polaris", "duoplan", "powermatic", "perpetual"],
    "jlc": ["reverso", "memovox", "geophysic", "futurematic", "atmos", "master", "polaris", "duoplan", "powermatic", "perpetual"],
    "iwc": ["portugieser", "ingenieur", "mark", "pilot", "aquatimer", "da vinci", "portofino", "yacht club"],
    "breguet": ["type xx", "type xxi", "classique", "marine", "tourbillon", "repeater"],
    "longines": ["conquest", "flagship", "ultra-chron", "admiral", "record", "legend diver", "skin diver", "dolcevita", "flyback"],
    "universal geneve": ["polerouter", "compax", "tri-compax", "uni-compax", "aero-compax", "space-compax", "white shadow", "golden shadow", "microtor", "cabriolet"],
    "girard-perregaux": ["gyromatic", "chronometer hf", "laureato", "ferrari"],
    "seiko": ["grand seiko", "king seiko", "lord matic", "seiko 5", "presmatic", "lord marvel", "marvel", "crown", "sportsmatic", "bell-matic", "62mas", "6105", "6159", "6215", "6138", "6139", "5717", "5719", "bullhead", "pogue", "6306", "6309", "kakume", "ufo", "willard", "turtle", "alpinist"],
    "hamilton": ["ventura", "electric", "khaki", "railroad"],
    "elgin": ["railroad", "pocket"],
    "mido": ["commander", "ocean star", "multifort", "powerwind", "datoday"],
    "enicar": ["sherpa", "super dive", "graph", "star jewels", "ultrasonic"],
    "favre-leuba": ["raider", "bathy", "sea raider", "deep blue"],
    "record": ["datofix", "calendomatic"],
    "wittnauer": ["professional", "geneve", "electro-chron"],
    "tudor": ["submariner", "ranger", "snowflake", "oyster prince", "pelagos", "black bay", "chronograph"],
    "breitling": ["navitimer", "chronomat", "top time", "premier", "superocean"],
    "zenith": ["el primero", "defy", "captain", "elite"]
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

# -------------------------------------------------------------------------
# STATE & HELPERS
# -------------------------------------------------------------------------
seen_items = set()
auto_open_timestamps = []
tts_queue = queue.Queue()

def tts_worker():
    while True:
        text = tts_queue.get()
        if text is None:
            break
        cmd = f'powershell -Command "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak(\'{text}\')"'
        subprocess.run(cmd, shell=True)
        tts_queue.task_done()

threading.Thread(target=tts_worker, daemon=True).start()

def play_tts_alarm(title, price_usd, is_gold=False, market="US"):
    clean_title = "".join(c for c in title if c.isalnum() or c.isspace())
    prefix = ""
    if market == "EBAY_GB":
        prefix = "U K Arbitrage Alert. "
    elif market == "EBAY_DE":
        prefix = "Germany Arbitrage Alert. "
        
    if is_gold:
        text = f"{prefix}GOLD JACKPOT ALERT. {clean_title} for {int(price_usd)} U S dollars."
    else:
        text = f"{prefix}Snipe alert. {clean_title} for {int(price_usd)} U S dollars."
    tts_queue.put(text)

def should_auto_open():
    global auto_open_timestamps
    now = time.time()
    auto_open_timestamps = [t for t in auto_open_timestamps if now - t < 60]
    
    if len(auto_open_timestamps) < MAX_AUTO_OPENS_PER_MIN:
        auto_open_timestamps.append(now)
        return True
    return False

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
        return "Unknown"

def check_health(full_text):
    if any(k in full_text for k in RUNNING_KEYWORDS):
        return "\033[92m[🟢 RUNNING]\033[0m"
    if any(k in full_text for k in BROKEN_KEYWORDS):
        return "\033[91m[🟠 BROKEN/UNTESTED]\033[0m"
    return "[⚪ UNKNOWN STATUS]"

def check_seller_safety(seller):
    score = seller.get("feedbackScore", 0)
    try:
        score = int(score)
    except:
        score = 0
    if score == 0:
        return "\033[91m [WARNING: 0 FEEDBACK] \033[0m"
    elif score < 10:
        return f"\033[93m [LOW FEEDBACK: {score}] \033[0m"
    return f" (Feedback: {score})"

# -------------------------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------------------------
def run_sniper():
    print("=====================================================")
    print("= EBAY 24/7 WATCH SNIPER (V5 DESCRIPTION DEEP-SCAN) =")
    print("=====================================================")
    print(f"Monitoring Global Price Range: ${GLOBAL_MIN_PRICE_USD} - ${GLOBAL_MAX_PRICE_USD} USD")
    print(f"Targeting: {len(TARGETS)} Multi-Region Search Buckets (US, UK, DE)")
    print("Waiting for new listings... (Press Ctrl+C to stop)\n")
    
    client = EbayBrowseClient(load_config())
    
    print("Pre-seeding historical data...")
    for query, market in TARGETS:
        try:
            cat_id = None if "lot" in query.lower() else "31387"
            data = client.search(query, limit=10, sort="newlyListed", filter="itemLocationCountry:US", category_ids=cat_id, marketplace=market)
            for item in data.get("itemSummaries", []):
                seen_items.add(item.get("itemId"))
            time.sleep(1)
        except Exception as e:
            pass
    
    print(f"Seeded {len(seen_items)} historical items. Live monitoring started!\n")
    
    while True:
        for query, market in TARGETS:
            try:
                cat_id = None if "lot" in query.lower() else "31387"
                data = client.search(query, limit=10, sort="newlyListed", filter="itemLocationCountry:US", category_ids=cat_id, marketplace=market)
                
                for item in data.get("itemSummaries", []):
                    item_id = item.get("itemId")
                    if not item_id or item_id in seen_items:
                        continue
                    
                    seen_items.add(item_id)
                    
                    title = item.get("title", "Unknown Title")
                    short_desc = item.get("shortDescription", "")
                    title_lower = title.lower()
                    
                    # Combine title and description for Deep-Scan logic
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
                    if not is_model_locked(full_text, query_brand):
                        continue
                    
                    # 4. Currency Conversion & Global Price Limit
                    price_dict = item.get("price", {})
                    try:
                        raw_price = float(price_dict.get("value", 999999))
                        currency = price_dict.get("currency", "USD")
                    except:
                        continue
                        
                    price_usd = to_usd(raw_price, currency)
                    
                    if price_usd < GLOBAL_MIN_PRICE_USD:
                        continue
                        
                    # 4. Apply Brand-Specific Ceiling and Model Lock
                    applicable_max_usd = GLOBAL_MAX_PRICE_USD
                    triggered_brand = None
                    
                    for brand, limit in BRAND_LIMITS_USD.items():
                        if brand in full_text:
                            triggered_brand = brand
                            break
                            
                    if price_usd > applicable_max_usd:
                        continue
                        
                    # 5. THE STRICT VALIDATION (Model Lock & Generic Lock)
                    if triggered_brand:
                        if not is_model_locked(full_text, triggered_brand):
                            continue # Throw away accessories that passed the nuke
                    else:
                        valid_unbranded = ["watch", "movement", "dial", "lot", "estate", "collection"]
                        if not any(word in full_text for word in valid_unbranded):
                            continue
                        
                    seller = item.get("seller", {})
                    url = item.get("itemWebUrl", "")
                    buying_options = item.get("buyingOptions", [])
                    
                    options_str = format_buying_options(buying_options)
                    safety_str = check_seller_safety(seller)
                    health_str = check_health(full_text)
                    
                    # Gold Jackpot Check
                    is_gold_jackpot = any(gold in full_text for gold in GOLD_KEYWORDS)
                    
                    # V6 Engines
                    scrap_value = get_gold_scrap_value(full_text)
                    contacts = find_contact_info(full_text)
                    image_url = item.get("image", {}).get("imageUrl", "")
                    
                    time_listed = parse_time_listed(item.get("itemCreationDate"))
                    gender = extract_gender(full_text)
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    market_str = "\033[96m[GLOBAL ARBITRAGE]\033[0m" if market != "EBAY_US" else ""
                    
                    if is_gold_jackpot:
                        print(f"\n\033[45m\033[97m[{timestamp}] 🚨 SOLID GOLD JACKPOT ALERT 🚨 {market_str}\033[0m")
                    else:
                        print(f"\n\033[92m[{timestamp}] SNIPE ALERT: {query.upper()} {market_str}\033[0m")
                        
                    print(f"Title: {title} {health_str}")
                    print(f"Price: {raw_price} {currency} (~${int(price_usd)} USD) {options_str}")
                    
                    if scrap_value > 0:
                        print(f"\033[93m=> EST. SCRAP VALUE: ${scrap_value} USD (GUARANTEED FLOOR)\033[0m")
                        
                    if contacts:
                        print(f"\033[91m=> [OFF-MARKET DEAL] Contact info found: {', '.join(contacts)}\033[0m")
                        
                    print(f"Seller: {seller.get('username', 'Unknown')} | Region: {market}{safety_str}")
                    print(f"Link: {url}")
                    
                    # Write to Overnight Log File
                    try:
                        with open("C:\\Users\\Oves\\Desktop\\snipe_history.txt", "a", encoding="utf-8") as f:
                            f.write(f"[{timestamp}] {market} | {title} | ~${int(price_usd)} USD | {url}\n")
                    except Exception:
                        pass
                        
                    # Write to Live JSON Feed for Dashboard (Legacy Backup)
                    try:
                        json_file = "C:\\Users\\Oves\\Desktop\\Ebay\\live_snipes.json"
                        snipes = []
                        if os.path.exists(json_file):
                            try:
                                with open(json_file, "r", encoding="utf-8") as f:
                                    snipes = json.load(f)
                            except:
                                pass
                        
                        snipe_data = {
                            "Query": query,
                            "Region": market,
                            "Title": title,
                            "Price": int(price_usd),
                            "TimeLeft": "New Listing",
                            "TimeListed": time_listed,
                            "Gender": gender,
                            "BuyingOptions": options_str,
                            "Condition": item.get("condition", "Unknown"),
                            "Health": health_str,
                            "ScrapValue": f"${scrap_value}" if scrap_value else "N/A",
                            "Contacts": ", ".join(contacts) if contacts else "None",
                            "Seller": seller.get('username', 'Unknown'),
                            "Link": url,
                            "ImageUrl": image_url,
                            "Timestamp": timestamp
                        }
                        snipes.insert(0, snipe_data)
                        snipes = snipes[:50]
                        with open(json_file, "w", encoding="utf-8") as f:
                            json.dump(snipes, f, indent=4)
                            
                        # PUSH TO SUPABASE CLOUD (UPSERT)
                        supabase_url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
                        supabase_key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")
                        if supabase_url and supabase_key:
                            headers = {
                                "apikey": supabase_key,
                                "Authorization": f"Bearer {supabase_key}",
                                "Content-Type": "application/json",
                                "Prefer": "resolution=merge-duplicates"
                            }
                            
                            payload = {
                                "query": query,
                                "region": market,
                                "title": title,
                                "price": int(price_usd),
                                "time_left": "New Listing",
                                "time_listed": time_listed,
                                "gender": gender,
                                "buying_options": options_str,
                                "condition": item.get("condition", "Unknown"),
                                "health": health_str,
                                "scrap_value": f"${scrap_value}" if scrap_value else "N/A",
                                "contacts": ", ".join(contacts) if contacts else "None",
                                "seller": seller.get("username", "Unknown"),
                                "link": url,
                                "excel_link": f'=HYPERLINK("{url}", "Open eBay")',
                                "image_url": image_url
                            }
                            
                            res = requests.post(f"{supabase_url}/rest/v1/live_snipes", headers=headers, json=payload)
                            if res.status_code not in (200, 201):
                                print(f"\033[91mCloud Sync Error: {res.text}\033[0m")
                                
                    except Exception as e:
                        print(f"Export Error: {e}")
                    
                    # Alarm & Auto-open
                    play_tts_alarm(title, price_usd, is_gold=is_gold_jackpot, market=market)
                        
                    if should_auto_open():
                        print("-> Auto-opening checkout tab!")
                        webbrowser.open(url)
                    else:
                        print("-> Auto-open rate limited. Click link manually!")
                        
            except Exception as e:
                print(f"API Error on {query} ({market}): {e}")
                
            time.sleep(POLL_DELAY_SECONDS)

if __name__ == "__main__":
    try:
        run_sniper()
    except KeyboardInterrupt:
        print("\nSniper Bot Terminated.")
        sys.exit(0)
