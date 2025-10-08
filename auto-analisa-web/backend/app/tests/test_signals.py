from app.services.scorer import score_ema50, score_rsi, score_macd
from app.services.aggregator import weighted_avg, bucket_strength


def test_score_ema50_neutral_zone():
    assert score_ema50(100, 100.1, atr14=5.0, k_atr=0.05) == 0


def test_score_rsi_bands():
    bands = { 'long_lo': 55, 'long_hi': 70, 'short_hi': 45, 'short_lo': 30, 'mid_lo': 45, 'mid_hi': 55 }
    assert score_rsi(60, bands) == 1
    assert score_rsi(40, bands) == -1
    assert score_rsi(50, bands) == 0


def test_weighted_avg_range():
    s = {'ST':1,'EMA50':1,'RSI':0,'MACD':-1}
    w = {'ST':0.6,'EMA50':0.2,'RSI':0.1,'MACD':0.1}
    v = weighted_avg(s, w)
    assert -1.0 <= v <= 1.0


def test_bucket_strength_thresholds():
    assert bucket_strength(0.10) == 'NONE'
    assert bucket_strength(0.30) == 'WEAK'
    assert bucket_strength(0.50) == 'MEDIUM'
    assert bucket_strength(0.60) == 'STRONG'
    assert bucket_strength(0.80) == 'EXTREME'

