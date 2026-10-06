"""Exécution réelle Binance (ordres signés HMAC) + mode papier temps réel."""
import hashlib, hmac, json, os, time, urllib.parse, urllib.request
from .engine import signal_at
from .risk import Risk
from .data import klines, resample


def _signed(path, params, key, secret, method="POST", base="https://api.binance.com"):
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


def run(symbol="BTCUSDT", profile=None, stake=10.0, expiry_min=5, real=False,
        fee_pct=0.10):
    """Boucle temps réel. Papier par défaut ; réel seulement avec les clés + --real."""
    key = os.environ.get("BINANCE_API_KEY", "")
    secret = os.environ.get("BINANCE_API_SECRET", "")
    real = real and key and secret
    print("[bot] mode %s · %s · mise %.2f USDT · expiration %d min"
          % ("RÉEL 🔴" if real else "papier", profile["name"], stake, expiry_min))
    risk = Risk()
    equity = 1000.0
    if real:
        acc = account(key, secret)
        usdt = next((float(b["free"]) for b in acc.get("balances", [])
                     if b["asset"] == "USDT"), 0.0)
        equity = usdt
        print("[bot] solde réel : %.2f USDT" % equity)
    step, cur_stake, hold_until, pos = 0, stake, None, None
    log = []
    while True:
        try:
            bars = klines(symbol, "1m", days=2, refresh=True)
            if len(bars) < 330:
                time.sleep(60)
                continue
            i = len(bars) - 1
            t, px = bars[i][0], bars[i][4]
            # clôture à l'échéance
            if pos and t >= pos["hold_until"]:
                pnl = pos["stake"] * (px / pos["entry"] - 1) - pos["stake"] * fee_pct / 100 * 2
                if real:
                    try:
                        o = market_sell(symbol, pos["qty"], key, secret)
                        print("[bot] vente réelle :", o.get("executedQty"))
                    except Exception as e:
                        print("[bot] ERREUR vente réelle :", e)
                equity += pnl
                log.append((t, pnl, pos["step"]))
                print("[bot] clôturé %+.2f USDT (palier %d) · équité %.2f"
                      % (pnl, pos["step"], equity))
                if pnl > 0:
                    step, cur_stake = 0, stake
                else:
                    step += 1
                    if step >= profile["steps"]:
                        print("[bot] série max : pause 30 min")
                        step, cur_stake = 0, stake
                        time.sleep(1800)
                    else:
                        cur_stake *= profile["martingale"]
                pos = None
            # entrée
            if pos is None and risk.gate(t, equity):
                sig = signal_at(bars, i)
                if sig and sig["side"] == "BUY":
                    s = risk.cap_stake(cur_stake, equity)
                    if s >= profile["min_amount"]:
                        entry = px * (1 + fee_pct / 100)
                        pos = {"entry": entry, "stake": s, "step": step,
                               "hold_until": t + expiry_min * 60000,
                               "qty": s / px}
                        if real:
                            try:
                                o = market_buy(symbol, s, key, secret)
                                print("[bot] achat réel :", o.get("cummulativeQuoteQty"))
                            except Exception as e:
                                print("[bot] ERREUR achat réel :", e)
                                pos = None
                        if pos:
                            print("[bot] BUY conf %.0f%% · mise %.2f · palier %d"
                                  % (sig["conf"], s, step))
                elif sig and sig["side"] == "SELL":
                    print("[bot] signal SELL %.0f%% (spot : ignoré)" % sig["conf"])
            time.sleep(30)
        except KeyboardInterrupt:
            print("\n[bot] arrêt.")
            return
        except Exception as e:
            print("[bot] erreur :", e)
            time.sleep(30)
