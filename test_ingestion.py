import asyncio
import json
import os
import sys
from dotenv import load_dotenv
import websockets

# Load environment variables from .env file
load_dotenv()

WS_URL = os.getenv("LIVEFX_WS_URL", "wss://v3-prod.livefxhub.com/ws/algo")
API_KEY = os.getenv("LIVEFX_API_KEY") or os.getenv("API_KEY")
SECRET_KEY = os.getenv("LIVEFX_SECRET_KEY") or os.getenv("SECRET_KEY") or os.getenv("SECRET")

ALL_SYMBOLS = [
    "AUDUSD", "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD",
    "AUDSGD", "CADCHF", "CADJPY", "CHFJPY", "CHFSGD",
    "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY",
    "EURNZD", "EURUSD", "GBPAUD", "GBPCAD", "GBPCHF",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCAD", "NZDCHF",
    "NZDJPY", "NZDUSD", "USDCAD", "USDCHF", "USDCNH",
    "USDJPY", "USDMXN", "USDNOK", "USDPLN", "USDSEK",
    "USDSGD", "USDTRY", "USDZAR", "EURTRY", "GBPTRY",
    "NOKJPY", "SEKJPY", "SGDJPY", "ZARJPY", "XAUUSD",
    "XAGUSD", "BTCUSD", "ETHUSD", "BNBUSD", "SOLUSD",
    "XRPUSD", "ADAUSD", "DOGUSD", "DOTUSD", "LTCUSD",
    "BCHUSD", "XLMUSD", "TRXUSD", "UNIUSD", "FILUSD",
    "AVXUSD"
]

async def test_websocket_ingestion():
    print("=" * 60)
    print("STEP 1: Checking API Credentials in .env")
    print(f"WS URL     : {WS_URL}")
    print(f"API Key    : {'[PRESENT]' if API_KEY else '[MISSING]'}")
    print(f"Secret Key : {'[PRESENT]' if SECRET_KEY else '[MISSING]'}")
    print("=" * 60)

    if not API_KEY or not SECRET_KEY:
        print("[ERROR] API Key or Secret Key is missing in .env environment file.")
        print("Please set LIVEFX_API_KEY and LIVEFX_SECRET_KEY in .env!")
        return False

    print(f"\nSTEP 2: Connecting to WebSocket at {WS_URL}...")
    try:
        async with websockets.connect(WS_URL) as ws:
            print("[SUCCESS] Connected to LiveFXHub WebSocket endpoint.")

            # Step 3: Send authentication payload
            auth_payload = {
                "action": "auth",
                "api_key": API_KEY,
                "secret": SECRET_KEY
            }
            print(f"\nSTEP 3: Sending Auth Request: action='auth' (Key length: {len(API_KEY)})")
            await ws.send(json.dumps(auth_payload))

            # Step 4: Wait for authentication response
            print("STEP 4: Waiting for Authentication Response...")
            auth_resp_raw = await ws.recv()
            print(f"[AUTH RESPONSE RECEIVED]: {auth_resp_raw}")
            
            try:
                auth_resp = json.loads(auth_resp_raw)
            except Exception:
                auth_resp = {"raw": auth_resp_raw}

            # Check for auth success indicator
            # Common patterns: {"status": "success"}, {"authenticated": True}, {"action": "auth", "status": ...}
            is_success = False
            if isinstance(auth_resp, dict):
                status = str(auth_resp.get("status", "")).lower()
                message = str(auth_resp.get("message", "")).lower()
                event = str(auth_resp.get("event", "")).lower()
                action = str(auth_resp.get("action", "")).lower()
                
                if status in ["success", "ok", "authenticated", "true"] or "authenticated" in message or "success" in message:
                    is_success = True
                elif auth_resp.get("authenticated") is True or auth_resp.get("success") is True:
                    is_success = True
                elif status == "" and "error" not in auth_resp_raw.lower() and "fail" not in auth_resp_raw.lower():
                    # If server responds without explicit error, assume success or inspect further
                    is_success = True

            if not is_success and ("fail" in auth_resp_raw.lower() or "error" in auth_resp_raw.lower() or "invalid" in auth_resp_raw.lower()):
                print(f"[ERROR] Authentication FAILED! Response: {auth_resp_raw}")
                print("Subscription aborted because authentication was not successful.")
                return False

            print("[SUCCESS] Authentication succeeded!")

            # Step 5: Subscribe to symbols
            sub_payload = {
                "action": "subscribeMarketPrice",
                "symbols": ALL_SYMBOLS
            }
            print(f"\nSTEP 5: Subscribing to {len(ALL_SYMBOLS)} symbols...")
            await ws.send(json.dumps(sub_payload))

            # Step 6 & 7: Receive and display real market ticks
            print("\nSTEP 6 & 7: Receiving Real Market Data Messages...")
            received_count = 0
            while received_count < 10:
                msg = await ws.recv()
                received_count += 1
                print(f"\n--- [MARKET TICK #{received_count}] ---")
                print(msg)
                
                try:
                    data = json.loads(msg)
                    symbol = data.get("symbol", "N/A")
                    buy = data.get("buy", "N/A")
                    sell = data.get("sell", "N/A")
                    ts = data.get("timestamp", "N/A")
                    print(f"Parsed -> Symbol: {symbol} | Buy: {buy} | Sell: {sell} | Timestamp: {ts}")
                except Exception as e:
                    print(f"Raw message parse error: {e}")

            print("\n[VERIFICATION COMPLETE] Successfully received real market data ticks!")
            return True

    except Exception as e:
        print(f"\n[CONNECTION ERROR] Failed to connect or communicate with WebSocket: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_websocket_ingestion())
