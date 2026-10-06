# OrionBot — Bot IA Binance (mécanique Penifx) + Backtesting

Bot de trading Python qui réplique la **mécanique du robot Penifx** — analyse
multi-facteurs multi-timeframes, seuil de confiance ≥ 65 %, profils
Beginner/Balance/Pro/Expert avec martingale de récupération, limite de perte
journalière avec pause automatique — mais appliquée au **vrai marché Binance
spot** : ici, c'est le marché qui décide du résultat, pas un moteur interne.

## ⚠️ Avertissement honnête (lis ça d'abord)

Chez Penifx, le résultat est décidé par un moteur avec winrate cible (payout 92-94 %).
Sur Binance, le résultat est le vrai mouvement du prix, **moins les frais (0,1 % × 2 = 0,2 %
par aller-retour)**. La martingale multiplie la mise après chaque perte (jusqu'à ×2,6,
6 paliers) : sur une mauvaise série elle peut consommer tout le capital. Le module de
backtesting existe précisément pour mesurer ça *avant* de risquer de l'argent réel.

## Structure

```
orionbot/
  data.py        # klines Binance (avec fallback OKX), cache CSV
  indicators.py  # RSI, MACD, EMA, Bollinger, Stochastic, ATR, z-score volume
  engine.py      # moteur de signaux multi-timeframes (1m/5m/15m), confiance 0-100
  profiles.py    # Beginner/Balance/Pro/Expert (mêmes réglages que Penifx)
  risk.py        # limite de perte journalière, cap de mise, pause auto
  backtest.py    # backtest honnête : frais, martingale, drawdown, sans lookahead
  trader.py      # exécution réelle Binance (ordres signés HMAC) + mode papier
  cli.py         # ligne de commande
```

## Installation

Python 3.10+, aucune dépendance externe (100 % stdlib).

## Utilisation

```bash
# Backtest 14 jours de BTCUSDT en 1m, profil Expert
python3 -m orionbot.cli backtest BTCUSDT --days 14 --profile expert

# Tous les profils, 30 jours, écrit le rapport dans backtests/
python3 -m orionbot.cli backtest BTCUSDT --days 30 --all-profiles

# Bot papier (temps réel, données live, aucun ordre réel)
python3 -m orionbot.cli run BTCUSDT --profile balance

# Bot RÉEL (ordres signés Binance depuis ta machine)
export BINANCE_API_KEY="..."
export BINANCE_API_SECRET="..."
python3 -m orionbot.cli run BTCUSDT --profile balance --real
```

## Les 4 profils (identiques à Penifx)

| Profil   | Trades/série | Paliers martingale | Multiplicateur | Mise min |
|----------|--------------|--------------------|----------------|----------|
| Beginner | 2            | 3                  | ×2,3           | 5 USDT   |
| Balance  | 3            | 4                  | ×2,4           | 5 USDT   |
| Pro      | 4            | 5                  | ×2,5           | 5 USDT   |
| Expert   | 5            | 6                  | ×2,6           | 5 USDT   |

## Mécanique d'un trade

1. Le moteur analyse 1m + 5m + 15m (RSI, MACD, EMA, Bollinger, Stochastic,
   volume) → direction + confiance
2. Confiance ≥ 65 % → ordre BUY au marché (spot = pas de short : les signaux
   SELL sont journalisés, pas tradés)
3. Position tenue `expiry_min` minutes (défaut 5) puis vendue au marché
4. P&L = mouvement réel − frais. Gain → palier remis à zéro ; perte →
   prochaine mise × multiplicateur (jusqu'au cap et au max de paliers)
5. Limite de perte journalière (défaut −15 %) → pause automatique jusqu'au
   lendemain. Cap de mise : 25 % du capital par trade.

## Licence

Usage personnel. Aucun conseil financier. Tu restes seul responsable de tes ordres.
