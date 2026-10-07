"""Exécution réelle Binance/OKX (ordres signés HMAC) + mode papier temps réel.

Deux modes :
  - "penifx"  : mécanique Penifx d'origine (momentum conf>=65, expiration fixe).
  - "optimal" : configuration validée par la campagne 60 jours (optimize.py) —
                entrée trend_hold (tf15 > percentile 75, RSI 1m < 62),
                TP +3 % / SL -1,5 %, martingale x2,6 max 6 paliers, pause auto.
                Gagnante sur le train (+11,31 USDT) ET hors échantillon (+3,03).
"""
import os, time
from .engine import signal_at
from .indicators import rsi
from .risk import Risk
from .data import klines


def _signed(path, params, key, secret, method="POST", base="https://api.binance.com"):
    import hashlib, hmac, json, urllib.parse, urllib.request
    params = dict(params)
    params["timestamp"] = int(time.time() * 1000)
    params["recvWindow"] = 8000
    qs = urllib.parse.urlencode(params)
    sig = hmac.new(secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
    url = base + path + "?" + qs + "&signature=" + sig
    req = urllib.request.Request(url, method=method,
                                 headers={"X-MBX-APIKEY": key})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def market_buy(symbol, quote_qty, key, secret):
    return _signed("/api/v3/order",
                   {"symbol": symbol, "side": "BUY", "type": "MARKET",
                    "quoteOrderQty": round(quote_qty, 2)}, key, secret)


def market_sell(symbol, qty, key, secret):
    return _signed("/api/v3/order",
                   {"symbol": symbol, "side": "SELL", "type": "MARKET",
                    "quantity": qty}, key, secret)


def account(key, secret):
    return _signed("/api/v3/account", {}, key, secret, method="GET")


def _p75_tf15(bars):
    """Percentile 75 du score 15m sur l'historique disponible (aucun futur)."""
    vals = []
    for i in range(920, len(bars), 15):
        s = signal_at(bars, i)
        vals.append(s["tf"]["15m"])
    vals.sort()
    return vals[int(len(vals) * 0.75)]


def _buy(exchange, symbol, s, broker, key, secret):
    if exchange == "okx":
        return broker.market_buy(symbol, s)
    return market_buy(symbol, s, key, secret)


def _sell(exchange, symbol, qty, broker, key, secret):
    if exchange == "okx":
        return broker.market_sell(symbol, qty)
    return market_sell(symbol, qty, key, secret)


def run(symbol="BTCUSDT", profile=None, stake=10.0, expiry_min=5, real=False,
        fee_pct=0.10, exchange="binance", mode="optimal"):
    key = os.environ.get("BINANCE_API_KEY", "")
    secret = os.environ.get("BINANCE_API_SECRET", "")
    broker = None
    if exchange == "okx":
        from . import okx as broker
        real = real and all(os.environ.get(v) for v in
                            ("OKX_API_KEY", "OKX_API_SECRET", "OKX_API_PASSPHRASE"))
    else:
        real = real and key and secret

    tp_pct, sl_pct = (0.03, 0.015) if mode == "optimal" else (None, None)
    print("[bot] mode %s · courtier %s · réel=%s · mise %.2f USDT"
          % (mode, exchange, "OUI 🔴" if real else "non (papier)", stake))
    if profile:
        print("[bot] profil %s · martingale ×%.1f (max %d paliers)"
              % (profile["name"], profile["martingale"], profile["steps"]))

    risk = Risk()
    equity, day_eq, day = 1000.0, None, None
    if real:
        try:
            equity = broker.usdt_balance() if exchange == "okx" else \
                next((float(b["free"]) for b in account(key, secret)["balances"]
                      if b["asset"] == "USDT"), 0.0)
            print("[bot] solde réel : %.2f USDT" % equity)
        except Exception as e:
            print("[bot] ERREUR solde réel :", e)
            return

    step, cur, pos = 0, stake, None
    mart_mult = profile["martingale"] if profile else 2.6
    mart_steps = profile["steps"] if profile else 6
    thr15 = None

    while True:
        try:
            bars = klines(symbol, "1m", days=2, refresh=True)
            if len(bars) < 1000:
                time.sleep(60)
                continue
            if thr15 is None:
                thr15 = _p75_tf15(bars)
                print("[bot] seuil tf15 (p75) : %.3f" % thr15)
            i = len(bars) - 1
            t, px = bars[i][0], bars[i][4]

            d = t // 86400000
            if d != day:
                day, day_eq = d, equity
            if day_eq and (day_eq - equity) / day_eq * 100 >= 15:
                print("[bot] limite journalière -15%% touchée : pause jusqu'à demain")
                while t // 86400000 == day:
                    time.sleep(300)
                continue

            # ---- clôtures ----
            if pos:
                hit = None
                if mode == "optimal":
                    if px >= pos["tp"]:
                        hit = "TP"
                    elif px <= pos["stop"]:
                        hit = "SL"
                else:  # penifx : expiration fixe
                    if t >= pos["hold_until"]:
                        hit = "EXPIRE"
                if hit:
                    exit_px = px * (1 - fee_pct / 100.0)
                    pnl = pos["stake"] * (exit_px / pos["entry"] - 1)
                    if real:
                        try:
                            _sell(exchange, symbol, pos["qty"], broker, key, secret)
                        except Exception as e:
                            print("[bot] ERREUR vente réelle :", e)
                    equity += pnl
                    print("[bot] clôturé %s %+.2f USDT (palier %d) · équité %.2f"
                          % (hit, pnl, pos["step"], equity))
                    if pnl > 0:
                        step, cur = 0, stake
                    else:
                        step += 1
                        if step >= mart_steps:
                            print("[bot] série max atteinte : pause 30 min")
                            step, cur = 0, stake
                            pos = None
                            time.sleep(1800)
                            continue
                        cur *= mart_mult
                    pos = None

            # ---- entrées ----
            if pos is None:
                sig = signal_at(bars, i)
                rs = rsi([b[4] for b in bars], 14)[-1]
                enter = False
                if mode == "optimal":
                    enter = sig["tf"]["15m"] > thr15 and rs < 62
                    why = "trend_hold (tf15 %.3f>%.3f, rsi %.0f<62)" % (
                        sig["tf"]["15m"], thr15, rs)
                else:
                    enter = sig["side"] == "BUY" and sig["conf"] >= 65
                    why = "momentum conf %.0f%%" % sig["conf"]
                if enter:
                    s = risk.cap_stake(cur, equity)
                    if s >= 5:
                        entry = px * (1 + fee_pct / 100.0)
                        pos = {"entry": entry, "stake": s, "step": step,
                               "qty": s / px}
                        if mode == "optimal":
                            pos["tp"] = entry * (1 + tp_pct)
                            pos["stop"] = entry * (1 - sl_pct)
                        else:
                            pos["hold_until"] = t + expiry_min * 60000
                        if real:
                            try:
                                _buy(exchange, symbol, s, broker, key, secret)
                            except Exception as e:
                                print("[bot] ERREUR achat réel :", e)
                                pos = None
                                continue
                        if pos:
                            print("[bot] BUY %s · mise %.2f · palier %d"
                                  % (why, s, step))
                elif sig["side"] == "SELL":
                    pass  # spot : signal journalisé seulement
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n[bot] arrêt.")
            return
        except Exception as e:
            print("[bot] erreur :", e)
            time.sleep(30)
