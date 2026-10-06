"""Backtest honnête : frais réels, martingale, limite journalière, sans lookahead.

Mécanique Penifx appliquée au vrai marché :
  - le moteur ne voit que les barres <= t (aucune fuite de futur) ;
  - BUY au marché (spot = pas de short ; les SELL sont comptés en journal) ;
  - position tenue `expiry` barres puis vendue au marché ;
  - P&L = mouvement réel - frais (0,1 % par côté) ;
  - perte -> mise suivante x multiplicateur (jusqu'à max_steps paliers) ;
  - limite de perte journalière -> pause automatique.
"""
import time
from .engine import signal_at, MIN_CONF
from .risk import Risk


def run_backtest(bars, profile, capital=1000.0, stake=10.0, expiry=5,
                 fee_pct=0.10, daily_loss_pct=15.0, verbose=False):
    p = profile
    risk = Risk(daily_loss_pct=daily_loss_pct)
    equity = capital
    step = 0               # palier martingale en cours
    cur_stake = stake
    trades = []
    signals_logged = sells = 0
    open_trade = None
    peak = equity
    max_dd = 0.0
    streak = max_streak = 0

    for i in range(len(bars)):
        t, px = bars[i][0], bars[i][4]

        # clôture à l'échéance (prix de la barre courante)
        if open_trade and i >= open_trade["exit_i"]:
            exit_px = px * (1 - fee_pct / 100.0)
            pnl = open_trade["stake"] * (exit_px / open_trade["entry"] - 1.0)
            equity += pnl
            win = pnl > 0
            trades.append({**open_trade, "exit": exit_px, "pnl": pnl,
                           "win": win, "step": open_trade["step"]})
            if win:
                step, cur_stake = 0, stake
                streak = 0
            else:
                streak += 1
                max_streak = max(max_streak, streak)
                step += 1
                if step >= p["steps"]:
                    risk.hit_streak(i)          # série maximale -> pause
                    step, cur_stake = 0, stake
                else:
                    cur_stake = cur_stake * p["martingale"]
            peak = max(peak, equity)
            max_dd = max(max_dd, (peak - equity) / peak * 100 if peak > 0 else 0)
            open_trade = None

        # nouvelle entrée
        if open_trade is None and i > risk.paused_until and risk.gate(t, equity):
            sig = signal_at(bars, i)
            if sig:
                if sig["side"] == "SELL":
                    sells += 1
                    signals_logged += 1
                elif sig["side"] == "BUY":
                    if step == 0 or trades:    # martingale : on enchaîne direct
                        pass
                    stake_i = risk.cap_stake(cur_stake, equity)
                    if stake_i >= p["min_amount"]:
                        entry = px * (1 + fee_pct / 100.0)
                        open_trade = {"t": t, "sym": "SPOT", "entry": entry,
                                      "stake": stake_i, "exit_i": i + expiry,
                                      "step": step}
                        signals_logged += 1

    if open_trade:  # position restée ouverte à la fin des données
        exit_px = bars[-1][4] * (1 - fee_pct / 100.0)
        pnl = open_trade["stake"] * (exit_px / open_trade["entry"] - 1.0)
        equity += pnl
        trades.append({**open_trade, "exit": exit_px, "pnl": pnl,
                       "win": pnl > 0, "step": open_trade["step"]})

    wins = [t for t in trades if t["win"]]
    gross_win = sum(t["pnl"] for t in wins)
    gross_loss = abs(sum(t["pnl"] for t in trades if not t["win"]))
    fees_paid = sum(t["stake"] * fee_pct / 100.0 * 2 for t in trades)
    return {
        "profile": p["name"], "trades": len(trades), "wins": len(wins),
        "winrate": (100.0 * len(wins) / len(trades)) if trades else 0.0,
        "net_pnl": equity - capital, "equity": equity,
        "return_pct": (equity / capital - 1) * 100,
        "gross_win": gross_win, "gross_loss": gross_loss,
        "profit_factor": (gross_win / gross_loss) if gross_loss else float("inf"),
        "fees": fees_paid,
        "max_drawdown_pct": max_dd, "max_loss_streak": max_streak,
        "max_stake_used": max((t["stake"] for t in trades), default=0),
        "ruin": equity <= capital * 0.25,
        "sell_signals_skipped": sells, "signals": signals_logged,
        "trade_log": trades,
    }


def report(r):
    print()
    print("=== %s ===" % r["profile"])
    print("trades          : %d  (gagnants %d, winrate %.1f%%)"
          % (r["trades"], r["wins"], r["winrate"]))
    print("P&L net         : %+.2f USDT  (%+.2f%%)" % (r["net_pnl"], r["return_pct"]))
    print("profit factor   : %.2f" % r["profit_factor"])
    print("frais payés     : %.2f USDT" % r["fees"])
    print("drawdown max    : %.1f%%" % r["max_drawdown_pct"])
    print("série de pertes : max %d" % r["max_loss_streak"])
    print("plus grosse mise: %.2f USDT" % r["max_stake_used"])
    print("signals SELL    : %d (spot : pas tradés)" % r["sell_signals_skipped"])
    verdict = ("RUINE (-75%%+)" if r["ruin"] else
               ("PERDANT" if r["net_pnl"] < 0 else "GAGNANT"))
    print("verdict         : %s" % verdict)
    return verdict
