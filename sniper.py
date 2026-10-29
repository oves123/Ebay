import json
import time
import os
import sys
import requests
from datetime import datetime, timezone
import threading
import queue
import re

from ebay_mcp.browse import EbayBrowseClient
from ebay_mcp.config import load_config
from dotenv import load_dotenv
import uvicorn
from fastapi import FastAPI

# Ensure UTF-8 output encoding on Windows consoles
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        # sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Fallback for local vs cloud
if os.path.exists("c:/Users/Oves/Desktop/Ebay/ebay-mcp/.env"):
    load_dotenv("c:/Users/Oves/Desktop/Ebay/ebay-mcp/.env")
else:
    load_dotenv()

# --- Cloud Web Server (For Render) ---
app = FastAPI()

@app.get("/")
def health_check():
    return {"status": "Sniper Bot is alive and hunting!"}

def run_server():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)

# -------------------------------------------------------------------------
# FIREBASE PUSH NOTIFICATION ENGINE
# -------------------------------------------------------------------------
firebase_initialized = False
cached_tokens = []
last_token_fetch = 0

def get_fcm_tokens():
    global cached_tokens, last_token_fetch
    now = time.time()
    if cached_tokens and (now - last_token_fetch < 60):
        return cached_tokens
    
    supabase_url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
    supabase_key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")
    if supabase_url and supabase_key:
        try:
            h = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
            r = requests.get(f"{supabase_url}/rest/v1/fcm_tokens?select=token", headers=h, timeout=5)
            if r.status_code == 200:
                raw_tokens = [row["token"] for row in r.json() if row.get("token") and not str(row["token"]).startswith("__")]
                cached_tokens = list(dict.fromkeys(raw_tokens))
                last_token_fetch = now
                print(f"🔥 Successfully loaded {len(cached_tokens)} unique push tokens from Supabase")
        except Exception as se:
            print(f"Token fetch notice: {se}")
    return cached_tokens

def init_firebase():
    global firebase_initialized
    try:
        import firebase_admin
        from firebase_admin import credentials
        if firebase_admin._apps:
            firebase_initialized = True
            return True, "App already initialized"
    except ImportError as e:
        print(f"⚠️ firebase-admin library not installed: {e}")
        return False, f"Missing firebase_admin library: {e}"

    try:
        # 1. Search for local service account json
        local_files = [
            "ebay-sniper-alerts-firebase-adminsdk-fbsvc-7132eb45cb.json",
            os.path.join(os.path.dirname(__file__), "ebay-sniper-alerts-firebase-adminsdk-fbsvc-7132eb45cb.json"),
            "C:\\Users\\Oves\\Desktop\\Ebay\\ebay-sniper-alerts-firebase-adminsdk-fbsvc-7132eb45cb.json",
            "C:\\Users\\Oves\\Desktop\\ebay-sniper-alerts-firebase-adminsdk-fbsvc-7132eb45cb.json"
        ]
        cred_path = next((f for f in local_files if os.path.exists(f)), None)
        cred_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
        
        if cred_path:
            cred = credentials.Certificate(cred_path)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            firebase_initialized = True
            print(f"🔥 Firebase Push Notifications Initialized with {os.path.basename(cred_path)}")
            return True, f"Loaded from file {os.path.basename(cred_path)}"
        elif cred_env:
            import json as _json
            clean_env = cred_env.strip()
            if (clean_env.startswith("'") and clean_env.endswith("'")) or (clean_env.startswith('"') and clean_env.endswith('"')):
                clean_env = clean_env[1:-1]
            cred_dict = _json.loads(clean_env)
            if "private_key" in cred_dict and "\\n" in cred_dict["private_key"]:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
            cred = credentials.Certificate(cred_dict)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            firebase_initialized = True
            print("🔥 Firebase Push Notifications Initialized via Environment Variable")
            return True, "Loaded from ENV"
        else:
            # 3. Automatic Cloud Fallback: Load credentials securely from Supabase Vault
            supabase_url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
            supabase_key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")
            if supabase_url and supabase_key:
                try:
                    import json as _json
                    h = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
                    r = requests.get(f"{supabase_url}/rest/v1/fcm_tokens?token=eq.__firebase_service_account__&select=device_info", headers=h, timeout=6)
                    if r.status_code == 200:
                        rows = r.json()
                        if rows and rows[0].get("device_info"):
                            raw_cred = rows[0]["device_info"]
                            cred_dict = _json.loads(raw_cred)
                            if "private_key" in cred_dict and "\\n" in cred_dict["private_key"]:
                                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")
                            cred = credentials.Certificate(cred_dict)
                            if not firebase_admin._apps:
                                firebase_admin.initialize_app(cred)
                            firebase_initialized = True
                            print("🔥 Firebase Push Notifications Initialized via Supabase Cloud Vault!")
                            return True, "Loaded from Supabase Vault"
                except Exception as ve:
                    print(f"Supabase vault load error: {ve}")

            print("⚠️ Firebase Service Account JSON not found in environment or database!")
            return False, "FIREBASE_SERVICE_ACCOUNT_JSON not found in ENV or Supabase"
    except Exception as e:
        print(f"⚠️ Firebase initialization skipped: {e}")
        return False, f"Init error: {e}"

def send_mobile_push(title, price_usd, url, image_url=None, time_listed="Just now", condition="Pre-owned", health_str="", options_str="", scrap_value=0):
    # Safety guard: Suppress push notifications for old/historical listings
    if time_listed and ("h ago" in time_listed or "d ago" in time_listed) and "[📉 PRICE DROP]" not in title:
        print(f"[SUPPRESSED] Push Notification suppressed for old listing ({time_listed}): {title[:50]}")
        return f"Suppressed: Old listing ({time_listed})"

    ok, init_msg = init_firebase()
    if not ok:
        print(f"⚠️ Push notification skipped: {init_msg}")
        return f"Skipped: {init_msg}"
    try:
        from firebase_admin import messaging
        
        # Extract clean eBay item ID for OS-level deduplication tag & native app deep link
        item_id_match = re.search(r'/itm/(?:[^/]+/)?(\d{9,14})', url) or re.search(r'(\d{9,14})', url)
        ebay_item_id = item_id_match.group(1) if item_id_match else str(abs(hash(url)))
        notification_tag = f"ebay-deal-{ebay_item_id}"

        # Build direct App Launcher URL for iOS & Android
        import urllib.parse
        launcher_url = f"https://ebay-1e4.pages.dev/open.html?id={ebay_item_id}&url={urllib.parse.quote(url, safe='')}"

        # 1. Clean Title and Brand/Model
        clean_title = re.sub(r'\[.*?\]', '', title).strip()
        
        # Highlight distinct features like dial color or ref to distinguish similar watches
        dial_match = re.search(r'\b(blue|black|white|silver|gold|green|red|salmon|grey|gray|yellow|orange|champagne)\s+dial\b', clean_title, re.IGNORECASE)
        dial_suffix = f" ({dial_match.group(0).title()})" if dial_match else ""
        
        concise = re.sub(r'\b(men\'s|mens|women\'s|womens|stainless|steel|watch|wrist|automatic|quartz)\b', '', clean_title, flags=re.IGNORECASE)
        concise = re.sub(r'\s+', ' ', concise).strip()
        display_title = (concise[:42] + '..') if len(concise) > 42 else concise
        notification_title = f"⚡ ${int(price_usd)} | {display_title}{dial_suffix}"

        # 2. Build Rich Notification Body with Watch Specs
        details_list = []
        if time_listed:
            details_list.append(f"⏱️ {time_listed}")
        if health_str and "RUNNING" in health_str.upper():
            details_list.append("🟢 Running")
        elif health_str and ("BROKEN" in health_str.upper() or "REPAIR" in health_str.upper()):
            details_list.append("🔴 Repair/Parts")
        if condition and condition != "Unknown":
            details_list.append(f"🏷️ {condition}")
        if options_str:
            clean_opts = options_str.replace("Buy It Now", "BIN").replace("Accepts Offers", "Offers")
            details_list.append(f"📦 {clean_opts}")
        if scrap_value and scrap_value > 0:
            details_list.append(f"💰 Scrap: ${scrap_value}")

        body_details = " | ".join(details_list[:3])
        notification_body = f"{body_details}\n👉 Tap to open eBay and buy now!"

        tokens = get_fcm_tokens()

        # Web Push Configuration for Mobile Safari, Chrome & Android (opens native eBay App)
        webpush_config = messaging.WebpushConfig(
            fcm_options=messaging.WebpushFCMOptions(
                link=launcher_url
            ),
            notification=messaging.WebpushNotification(
                title=notification_title,
                body=notification_body,
                icon=image_url if image_url else "https://ir.ebaystatic.com/cr/v/c1/ebay-logo-1-1.png",
                image=image_url if image_url else None,
                tag=notification_tag,
                renotify=False
            ),
            data={
                "url": url,
                "link": launcher_url,
                "launcher_url": launcher_url,
                "price": str(price_usd),
                "title": clean_title,
                "item_id": ebay_item_id
            }
        )

        data_payload = {
            "url": url,
            "link": launcher_url,
            "launcher_url": launcher_url,
            "price": str(price_usd),
            "title": clean_title[:80],
            "item_id": ebay_item_id
        }

        if tokens:
            multicast = messaging.MulticastMessage(
                tokens=tokens,
                notification=messaging.Notification(
                    title=notification_title,
                    body=notification_body,
                    image=image_url if image_url else None
                ),
                webpush=webpush_config,
                data=data_payload
            )
            response = messaging.send_each_for_multicast(multicast)
            status_text = f"Sent to {response.success_count}/{len(tokens)} devices"
            print(f"📱 Sent Detailed Mobile Push Alert to {response.success_count}/{len(tokens)} registered devices!")
            return status_text
        else:
            msg = messaging.Message(
                topic="deals",
                notification=messaging.Notification(
                    title=notification_title,
                    body=notification_body,
                    image=image_url if image_url else None
                ),
                webpush=webpush_config,
                data=data_payload
            )
            messaging.send(msg)
            print("📱 Broadcasted Push Notification to 'deals' topic.")
            return "Sent to topic: deals"
    except Exception as e:
        print(f"⚠️ Push notification send error: {e}")
        return f"Send error: {e}"

# -------------------------------------------------------------------------
# CONFIGURATION V5 - BOOLEAN GROUPED QUERIES (7x FASTER SCANNING)
# -------------------------------------------------------------------------
MAX_AUTO_OPENS_PER_MIN = 2

GLOBAL_MIN_PRICE_USD = 50.0
GLOBAL_MAX_PRICE_USD = 700.0

# Strict age gate: Only notify & record listings posted in the last 30 minutes (real-time live snipes)
MAX_SNIPE_AGE_MINUTES = 30

# NOTE: BRAND_LIMITS_USD is kept for reference but the global $50-$700 cap is now strictly enforced.
# No brand-specific overrides — ALL listings must be between $50 and $700 USD.


# -------------------------------------------------------------------------
# PRIORITY FAST-LANE SYSTEM (Option 2)
# Omega scanned 3x per cycle for maximum speed, others scanned once
# Pattern: Omega -> B2 -> Omega -> B3 -> Omega -> B4 -> B5 -> repeat
# API Budget (7 entries, 12s peak / 60s off-peak):
#   Peak    (12s delay): 7x per ~84s  = ~43 cycles/hr = 300 calls/hr x 10h = 3,000
#   Off-peak (60s delay): 7x per ~7min = ~8.5 cycles/hr = 60 calls/hr  x 14h =   840
#   Total per day: ~3,840  (well within 5,000 limit, ~23% buffer)
#   Omega scan frequency: every ~24 seconds (was 75 seconds before)
# -------------------------------------------------------------------------
# Each tuple: (query_string, marketplace, is_lot_bucket)
TARGETS = [
    # 🚀 OMEGA PASS 1 of 3 — scanned first, immediately
    ("(Omega Speedmaster, Omega Seamaster, Omega Constellation, Omega De Ville, Omega Geneve, Omega Dynamic, Omega Railmaster)", "EBAY_US", False),

    # Bucket 2 - Mid-Range Vintage Collectibles ($50-$700 sweet spot)
    ("(Longines, Universal Geneve, Hamilton, Bulova, Tissot, Wittnauer, Movado, Zodiac)", "EBAY_US", False),

    # 🚀 OMEGA PASS 2 of 3 — scanned again after Bucket 2 (~24s gap)
    ("(Omega Speedmaster, Omega Seamaster, Omega Constellation, Omega De Ville, Omega Geneve, Omega Dynamic, Omega Railmaster)", "EBAY_US", False),

    # Bucket 3 - Japanese & Cult Brands (strong $50-$700 market)
    ("(Seiko, Grand Seiko, King Seiko, Enicar, Mido, Favre-Leuba, Elgin, Girard-Perregaux)", "EBAY_US", False),

    # 🚀 OMEGA PASS 3 of 3 — scanned again after Bucket 3 (~24s gap)
    ("(Omega Speedmaster, Omega Seamaster, Omega Constellation, Omega De Ville, Omega Geneve, Omega Dynamic, Omega Railmaster)", "EBAY_US", False),

    # Bucket 4 - Vintage Styles & Movements (broad category sweep)
    ("(vintage automatic watch, vintage mechanical watch, vintage diver, vintage chronograph, vintage military watch, Swiss vintage watch)", "EBAY_US", False),

    # Bucket 5 - Gold, Estate & Lots COMBINED (best ROI bucket)
    ("(14k vintage watch, 18k vintage watch, solid gold vintage watch, estate watch, antique watch, watchmaker lot, vintage watch lot, junk drawer watch, estate watch lot)", "EBAY_US", True),
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
HIGH_VALUE_DIALS = ["tropical", "salmon", "tiffany", "meteorite", "linen dial", "bullseye", "sector dial"]
FULL_SET_KEYWORDS = ["with original box", "box and papers", "b&p", "full kit", "complete set", "original papers"]
RUNNING_KEYWORDS = ["running", "working", "keeps time", "runs"]
BROKEN_KEYWORDS = ["untested", "not running", "for parts", "repair", "not working", "needs battery", "project", "spares", "fixer upper", "needs service", "needs tlc", "restoration"]
LADIES_KEYWORDS = ["ladies", "womens", "women"]

# -------------------------------------------------------------------------
# THE MODEL-LOCK SYSTEM
# Only brands we actually target under $700 are listed here.
# Luxury brands removed from buckets are kept ONLY for lot-hidden-gem detection.
# -------------------------------------------------------------------------
GENERIC_VALIDATORS = ["watch", "vintage", "mens", "womens", "ladies", "lot", "estate"]

VALID_MODELS = {
    # PRIMARY TARGET
    "omega": ["speedmaster", "seamaster", "constellation", "genève", "geneve", "de ville", "dynamic", "railmaster", "ranchero", "flightmaster", "chronostop", "memomatic", "cosmic", "automatic", "quartz"],

    # MID-RANGE VINTAGE (Bucket 2)
    "longines": ["conquest", "flagship", "ultra-chron", "admiral", "record", "legend diver", "skin diver", "dolcevita", "flyback"],
    "universal geneve": ["polerouter", "compax", "tri-compax", "uni-compax", "aero-compax", "space-compax", "white shadow", "golden shadow", "microtor", "cabriolet"],
    "hamilton": ["ventura", "electric", "khaki", "railroad", "watch"],
    "bulova": ["accutron", "caravelle", "spaceview", "snorkel", "lone eagle", "sea king", "day-date", "watch"],
    "tissot": ["seastar", "navigator", "visodate", "le locle", "pr50", "pr100", "watch"],
    "wittnauer": ["professional", "geneve", "electro-chron", "watch"],
    "movado": ["museum", "kingmatic", "sub sea", "triple calendar", "polyplan", "ermeto"],
    "zodiac": ["sea wolf", "aerospace", "super seawolf", "astrographic", "olympos", "chronograph"],

    # JAPANESE & CULT (Bucket 3)
    "seiko": ["grand seiko", "king seiko", "lord matic", "seiko 5", "presmatic", "lord marvel", "marvel", "crown", "sportsmatic", "bell-matic", "62mas", "6105", "6159", "6215", "6138", "6139", "5717", "5719", "bullhead", "pogue", "6306", "6309", "kakume", "ufo", "willard", "turtle", "alpinist"],
    "enicar": ["sherpa", "super dive", "graph", "star jewels", "ultrasonic"],
    "mido": ["commander", "ocean star", "multifort", "powerwind", "datoday"],
    "favre-leuba": ["raider", "bathy", "sea raider", "deep blue"],
    "elgin": ["railroad", "pocket", "watch"],
    "girard-perregaux": ["gyromatic", "chronometer hf", "laureato", "watch"],

    # KEPT FOR LOT/HIDDEN GEM DETECTION ONLY (not in search buckets)
    "rolex": ["oyster", "datejust", "day-date", "air-king", "explorer", "submariner", "gmt-master", "daytona", "milgauss", "sea-dweller", "precision", "bubbleback"],
    "tudor": ["submariner", "ranger", "snowflake", "oyster prince", "pelagos", "black bay"],
    "cartier": ["tank", "santos", "panthère", "must de cartier"],
    "patek": ["calatrava", "nautilus", "aquanaut"],
    "zenith": ["el primero", "defy", "captain", "elite"],
}

def is_model_locked(full_text, brand):
    validators = VALID_MODELS.get(brand, []) + [brand]
    return any(re.search(r'\b' + re.escape(v) + r'\b', full_text) for v in validators)

# -------------------------------------------------------------------------
# V6: OFF-MARKET SCANNER & SCRAP VALUE ENGINE
# -------------------------------------------------------------------------
def get_gold_scrap_value(full_text):
    if re.search(r'\b(plated|filled|gf|electroplated|gep|gp|rgp|rolled)\b', full_text): return 0
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
seen_items = {}

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

def get_item_age_minutes(creation_date_str):
    if not creation_date_str:
        return 999999
    try:
        creation_date_str = creation_date_str.replace('Z', '+00:00')
        creation_time = datetime.fromisoformat(creation_date_str)
        now = datetime.now(timezone.utc)
        time_since = now - creation_time
        return max(0, int(time_since.total_seconds() // 60))
    except Exception:
        return 999999

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
                return f"{mins}m ago" if mins > 0 else "Just now"
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

def get_smart_delay():
    """Priority fast-lane delays. Omega scanned 3x per cycle.
    7 entries per cycle. Budget math:
      Peak    (12s delay): 7 x 12s = 84s/cycle  -> ~43 cycles/hr -> 300 calls/hr x 10h = 3,000
      Off-peak (60s delay): 7 x 60s = 7min/cycle ->  ~8.5 cycles/hr -> 60 calls/hr  x 14h =   840
      TOTAL: ~3,840/day  (under 5,000 limit)
      Omega scanned every ~24 seconds at peak (3x per cycle).
    """
    current_hour = datetime.now(timezone.utc).hour
    # US peak listing hours: 11am-11pm EST = 16:00-04:00 UTC
    if 16 <= current_hour <= 23 or 0 <= current_hour <= 4:
        return 12  # Peak: Omega hit every ~24s (2 entries between each Omega)
    return 60      # Off-peak: full cycle every ~7 minutes

# -------------------------------------------------------------------------
# MAIN LOOP
# -------------------------------------------------------------------------
def start_sniper_bot():
    print("==========================================================")
    print("= EBAY 24/7 WATCH SNIPER (V8 - OMEGA PRIORITY FAST LANE) =")
    print("==========================================================")
    print(f"Monitoring: ${GLOBAL_MIN_PRICE_USD} - ${GLOBAL_MAX_PRICE_USD} USD")
    print("🚀 OMEGA scanned every ~24 seconds (3x per cycle - PRIORITY)")
    print("API budget: ~3,840 calls/day (under 5,000 limit)")
    print("Other brands scanned every ~84 seconds | Waiting for new listings...\n")
    
    client = EbayBrowseClient(load_config())
    
    # Load previously seen items from local JSONs to prevent duplicates on restart
    json_files = [
        "C:\\Users\\Oves\\Desktop\\Ebay\\live_snipes.json",
        "C:\\Users\\Oves\\Desktop\\Ebay\\deep_sweep_results.json"
    ] if os.name == 'nt' else ["live_snipes.json", "deep_sweep_results.json"]

    for json_file in json_files:
        if os.path.exists(json_file):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    for s in json.load(f):
                        if "Link" in s and "Price" in s:
                            try:
                                seen_items[s["Link"].split("?")[0]] = float(s["Price"])
                            except (ValueError, TypeError):
                                seen_items[s["Link"].split("?")[0]] = 999999.0
            except Exception as e:
                print(f"Error loading {json_file}: {e}")

    seen_notifications = set()

    # Also load recent deals from Supabase Cloud so Render restarts never treat old deals as new
    supabase_url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
    supabase_key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")
    if supabase_url and supabase_key:
        try:
            h = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"}
            r = requests.get(f"{supabase_url}/rest/v1/live_snipes?select=link,price&order=id.desc&limit=2000", headers=h, timeout=10)
            if r.status_code == 200:
                cloud_deals = r.json()
                for cd in cloud_deals:
                    if cd.get("link"):
                        clean_link = cd["link"].split("?")[0]
                        try:
                            seen_items[clean_link] = float(cd.get("price", 999999))
                        except (ValueError, TypeError):
                            seen_items[clean_link] = 999999.0
                        m = re.search(r'/itm/(\d+)', clean_link)
                        if m:
                            seen_notifications.add(m.group(1))
                        seen_notifications.add(clean_link)
                print(f"Loaded {len(cloud_deals)} existing deals from Supabase Cloud into memory.")
        except Exception as se:
            print(f"Notice: Supabase seed error: {se}")

    print(f"Loaded {len(seen_items)} previously seen deals from local backups & cloud.")
    print("Live monitoring started! Scanning directly for unmissed deals...\n")
    
    while True:
        for query, market, is_lot_bucket in TARGETS:
            try:
                # Prevent Memory Leak: Cap seen_items at 50,000
                if len(seen_items) > 50000:
                    seen_items.clear()

                # Lot buckets search all categories; brand buckets target watches (31387)
                cat_id = None if is_lot_bucket else "31387"
                data = client.search(query, limit=100, sort="newlyListed", filter="itemLocationCountry:US", category_ids=cat_id, marketplace=market)
                
                for item in data.get("itemSummaries", []):
                    url = item.get("itemWebUrl", "")
                    if url:
                        url = url.split("?")[0] # Strip eBay tracking parameters
                        
                    if not url:
                        continue
                        
                    # Extract price early for price drop detection
                    price_dict = item.get("price", {})
                    try:
                        raw_price = float(price_dict.get("value", 999999))
                        currency = price_dict.get("currency", "USD")
                    except:
                        continue
                        
                    price_usd = to_usd(raw_price, currency)
                    
                    is_price_drop = False
                    if url in seen_items:
                        old_price = seen_items[url]
                        if price_usd <= old_price - 1.0: # Dropped by at least $1
                            is_price_drop = True
                        else:
                            continue
                            
                    seen_items[url] = price_usd
                    
                    title = item.get("title", "Unknown Title")
                    if is_price_drop:
                        title = f"[📉 PRICE DROP] {title}"
                        
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
                        luxury_brands = ["rolex", "omega", "cartier", "tudor", "patek", "audemars", "jaeger-lecoultre", "jlc", "iwc", "breitling", "zenith", "breguet", "vacheron"]
                        if not re.search(r'\bvintage\b', full_text) and not any(re.search(r'\b' + brand + r'\b', full_text) for brand in luxury_brands):
                            continue
                            
                    # 3. Model Lock (brand detection from full_text, not from query string)
                    # With grouped queries like "(Rolex, Omega, Tudor...)" we detect
                    # the actual brand present in the listing title/description.
                    triggered_brand = next(
                        (b for b in VALID_MODELS.keys() if re.search(r'\b' + re.escape(b) + r'\b', full_text)),
                        None
                    )

                    if not is_lot_bucket:
                        # Non-lot buckets: must match a known brand or model
                        if triggered_brand:
                            if not is_model_locked(full_text, triggered_brand):
                                continue  # Has brand name but no recognized model — skip accessory/generic
                        else:
                            # No known brand found — must at least be a valid generic vintage watch
                            generic_ok = ["watch", "vintage", "antique", "estate"]
                            if not any(word in full_text for word in generic_ok):
                                continue

                    # 4. Strict Global Price Limit: $50 - $700 for ALL brands, no exceptions
                    if price_usd < GLOBAL_MIN_PRICE_USD or price_usd > GLOBAL_MAX_PRICE_USD:
                        continue

                    # 5. Lot-bucket validation & Hidden Gem detection
                    if is_lot_bucket:
                        luxury_brands = ["rolex", "omega", "patek", "audemars", "tudor", "cartier", "breitling", "zenith", "vacheron", "breguet", "iwc", "jaeger-lecoultre", "heuer"]
                        found_lux = [b for b in luxury_brands if re.search(r'\b' + b + r'\b', full_text)]
                        if found_lux:
                            title = f"[💎 HIDDEN GEM: {found_lux[0].upper()}] {title}"
                        
                    seller = item.get("seller", {})
                    url = item.get("itemWebUrl", "")
                    buying_options = item.get("buyingOptions", [])
                    
                    options_str = format_buying_options(buying_options)
                    safety_str = check_seller_safety(seller)
                    health_str = check_health(full_text)
                    
                    # Gold & Rare Dial & Full Set Checks
                    is_gold_jackpot = any(gold in full_text for gold in GOLD_KEYWORDS)
                    is_rare_dial = any(dial in full_text for dial in HIGH_VALUE_DIALS)
                    is_full_set = any(bp in full_text for bp in FULL_SET_KEYWORDS)
                    
                    if is_gold_jackpot:
                        title = f"[🚨 SOLID GOLD] {title}"
                    if is_rare_dial:
                        title = f"[🎨 RARE DIAL] {title}"
                    if is_full_set:
                        title = f"[🏆 FULL SET B&P] {title}"
                    
                    # V6 Engines
                    scrap_value = get_gold_scrap_value(full_text)
                    contacts = find_contact_info(full_text)
                    image_url = item.get("image", {}).get("imageUrl", "")
                    
                    time_listed = parse_time_listed(item.get("itemCreationDate"))
                    item_age_mins = get_item_age_minutes(item.get("itemCreationDate"))
                    is_fresh_listing = (item_age_mins <= MAX_SNIPE_AGE_MINUTES)
                    
                    # STRICT GATE: Only truly fresh new listings (e.g. <= 30 mins) or price drops qualify as LIVE SNIPES
                    if not is_fresh_listing and not is_price_drop:
                        # Silently remember in seen_items (already set above) so we don't scan again,
                        # but skip push alert, local export, and Supabase live feed insertion
                        continue

                    gender = extract_gender(full_text)
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    market_str = "\033[96m[GLOBAL ARBITRAGE]\033[0m" if market != "EBAY_US" else ""
                    
                    if is_gold_jackpot:
                        print(f"\n\033[45m\033[97m[{timestamp}] 🚨 SOLID GOLD JACKPOT ALERT 🚨 {market_str}\033[0m")
                    else:
                        print(f"\n\033[92m[{timestamp}] SNIPE ALERT: {query.upper()} {market_str}\033[0m")
                        
                    print(f"Title: {title} {health_str}")
                    print(f"Price: {raw_price} {currency} (~${int(price_usd)} USD) {options_str} | Listed: {time_listed} | Found: {timestamp}")
                    
                    if scrap_value > 0:
                        print(f"\033[93m=> EST. SCRAP VALUE: ${scrap_value} USD (GUARANTEED FLOOR)\033[0m")
                        
                    if contacts:
                        print(f"\033[91m=> [OFF-MARKET DEAL] Contact info found: {', '.join(contacts)}\033[0m")
                        
                    print(f"Seller: {seller.get('username', 'Unknown')} | Region: {market}{safety_str}")
                    print(f"Link: {url}")
                    
                    # Write to Overnight Log File
                    try:
                        # Use local directory if running on cloud
                        log_path = "C:\\Users\\Oves\\Desktop\\snipe_history.txt" if os.name == 'nt' else "snipe_history.txt"
                        with open(log_path, "a", encoding="utf-8") as f:
                            f.write(f"[{timestamp}] {market} | {title} | ~${int(price_usd)} USD | {url}\n")
                    except Exception:
                        pass
                        
                    # Write to Live JSON Feed for Dashboard (Legacy Backup)
                    try:
                        json_file = "C:\\Users\\Oves\\Desktop\\Ebay\\live_snipes.json" if os.name == 'nt' else "live_snipes.json"
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
                        snipes = snipes[:1000]
                        with open(json_file, "w", encoding="utf-8") as f:
                            json.dump(snipes, f, indent=4)
                            
                        # 1. TRIGGER INSTANT MOBILE PUSH NOTIFICATION IMMEDIATELY
                        push_status = "Not sent"
                        item_id_match = re.search(r'/itm/(?:[^/]+/)?(\d{9,14})', url) or re.search(r'(\d{9,14})', url)
                        item_id_key = item_id_match.group(1) if item_id_match else url

                        if len(seen_notifications) > 20000:
                            seen_notifications.clear()

                        if item_id_key in seen_notifications and not is_price_drop:
                            push_status = f"Deduplicated: Already notified item {item_id_key}"
                            print(f"ℹ️ {push_status}")
                        else:
                            seen_notifications.add(item_id_key)
                            try:
                                push_status = send_mobile_push(
                                    title=title,
                                    price_usd=price_usd,
                                    url=url,
                                    image_url=image_url,
                                    time_listed=time_listed,
                                    condition=item.get("condition", "Unknown"),
                                    health_str=health_str,
                                    options_str=options_str,
                                    scrap_value=scrap_value
                                )
                            except Exception as pe:
                                push_status = f"Push Trigger Error: {pe}"
                                print(push_status)

                        # 2. PUSH TO SUPABASE CLOUD (UPSERT)
                        supabase_url = os.getenv("SUPABASE_URL", "").strip('"').strip("'")
                        supabase_key = os.getenv("SUPABASE_KEY", "").strip('"').strip("'")
                        print(f"DEBUG: SUPABASE_URL loaded: {bool(supabase_url)}")
                        if supabase_url and supabase_key:
                            print("DEBUG: Pushing to Supabase...")
                            headers = {
                                "apikey": supabase_key,
                                "Authorization": f"Bearer {supabase_key}",
                                "Content-Type": "application/json",
                                "Prefer": "resolution=merge-duplicates"
                            }
                            
                            contacts_entry = f"Push: {push_status}"
                            if contacts:
                                contacts_entry += f" | {', '.join(contacts)}"

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
                                "contacts": contacts_entry,
                                "seller": seller.get("username", "Unknown"),
                                "link": url,
                                "excel_link": f'=HYPERLINK("{url}", "Open eBay")',
                                "image_url": image_url
                            }
                            
                            res = requests.post(f"{supabase_url}/rest/v1/live_snipes?on_conflict=link", headers=headers, json=payload, timeout=10)
                            if not res.ok:
                                print(f"\033[91mCloud Sync Error: {res.text}\033[0m")
                                
                    except Exception as e:
                        print(f"Export Error: {e}")
                        
            except Exception as e:
                print(f"API Error on bucket '{query[:40]}...' ({market}): {e}")

            time.sleep(get_smart_delay())

if __name__ == "__main__":
    # Start web server in background thread so Render keeps this script alive
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    try:
        start_sniper_bot()
    except KeyboardInterrupt:
        print("\nSniper Bot Terminated.")
        sys.exit(0)
