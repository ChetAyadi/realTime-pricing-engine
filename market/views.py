from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from market.models import MarketTick
from market.serializers import MarketTickSerializer
from market.ingestion import MarketIngestionEngine, ALL_SYMBOLS

def dashboard(request):
    """Renders the Django Template Dashboard."""
    engine = MarketIngestionEngine.get_instance()
    context = {
        "symbols_count": len(ALL_SYMBOLS),
        "status": engine.status,
        "last_error": engine.last_error,
    }
    return render(request, "market/dashboard.html", context)


class MarketTickListView(APIView):
    """GET /api/prices/ - Returns current snapshot of all symbols."""
    def get(self, request):
        engine = MarketIngestionEngine.get_instance()
        # Prefer in-memory state if available, else DB
        if engine.latest_ticks:
            data = list(engine.latest_ticks.values())
            return Response(data)
        
        ticks = MarketTick.objects.all()
        serializer = MarketTickSerializer(ticks, many=True)
        return Response(serializer.data)


class MarketTickDetailView(APIView):
    """GET /api/prices/<symbol>/ - Returns data for a specific symbol."""
    def get(self, request, symbol):
        symbol = symbol.upper()
        engine = MarketIngestionEngine.get_instance()
        
        if symbol in engine.latest_ticks:
            return Response(engine.latest_ticks[symbol])
            
        try:
            tick = MarketTick.objects.get(symbol=symbol)
            serializer = MarketTickSerializer(tick)
            return Response(serializer.data)
        except MarketTick.DoesNotExist:
            return Response({"error": f"Symbol '{symbol}' not found."}, status=status.HTTP_404_NOT_FOUND)


class EngineStatusView(APIView):
    """GET /api/status/ - Returns ingestion engine connection and auth status."""
    def get(self, request):
        engine = MarketIngestionEngine.get_instance()
        return Response({
            "status": engine.status,
            "last_error": engine.last_error,
            "total_ticks_received": engine.total_ticks_received,
            "symbols_count": len(ALL_SYMBOLS),
            "tracked_symbols": len(engine.latest_ticks)
        })
