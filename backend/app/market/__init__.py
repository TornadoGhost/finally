"""Market data subsystem for FinAlly.

Public API:
    PriceUpdate         - Immutable price snapshot dataclass
    PriceCache          - Thread-safe in-memory price store
    MarketDataSource    - Abstract interface for data providers
    create_market_data_source - Factory that selects simulator or Massive
    create_stream_router - FastAPI router factory for SSE endpoint
    get_price_cache     - Returns the shared PriceCache singleton
"""

from .cache import PriceCache
from .factory import create_market_data_source
from .interface import MarketDataSource
from .models import PriceUpdate
from .stream import create_stream_router

_price_cache: PriceCache | None = None


def register_price_cache(cache: PriceCache) -> None:
    """Called by main.py to register the shared cache so other modules can access it."""
    global _price_cache
    _price_cache = cache


def get_price_cache() -> PriceCache:
    """Return the shared PriceCache. Raises RuntimeError if not yet registered."""
    if _price_cache is None:
        raise RuntimeError("PriceCache not yet initialized. Call register_price_cache first.")
    return _price_cache


__all__ = [
    "PriceUpdate",
    "PriceCache",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
    "register_price_cache",
    "get_price_cache",
]
