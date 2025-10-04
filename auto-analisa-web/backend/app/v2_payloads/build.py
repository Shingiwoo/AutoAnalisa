from app.v2_schemas.market import MarketSnapshot
from app.v2_schemas.llm_input import LlmPrompt
from app.v2_schemas.llm_output import LlmOutput


SYSTEM = (
    "You are a crypto trading analyst. Receive structured market data (no images). "
    "Respond ONLY in JSON that conforms to the provided JSON Schema."
)

TEMPLATE_USER = (
    "Analyze {symbol} on {tf}. Last price: {price}.\n"
    "Indicators: EMA5={ema5}, EMA20={ema20}, EMA50={ema50}, RSI14={rsi14}, MACD={macd}/{macd_signal}.\n"
    "Bollinger: UP={bb_up}, MID={bb_mid}, LOW={bb_low}.\n"
    "Return trade plan with 2 entry levels (pullback + breakout), 2-3 TP, 1 SL."
)


# JSON Schema generated from Pydantic for strict LLM output
JSON_SCHEMA = LlmOutput.model_json_schema()


def build(snapshot: MarketSnapshot) -> LlmPrompt:
    ind = snapshot.indicators
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
    )
    return LlmPrompt(system=SYSTEM, user=user, json_schema=JSON_SCHEMA)

