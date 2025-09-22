import time
import types

from app.services import symbols_binance as sb


def test_get_symbols_cache(monkeypatch):
    class DummyExchange:
        def __init__(self, *args, **kwargs):
            pass

        def load_markets(self):
            return {
                "BTC/USDT": {"spot": True, "quote": "USDT"},
                "ETH/USDT": {"spot": True, "quote": "USDT"},
                "BTCUSDT": {"future": True},
            }

    monkeypatch.setattr(sb, "ccxt", types.SimpleNamespace(binance=lambda cfg=None: DummyExchange()))
    sb._state = {"ts": 0.0, "spot": [], "futures": []}

    spot = sb.get_symbols("spot")
    futs = sb.get_symbols("futures")
    assert spot == ["BTC/USDT", "ETH/USDT"]
    assert futs == ["BTCUSDT"]

    sb._state["spot"] = ["CACHE"]
    sb._state["ts"] = time.time()
    assert sb.get_symbols("spot") == ["CACHE"]
