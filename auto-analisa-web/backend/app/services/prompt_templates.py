from __future__ import annotations
from typing import Any, Dict
import json


def _schema_block() -> str:
    return (
        '{\n'
        '  "symbol": "...",\n'
        '  "mode": "scalping|swing",\n'
        '  "text": {\n'
        '    "section_scalping": {\n'
        '      "posisi": "LONG|SHORT|NO-TRADE",\n'
        '      "tp": [number, number, number],\n'
        '      "sl": number,\n'
        '      "bybk": [{"zone":[number,number],"note":"..."}],\n'
        '      "bo": [{"above":number,"note":"..."},{"below":number,"note":"..."}],\n'
        '      "strategi_singkat": ["..."],\n'
        '      "fundamental": ["..."]\n'
        '    },\n'
        '    "section_swing": null\n'
        '  },\n'
        '  "overlay": {\n'
        '    "tf": "5m|15m|1h|4h",\n'
        '    "lines": [{"type":"SL|TP","label":"TP1|TP2|TP3|SL","price": number}],\n'
        '    "zones": [{"type":"ENTRY|BYBK","range":[number, number]}],\n'
        '    "markers": [{"type":"BO","price": number, "label": "..."}]\n'
        '  },\n'
        '  "meta": {"engine": "gpt", "notes": ["..."]}\n'
        '}\n'
    )


def prompt_scalping(symbol: str, payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    return (
        "Kamu adalah profesional trader futures kripto.\n"
        "Tugas: buat analisa FUTURES scalping 5m–15m untuk {symbol} berbasis payload JSON (tanpa screenshot).\n"
        "Ikuti aturan pullback 1–4% (winrate target 65–75%, PF > 2) dari dokumen rules internal.\n"
        "Keluarkan JSON valid (object) persis schema berikut: \n"
        f"{_schema_block()}\n"
        "Ketentuan: gunakan ATR/EMA/BB/RSI6/levels di payload. Target TP 1–3% (ATR-aware). \n"
        "Jika ragu / sinyal lemah → beri skenario konservatif dan tandai WARNING (bukan NO-TRADE). \n"
        "Gunakan NO-TRADE hanya pada kondisi ekstrim (volatilitas/berita tinggi, struktur rusak). Overlay tetap isi level konservatif jika memungkinkan. \n"
        "Gunakan WIB sebagai konteks sesi bila tersedia.\n"
        f"SYMBOL: {symbol}\n"
        f"PAYLOAD: {payload_json}\n"
    )


def prompt_swing(symbol: str, payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False)
    return (
        "Kamu adalah profesional trader futures kripto.\n"
        "Tugas: buat analisa FUTURES swing 1H–4H untuk {symbol} berbasis payload JSON.\n"
        "Ikuti aturan pullback (RR ≥ 1.8) dan struktur HH/HL atau LH/LL.\n"
        "Keluarkan JSON valid (object) persis schema berikut: \n"
        f"{_schema_block()}\n"
        "Ketentuan: target TP 2–6% (ATR-aware), jaga ascending TP, dan gunakan invalid/SL logis.\n"
        "Jika ragu / borderline → berikan sisi preferensi + level konservatif dan beri WARNING. Gunakan NO-TRADE hanya untuk kondisi ekstrim.\n"
        f"SYMBOL: {symbol}\n"
        f"PAYLOAD: {payload_json}\n"
    )
