from fastapi import FastAPI
import threading
import uvicorn
import os
import sniper

# Create a tiny "fake" web server to trick Render into giving us a Free Tier
app = FastAPI()

@app.get("/")
def read_root():
    return {"status": "Active", "message": "Ebay Sniper Bot is Running 24/7!"}

@app.get("/ping")
def ping():
    return "pong"

def run_bot_in_background():
    print("Starting background sniper bot on Render Free Tier...")
    try:
        sniper.start_sniper_bot()
    except Exception as e:
        print(f"Background bot error: {e}")

if __name__ == "__main__":
    # 1. Start your actual eBay Sniper Bot in a background thread
    bot_thread = threading.Thread(target=run_bot_in_background, daemon=True)
    bot_thread.start()
    
    # 2. Start the web server on Render's required port to keep it online for FREE
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
