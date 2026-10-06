"""Moteur de signaux multi-facteurs multi-timeframes (mécanique Penifx).

Pour chaque timeframe (1m / 5m / 15m) un score directionnel est calculé à
partir de RSI, MACD, croisement d'EMA, position dans les bandes de
Bollinger, Stochastic et z-score du volume. Les timeframes sont pondérés
(1m 0.20 / 5m 0.35 / 15m 0.45), la confiance finale est 50 + 47×|score|
bornée à 97. Un signal part si confiance >= 65 (défaut Penifx).
"""
from .indicators import ema, rsi, macd, atr, bollinger, stochastic, zscore
from .data import resample

MIN_CONF = 65
# Echelle calibrée sur la distribution réelle des scores (calibration 06/10/2026
# sur BTCUSDT 1m : médiane 0,093, p93 0,195 -> le seuil 65 correspond au top ~7%).
CONF_SCALE = 77.0
TF_WEIGHTS = {"1m": 0.20, "5m": 0.35, "15m": 0.45}


def _clamp(x, lo=-1.0, hi=1.0):
    return max(lo, min(hi, x))


def tf_score(bars):
    """Score directionnel −1..+1 du dernier instant, pour une série de barres."""
    if len(bars) < 40:
        return 0.0
    closes = [b[4] for b in bars]
    r = rsi(closes, 14)[-1]
    m_line, m_sig, m_hist = macd(closes)
    a = atr(bars, 14)[-1] or 1e-9
    hist = m_hist[-1] / a
    e9, e21 = ema(closes, 9)[-1], ema(closes, 21)[-1]
    cross = (e9 - e21) / a
    mid, up, lo = bollinger(closes, 20)
    bpos = (closes[-1] - mid[-1]) / ((up[-1] - lo[-1]) or 1e-9)  # 0..1
    k, d = stochastic(bars, 14, 3)
    st = (k[-1] - d[-1]) / 20.0
    volz = zscore([b[5] for b in bars], 20)[-1]
    roc = (closes[-1] / closes[-6] - 1) if len(closes) > 6 and closes[-6] else 0.0

    # composantes (chaque −1..+1)
    s_rsi = _clamp((r - 50) / 20) if r < 70 else _clamp(-(r - 70) / 20)  # surchauffe = frein
    s_macd = _clamp(hist / 1.5)
    s_ema = _clamp(cross / 1.2)
    # Bollinger : momentum quand on remonte depuis la bande basse, frein en bande haute
    s_boll = _clamp((0.5 - bpos) * 1.6)
    s_st = _clamp(st)
    s_mom = _clamp(roc / 0.004)
    score = (0.22 * s_rsi + 0.24 * s_macd + 0.20 * s_ema + 0.10 * s_boll
             + 0.12 * s_st + 0.12 * s_mom)
    # le volume soutient la conviction mais ne crée pas la direction
    score *= (0.7 + 0.3 * min(1.0, abs(volz)))
    return _clamp(score)


def signal_at(bars_1m, i):
    """Signal à la barre 1m d'index i (utilise uniquement les données <= i).

    Retourne dict(conf 0-97, side 'BUY'/'SELL'/'HOLD', tf_scores) ou None si
    pas assez d'historique. Le 15m nécessite ~300 barres 1m, le 5m ~100.
    """
    if i < 320:
        return None
    w1 = bars_1m[max(0, i - 199): i + 1]
    w5 = resample(bars_1m[max(0, i - 199): i + 1], 5)
    w15 = resample(bars_1m[max(0, i - 449): i + 1], 15)
    s = {"1m": tf_score(w1), "5m": tf_score(w5), "15m": tf_score(w15)}
    agg = sum(s[tf] * TF_WEIGHTS[tf] for tf in TF_WEIGHTS)
    conf = min(97.0, 50 + CONF_SCALE * abs(agg))
    side = "BUY" if agg > 0 else "SELL"
    return {"conf": conf, "side": side if conf >= MIN_CONF else "HOLD",
            "raw_side": side, "agg": agg, "tf": s}
