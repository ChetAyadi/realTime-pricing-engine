from django.db import models

class MarketTick(models.Model):
    """
    Stores the latest processed market tick state for each symbol.
    Persisted to database to survive server process restarts.
    """
    symbol = models.CharField(max_length=20, primary_key=True)
    buy = models.FloatField(default=0.0)
    sell = models.FloatField(default=0.0)
    timestamp = models.BigIntegerField(default=0)
    computed_high_24h = models.FloatField(default=0.0)
    computed_low_24h = models.FloatField(default=0.0)
    computed_change_24h = models.FloatField(default=0.0)
    last_updated = models.DateTimeField(auto_now=True)

    def to_dict(self):
        return {
            "symbol": self.symbol,
            "buy": round(self.buy, 5),
            "sell": round(self.sell, 5),
            "high_24h": round(self.computed_high_24h, 5),
            "low_24h": round(self.computed_low_24h, 5),
            "change_24h": round(self.computed_change_24h, 4),
            "timestamp": self.timestamp
        }

    def __str__(self):
        return f"{self.symbol} | Buy: {self.buy} | Sell: {self.sell} | Change: {self.computed_change_24h}%"


class PricePoint(models.Model):
    """
    Stores price ticks for rolling 24-hour window calculations.
    """
    symbol = models.CharField(max_length=20, db_index=True)
    price = models.FloatField()
    timestamp = models.BigIntegerField(db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['symbol', 'timestamp']),
        ]
