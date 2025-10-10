from app.v2_schemas.market import MarketSnapshot
from app.v2_schemas.llm_input import LlmPrompt
from app.v2_schemas.llm_output import LlmOutput
from app.services.strategy_futures import PROFILES


SYSTEM = (
    "You are a crypto trading analyst. Receive structured market data (no images). "
    "Respond ONLY in JSON that conforms to the provided JSON Schema. "
    "If btc_bias is provided, ALL trade plans must align with it (NO conflicting sides)."
)

TEMPLATE_USER = (
    "Analyze {symbol} on {tf}. Last price: {price}.\n"
    "Indicators: EMA5={ema5}, EMA20={ema20}, EMA50={ema50}, RSI14={rsi14}, MACD={macd}/{macd_signal}.\n"
    "Bollinger: UP={bb_up}, MID={bb_mid}, LOW={bb_low}.\n"
    "btc_bias={btc_bias}. If btc_bias is 'bullish_*' → prefer LONG-only; if 'bearish_*' → prefer SHORT-only; if 'neutral' → allow both but avoid conflict with context.\n"
    "Profile preference: {profile}. Use these constraints when applicable: rr_min={rr_min}, sl_buf_atr={sl_buf_atr}, tp_atr={tp_atr}, ttl_min={ttl_min}.\n"
    "Return trade plan with 2 entry levels (pullback + breakout), 2-3 TP, 1 SL."
)


# JSON Schema generated from Pydantic for strict LLM output
JSON_SCHEMA = LlmOutput.model_json_schema()


def build(snapshot: MarketSnapshot, profile: str | None = None) -> LlmPrompt:
    ind = snapshot.indicators
    pkey = (profile or 'auto').lower()
    pmap = PROFILES.get('scalp' if pkey=='auto' and snapshot.timeframe in {'15m','5m','1m'} else pkey, PROFILES.get('swing')) if pkey!='auto' else (PROFILES.get('scalp') if snapshot.timeframe in {'1m','5m','15m'} else PROFILES.get('swing'))
    rr_min = (pmap or {}).get('min_rr', None)
    sl_buf = (pmap or {}).get('sl_buf_atr', None)
    tp_atr = (pmap or {}).get('tp_atr', None)
    ttl_min = (pmap or {}).get('ttl_min', None)
    user = TEMPLATE_USER.format(
        symbol=snapshot.symbol,
        tf=snapshot.timeframe,
        price=snapshot.last_price,
        ema5=ind.ema5,
        ema20=ind.ema20,
        ema50=ind.ema50,
        rsi14=ind.rsi14,
        macd=ind.macd,
        macd_signal=ind.macd_signal,
        bb_up=ind.bb_up,
        bb_mid=ind.bb_mid,
        bb_low=ind.bb_low,
        btc_bias=(snapshot.btc_bias or "unknown"),
        profile=(profile or 'auto'),
        rr_min=rr_min,
        sl_buf_atr=sl_buf,
        tp_atr=tp_atr,
        ttl_min=ttl_min,
    )
    return LlmPrompt(system=SYSTEM, user=user, json_schema=JSON_SCHEMA)
