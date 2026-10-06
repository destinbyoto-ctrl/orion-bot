"""Récupération de klines : Binance en priorité, fallback OKX si geo-bloqué (451).
Cache CSV local pour ne pas re-télécharger."""
import csv, json, os, time, urllib.request

CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cache")
os.makedirs(CACHE, exist_ok=True)

# intervalle minutes -> (binance, okx)
IV = {"1m": ("1m", "1m"), "3m": ("3m", "3m"), "5m": ("5m", "5m"),
      "15m": ("15m", "15m"), "30m": ("30m", "30m"), "1h": ("1h", "1Hutc")}


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "orionbot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _okx_symbol(sym):
    if "-" in sym:
        return sym.upper()
    # BTCUSDT -> BTC-USDT
    for q in ("USDT", "USDC", "BTC", "USD"):
        if sym.upper().endswith(q):
            return sym.upper()[: -len(q)] + "-" + q
    return sym


def _binance_klines(sym, iv, total):
    url = ("https://api.binance.com/api/v3/klines?symbol=%s&interval=%s&limit=1000"
           % (sym.upper(), iv))
    rows = _get(url)
    return [[r[0], float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])]
            for r in rows]


def _okx_klines(sym, iv, total, minutes):
    """OKX limite à 100/300 par requête : on pagine vers le passé."""
    inst = _okx_symbol(sym)
    out, after = [], None
    # /market/history-candles accepte 100 par page et un curseur 'after' (plus vieux)
    while len(out) < total:
        url = ("https://www.okx.com/api/v5/market/history-candles?instId=%s&bar=%s&limit=100"
               % (inst, iv))
        if after:
            url += "&after=" + str(after)
        resp = _get(url)
        if resp.get("code") != "0":
            break
        rows = resp.get("data") or []
        if not rows:
            break
        for r in rows:  # [ts,o,h,l,c,vol,...]
            out.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                        float(r[4]), float(r[5])])
        after = rows[-1][0]
        time.sleep(0.12)
    out.sort(key=lambda b: b[0])
    return out


def klines(symbol="BTCUSDT", interval="1m", days=7, source="auto", refresh=False):
    """Retourne une liste de barres [t_ms, o, h, l, c, v], la plus ancienne d'abord."""
    key = "%s_%s_%dd" % (symbol.upper(), interval, days)
    path = os.path.join(CACHE, key + ".csv")
    if os.path.exists(path) and not refresh:
        with open(path) as f:
            return [[int(r[0]), float(r[1]), float(r[2]), float(r[3]),
                     float(r[4]), float(r[5])] for r in csv.reader(f)]
    bn_iv, okx_iv = IV[interval]
    total = int(days * 1440 / {"1m": 1, "3m": 3, "5m": 5, "15m": 15,
                               "30m": 30, "1h": 60}[interval]) + 5
    bars = []
    if source in ("auto", "binance"):
        try:
            bars = _binance_klines(symbol, bn_iv, total)
            src = "binance"
        except Exception:
            bars = []
    if not bars or len(bars) < 100:
        bars = _okx_klines(symbol, okx_iv, total, interval)
        src = "okx"
    with open(path, "w", newline="") as f:
        csv.writer(f).writerows(bars)
    print("[data] %d barres %s (%s)" % (len(bars), interval, src))
    return bars


def resample(bars, factor):
    """Regroupe des barres 1m en barres de `factor` minutes."""
    out = []
    for i in range(0, len(bars) - factor + 1, factor):
        w = bars[i:i + factor]
        out.append([w[0][0], w[0][1], max(b[2] for b in w),
                    min(b[3] for b in w), w[-1][4], sum(b[5] for b in w)])
    return out
