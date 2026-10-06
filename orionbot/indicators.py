"""Indicateurs techniques en pur Python (aucune dépendance)."""


def ema(vals, period):
    out = []
    k = 2.0 / (period + 1)
    for i, v in enumerate(vals):
        out.append(v if i == 0 else v * k + out[-1] * (1 - k))
    return out


def rsi(closes, period=14):
    out = []
    gains = losses = 0.0
    for i, c in enumerate(closes):
        if i == 0:
            out.append(50.0)
            continue
        d = c - closes[i - 1]
        g, l = max(d, 0.0), max(-d, 0.0)
        if i <= period:
            gains += g
            losses += l
            if i == period:
                gains /= period
                losses /= period
        else:
            gains = (gains * (period - 1) + g) / period
            losses = (losses * (period - 1) + l) / period
        out.append(100.0 if losses == 0 else 100 - 100 / (1 + gains / losses))
    return out


def macd(closes, fast=12, slow=26, sig=9):
    ef, es = ema(closes, fast), ema(closes, slow)
    line = [a - b for a, b in zip(ef, es)]
    signal = ema(line, sig)
    return line, signal, [a - b for a, b in zip(line, signal)]


def atr(bars, period=14):
    out = []
    trs = []
    for i, b in enumerate(bars):
        if i == 0:
            trs.append(b[2] - b[3])
        else:
            pc = bars[i - 1][4]
            trs.append(max(b[2] - b[3], abs(b[2] - pc), abs(b[3] - pc)))
        if i < period:
            out.append(sum(trs) / (i + 1))
        else:
            out.append((out[-1] * (period - 1) + trs[-1]) / period)
    return out


def bollinger(closes, period=20, nb=2.0):
    mids, upps, lows = [], [], []
    for i in range(len(closes)):
        w = closes[max(0, i - period + 1): i + 1]
        m = sum(w) / len(w)
        var = sum((c - m) ** 2 for c in w) / len(w)
        sd = var ** 0.5
        mids.append(m)
        upps.append(m + nb * sd)
        lows.append(m - nb * sd)
    return mids, upps, lows


def stochastic(bars, period=14, smooth=3):
    k, d = [], []
    ks = []
    for i in range(len(bars)):
        w = bars[max(0, i - period + 1): i + 1]
        hi, lo = max(b[2] for b in w), min(b[3] for b in w)
        c = bars[i][4]
        kk = 50.0 if hi == lo else (c - lo) / (hi - lo) * 100
        ks.append(kk)
        k.append(kk)
        d.append(sum(ks[-smooth:]) / min(smooth, len(ks)))
    return k, d


def zscore(vals, period=20):
    out = []
    for i in range(len(vals)):
        w = vals[max(0, i - period + 1): i + 1]
        m = sum(w) / len(w)
        sd = (sum((v - m) ** 2 for v in w) / len(w)) ** 0.5 or 1e-12
        out.append((vals[i] - m) / sd)
    return out
