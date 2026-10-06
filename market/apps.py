import asyncio
import os
import threading
from django.apps import AppConfig

class MarketConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'market'

    def ready(self):
        # Auto-start WebSocket ingestion background thread when Django server launches
        if os.environ.get('RUN_MAIN') == 'true' or os.environ.get('START_INGESTION') == 'true':
            from market.ingestion import MarketIngestionEngine
            
            def run_background_loop():
                engine = MarketIngestionEngine.get_instance()
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(engine.run())

            t = threading.Thread(target=run_background_loop, daemon=True, name="IngestionEngineThread")
            t.start()
