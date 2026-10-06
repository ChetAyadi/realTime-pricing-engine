import json
from channels.generic.websocket import AsyncWebsocketConsumer
from market.ingestion import MarketIngestionEngine

class MarketConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "market_updates"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send connection status and initial state snapshot to client
        engine = MarketIngestionEngine.get_instance()
        await self.send(text_data=json.dumps({
            "type": "connection_status",
            "status": engine.status,
            "last_error": engine.last_error,
            "total_ticks": engine.total_ticks_received
        }))

        # Send latest snapshot of all symbols
        snapshot = list(engine.latest_ticks.values())
        if snapshot:
            await self.send(text_data=json.dumps({
                "type": "market_snapshot",
                "data": snapshot
            }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming WebSocket commands from client dashboard."""
        try:
            data = json.loads(text_data)
            action = data.get("action")
            
            if action == "ping":
                await self.send(text_data=json.dumps({"type": "pong"}))
            elif action == "get_status":
                engine = MarketIngestionEngine.get_instance()
                await self.send(text_data=json.dumps({
                    "type": "connection_status",
                    "status": engine.status,
                    "last_error": engine.last_error,
                    "total_ticks": engine.total_ticks_received
                }))
        except Exception:
            pass

    async def market_tick(self, event):
        """Handler for ticks broadcast from Ingestion Engine."""
        await self.send(text_data=json.dumps({
            "type": "market_tick",
            "data": event["data"]
        }))
