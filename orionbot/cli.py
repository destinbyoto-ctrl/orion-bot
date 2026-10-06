"""Ligne de commande OrionBot.

  python3 -m orionbot.cli backtest BTCUSDT --days 14 --profile expert
  python3 -m orionbot.cli backtest BTCUSDT --days 30 --all-profiles
  python3 -m orionbot.cli run BTCUSDT --profile balance [--real]
"""
import argparse, os, sys, time
from . import data, profiles, backtest as bt


def cmd_backtest(a):
    bars = data.klines(a.symbol, a.interval, a.days, refresh=a.refresh)
    print("[backtest] %s · %d barres · %d jours · expiration %d barres"
          % (a.symbol, len(bars), a.days, a.expiry))
    profs = list(profiles.PROFILES) if a.all_profiles else [a.profile]
    results = []
    for name in profs:
        r = bt.run_backtest(bars, profiles.get(name), capital=a.capital,
                            stake=a.stake, expiry=a.expiry)
        results.append(r)
        bt.report(r)
    if a.save:
        os.makedirs("backtests", exist_ok=True)
        path = os.path.join("backtests", "result_%s_%dd_%s.txt"
                            % (a.symbol, a.days, time.strftime("%Y%m%d_%H%M")))
        with open(path, "w") as f:
            f.write("OrionBot backtest · %s · %d barres %s · %d jours\n"
                    % (a.symbol, len(bars), a.interval, a.days))
            f.write("capital %.0f · mise %.2f · expiration %d barres · frais 0,10%%/côté\n\n"
                    % (a.capital, a.stake, a.expiry))
            for r in results:
                f.write("=== %s ===\n" % r["profile"])
                f.write("trades %d · winrate %.1f%% · P&L net %+.2f USDT (%+.2f%%)\n"
                        % (r["trades"], r["winrate"], r["net_pnl"], r["return_pct"]))
                f.write("profit factor %.2f · frais %.2f · drawdown max %.1f%% · série de pertes max %d\n"
                        % (r["profit_factor"], r["fees"], r["max_drawdown_pct"],
                           r["max_loss_streak"]))
                f.write("plus grosse mise %.2f · RUINE: %s\n\n"
                        % (r["max_stake_used"], "OUI" if r["ruin"] else "non"))
            for r in results:
                f.write("\n--- journal %s (50 derniers) ---\n" % r["profile"])
                for t in r["trade_log"][-50:]:
                    f.write("%s palier %d mise %.2f -> %+.2f %s\n"
                            % (time.strftime("%m-%d %H:%M", time.localtime(t["t"] / 1000)),
                               t["step"], t["stake"], t["pnl"],
                               "WIN" if t["win"] else "LOSS"))
        print("\nrapport : %s" % path)


def cmd_run(a):
    from . import trader
    trader.run(symbol=a.symbol, profile=profiles.get(a.profile),
               stake=a.stake, expiry_min=a.expiry, real=a.real)


def main():
    ap = argparse.ArgumentParser(prog="orionbot")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("backtest")
    b.add_argument("symbol", nargs="?", default="BTCUSDT")
    b.add_argument("--days", type=int, default=14)
    b.add_argument("--interval", default="1m")
    b.add_argument("--profile", default="expert", choices=list(profiles.PROFILES))
    b.add_argument("--all-profiles", action="store_true")
    b.add_argument("--capital", type=float, default=1000.0)
    b.add_argument("--stake", type=float, default=10.0)
    b.add_argument("--expiry", type=int, default=5, help="barres de détention")
    b.add_argument("--refresh", action="store_true")
    b.add_argument("--save", action="store_true")
    b.set_defaults(func=cmd_backtest)

    r = sub.add_parser("run")
    r.add_argument("symbol", nargs="?", default="BTCUSDT")
    r.add_argument("--profile", default="balance", choices=list(profiles.PROFILES))
    r.add_argument("--stake", type=float, default=10.0)
    r.add_argument("--expiry", type=int, default=5, help="minutes de détention")
    r.add_argument("--real", action="store_true")
    r.set_defaults(func=cmd_run)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
