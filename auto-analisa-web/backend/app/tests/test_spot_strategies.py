import types
from app.services.regime import detect_regime
from app.services.strategies_spot import assemble


class DF(types.SimpleNamespace):
    def __init__(self, close, ema20, ema50, ema100, ub, dn, mb, atr14):
        for k, v in locals().items():
            if k != 'self': setattr(self, k, v)
    def __getitem__(self, k): return getattr(self, k)
    def __len__(self): return 120
    @property
    def iloc(self):
        class I:
            def __init__(self, o): self.o = o
            def __getitem__(self, idx):
                return types.SimpleNamespace(**{k: getattr(self.o, k)[idx] for k in vars(self.o) if k != '__weakref__'})
        return I(self)


def _series(val): return [val] * 200


bundle = {
    "15m": DF(close=_series(1.0), ema20=_series(1.0), ema50=_series(0.99), ema100=_series(0.98), ub=_series(1.02), dn=_series(0.98), mb=_series(1.0), atr14=_series(0.01)),
    "1h":  DF(close=_series(1.0), ema20=_series(1.0), ema50=_series(0.99), ema100=_series(0.98), ub=_series(1.02), dn=_series(0.98), mb=_series(1.0), atr14=_series(0.01))
}
levels = {"support": [0.98, 0.96], "resistance": [1.02, 1.04]}


def test_assemble_has_rr_basics():
    reg = detect_regime(bundle)
    plan = assemble(bundle, levels, reg["regime"])
    assert plan["invalid"] < min(plan["entries"]) < plan["tp"][0]

