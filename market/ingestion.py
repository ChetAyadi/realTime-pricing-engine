import asyncio
import json
import logging
import os
import time
from collections import deque
from typing import Dict, Tuple
from asgiref.sync import async_to_sync, sync_to_async
import channels.layers
from dotenv import load_dotenv
import websockets


load_dotenv()
logger = logging.getLogger(__name__)

WS_URL = os.getenv("LIVEFX_WS_URL", "wss://v3-prod.livefxhub.com/ws/algo")
ALL_SYMBOLS = [
    "AUDUSD", "AUDCAD", "AUDCHF", "AUDJPY", "AUDNZD", "AUDSGD", "CADCHF", "CADJPY", "CHFJPY", "CHFSGD",
    "EURAUD", "EURCAD", "EURCHF", "EURGBP", "EURJPY", "EURNZD", "EURUSD", "GBPAUD", "GBPCAD", "GBPCHF",
    "GBPJPY", "GBPNZD", "GBPUSD", "NZDCAD", "NZDCHF", "NZDJPY", "NZDUSD", "USDCAD", "USDCHF", "USDCNH",
    "USDJPY", "USDMXN", "USDNOK", "USDPLN", "USDSEK", "USDSGD", "USDTRY", "USDZAR", "EURTRY", "GBPTRY",
    "NOKJPY", "SEKJPY", "SGDJPY", "ZARJPY", "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "BNBUSD", "SOLUSD",
    "XRPUSD", "ADAUSD", "DOGUSD", "DOTUSD", "LTCUSD", "BCHUSD", "XLMUSD", "TRXUSD", "UNIUSD", "FILUSD",
    "AVXUSD"
]

WINDOW_24H_MS = 24 * 60 * 60 * 1000

class MarketIngestionEngine:
    _instance = None

    def __init__(self):
        self.rolling_windows: Dict[str, deque] = {s: deque() for s in ALL_SYMBOLS}
        self.latest_ticks: Dict[str, dict] = {}
        self.status = "DISCONNECTED"
        self.last_error = None
        self.total_ticks_received = 0
        self.is_running = False

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @sync_to_async
    def _fetch_db_ticks(self):
        try:
            from market.models import MarketTick
            return list(MarketTick.objects.all())
        except Exception:
            return []

    async def load_persisted_state(self):
        try:
            ticks = await self._fetch_db_ticks()
            for t in ticks:
                self.latest_ticks[t.symbol] = t.to_dict()
                if t.symbol in self.rolling_windows and t.buy > 0:
                    self.rolling_windows[t.symbol].append((t.timestamp, (t.buy + t.sell) / 2))
            logger.info(f"Loaded {len(ticks)} persisted market ticks from DB.")
        except Exception as e:
            logger.warning(f"Could not load DB state: {e}")

    def update_rolling_window(self, symbol: str, price: float, timestamp_ms: int) -> Tuple[float, float, float]:
        window = self.rolling_windows.get(symbol)
        if window is None:
            window = deque()
            self.rolling_windows[symbol] = window

        cutoff = timestamp_ms - WINDOW_24H_MS
        while window and window[0][0] < cutoff:
            window.popleft()

        if not window or timestamp_ms >= window[-1][0]:
            window.append((timestamp_ms, price))

        prices = [p for _, p in window]
        high_24h = max(prices)
        low_24h = min(prices)
        
        open_24h_price = prices[0]
        change_24h = ((price - open_24h_price) / open_24h_price) * 100.0 if open_24h_price > 0 else 0.0

        return high_24h, low_24h, change_24h

    def process_incoming_tick(self, raw_data: dict):
        symbol = raw_data.get("symbol") or raw_data.get("s")
        if not symbol:
            return

        try:
            buy = float(raw_data.get("buy") or raw_data.get("ask") or raw_data.get("a") or 0.0)
            sell = float(raw_data.get("sell") or raw_data.get("bid") or raw_data.get("b") or 0.0)
            raw_ts = raw_data.get("timestamp") or raw_data.get("ts") or raw_data.get("t")
            
            if raw_ts:
                ts = int(raw_ts)
                if ts < 10000000000:
                    ts *= 1000
            else:
                ts = int(time.time() * 1000)

            mid_price = (buy + sell) / 2.0 if (buy > 0 and sell > 0) else buy

            # Price spike check
            if symbol in self.latest_ticks and self.latest_ticks[symbol].get("buy", 0) > 0:
                last_buy = self.latest_ticks[symbol]["buy"]
                if abs(buy - last_buy) / last_buy > 0.5:
                    logger.warning(f"Spike ignored on {symbol}: buy={buy}, last={last_buy}")
                    return

            high_24h, low_24h, change_24h = self.update_rolling_window(symbol, mid_price, ts)

            processed_tick = {
                "symbol": symbol,
                "buy": round(buy, 5),
                "sell": round(sell, 5),
                "high_24h": round(high_24h, 5),
                "low_24h": round(low_24h, 5),
                "change_24h": round(change_24h, 4),
                "timestamp": ts
            }

            self.latest_ticks[symbol] = processed_tick
            self.total_ticks_received += 1
            self.broadcast_tick(processed_tick)

        except Exception as e:
            logger.error(f"Error processing tick for {symbol}: {e}")

    def broadcast_tick(self, tick: dict):
        try:
            channel_layer = channels.layers.get_channel_layer()
            if channel_layer:
                async_to_sync(channel_layer.group_send)(
                    "market_updates",
                    {
                        "type": "market_tick",
                        "data": tick
                    }
                )
        except Exception as e:
            logger.debug(f"Broadcast error: {e}")

    async def run(self):
        self.is_running = True
        await self.load_persisted_state()

        while self.is_running:
            api_key = os.getenv("LIVEFX_API_KEY") or os.getenv("API_KEY")
            secret_key = os.getenv("LIVEFX_SECRET_KEY") or os.getenv("SECRET_KEY")

            if not api_key or not secret_key:
                self.status = "CREDENTIALS_MISSING"
                self.last_error = "LIVEFX_API_KEY / LIVEFX_SECRET_KEY missing in .env"
                await asyncio.sleep(5)
                continue

            self.status = "CONNECTING"
            try:
                async with websockets.connect(WS_URL, ping_interval=30, ping_timeout=10) as ws:
                    self.status = "AUTHENTICATING"
                    auth_payload = {
                        "action": "auth",
                        "api_key": api_key,
                        "secret": secret_key
                    }
                    await ws.send(json.dumps(auth_payload))
                    auth_resp_raw = await ws.recv()
                    
                    auth_resp = json.loads(auth_resp_raw)
                    if auth_resp.get("status") not in ["success", "ok"] and "error" in auth_resp_raw.lower():
                        self.status = "AUTH_FAILED"
                        self.last_error = f"Auth failed: {auth_resp_raw}"
                        await asyncio.sleep(10)
                        continue

                    self.status = "CONNECTED"
                    self.last_error = None
                    
                    sub_payload = {
                        "action": "subscribeMarketPrice",
                        "symbols": ALL_SYMBOLS
                    }
                    await ws.send(json.dumps(sub_payload))

                    while self.is_running:
                        msg = await ws.recv()
                        try:
                            data = json.loads(msg)
                            if isinstance(data, list):
                                for item in data:
                                    self.process_incoming_tick(item)
                            elif isinstance(data, dict):
                                if "data" in data and isinstance(data["data"], list):
                                    for item in data["data"]:
                                        self.process_incoming_tick(item)
                                elif "data" in data and isinstance(data["data"], dict):
                                    self.process_incoming_tick(data["data"])
                                else:
                                    self.process_incoming_tick(data)
                        except Exception as parse_err:
                            logger.error(f"Failed to parse websocket frame: {parse_err}")

            except Exception as conn_err:
                self.status = "DISCONNECTED"
                self.last_error = str(conn_err)
                logger.warning(f"WebSocket connection lost. Retrying in 5s: {conn_err}")
                await asyncio.sleep(5)