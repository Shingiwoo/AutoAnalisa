from fastapi import APIRouter, Query
import ccxt

router = APIRouter(prefix="/api/meta", tags=["meta"])


def _norm_symbol(sym: str) -> str:
    s = sym.upper().replace(":USDT", "/USDT")
    if "/" not in s and s.endswith("USDT"):
        s = f"{s[:-4]}/USDT"
    return s


@router.get("/symbol")
async def symbol_meta(symbol: str = Query(...), market: str = Query("spot")):
    ex = ccxt.binance() if str(market).lower() != "futures" else ccxt.binanceusdm()
    ex.load_markets(reload=False)
    m = ex.market(_norm_symbol(symbol))
    price_prec = None
    tick = None
    step = None
    if m.get("precision") and "price" in m["precision"]:
        price_prec = int(m["precision"]["price"])
        tick = float(10 ** (-price_prec)) if price_prec > 0 else 1.0
    limits = m.get("limits") or {}
    if not tick and limits.get("price") and limits["price"].get("min"):
        tick = float(limits["price"]["min"]) or None
    if limits.get("amount") and limits["amount"].get("min"):
        step = float(limits["amount"]["min"]) or None
    quote_prec = m.get("info", {}).get("quotePrecision") or None
    try:
        quote_prec = int(quote_prec) if quote_prec is not None else None
    except Exception:
        pass
    return {
        "symbol": symbol.upper(),
        "market": market,
        "price_tick": tick,
        "qty_step": step,
        "price_decimals": price_prec,
        "quote_precision": quote_prec,
    }

