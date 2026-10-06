from rest_framework import serializers
from market.models import MarketTick

class MarketTickSerializer(serializers.ModelSerializer):
    high_24h = serializers.FloatField(source='computed_high_24h')
    low_24h = serializers.FloatField(source='computed_low_24h')
    change_24h = serializers.FloatField(source='computed_change_24h')

    class Meta:
        model = MarketTick
        fields = ['symbol', 'buy', 'sell', 'high_24h', 'low_24h', 'change_24h', 'timestamp', 'last_updated']
