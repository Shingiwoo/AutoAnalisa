async def btc_gate_ok() -> bool:
    # stub: selalu OK untuk lokal; dapat dikembangkan
    return True


async def session_gate_ok(symbol: str) -> bool:
    """Return False di ±30 menit sebelum/sesudah rilis CPI/PPI/NFP/FOMC/PMI.
    (Integrasi dengan tabel/endpoint MacroDaily bila tersedia.)
    Sementara, placeholder selalu OK.
    """
    return True
