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

# Bot RÉEL Binance (ordres signés, depuis ta machine)
export BINANCE_API_KEY="..."
export BINANCE_API_SECRET="..."
python3 -m orionbot.cli run BTCUSDT --profile balance --real

# Bot RÉEL OKX
export OKX_API_KEY="..."
export OKX_API_SECRET="..."
export OKX_API_PASSPHRASE="..."
python3 -m orionbot.cli run BTCUSDT --profile balance --real --exchange okx

# Campagne d'optimisation (recherche sur 2/3, validation hors échantillon sur 1/3)
python3 -c "from orionbot import optimize; optimize.campaign(days=60)"
```

## Les 2 courtiers

* **Binance** : spot, ordres signés HMAC (`/api/v3/order`). Le serveur de Mugogo est geo-bloqué (HTTP 451) : le réel Binance passe uniquement depuis sa machine.
* **OKX** (`okx.py`) : spot « cash », API v5 signée (OK-ACCESS-KEY/SIGN/TIMESTAMP/PASSPHRASE), accessible serveur ET machine. Clés : OKX -> API -> permission « Trade ».

Les deux courtiers partagent le même moteur de signaux et le même backtester.

## Les 4 profils (identiques à Penifx)

| Profil   | Trades/série | Paliers martingale | Multiplicateur | Mise min |
|----------|--------------|--------------------|----------------|----------|
| Beginner | 2            | 3                  | ×2,3           | 5 USDT   |
| Balance  | 3            | 4                  | ×2,4           | 5 USDT   |
| Pro      | 4            | 5                  | ×2,5           | 5 USDT   |
| Expert   | 5            | 6                  | ×2,6           | 5 USDT   |

## Résultats de la campagne d'optimisation (60 jours réels BTCUSDT 1m)

Méthode honnête : recherche sur 40 jours (train), jugement final sur 20 jours
jamais vus (test). Frais 0,10 %/côté partout.

*Configurations gagnantes (train → test hors échantillon)*
trend_hold + TP 3% / SL 1,5% + martingale : +11,31 → *+3,03* (53% wr)
momentum + TP 4% / SL 2% + martingale : +9,63 → *+1,58* (62% wr)

*Ce que la campagne a démontré*
1. Toutes les variantes à horizon court (expiration fixe, TP < 1,5%) perdent : les frais 0,2% aller-retour dépassent le mouvement typique de BTC
2. Seules les cibles larges (TP 3-4%) alignées sur la tendance 15m survivent, en train ET en test
3. La martingale aggrave toutes les variantes court-espaçées ; elle n'aide que les rares configurations à forte winrate

*Avertissements*
Le buy-and-hold a fait +13,4% sur la même fenêtre de test : le bot protège mieux
le capital en marché baissier mais ne bat pas un marché haussier à ce stade.
Échantillons faibles (8-15 trades en test) : le mode optimal est livré en PAPIER
par défaut ; ne passe en réel qu'après validation continue.

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

## Mode optimal (par défaut du `run`)

`--mode optimal` : entrée trend_hold (score 15m > percentile 75 des 48 dernières
heures, RSI 1m < 62), sortie TP +3% / SL -1,5%, martingale ×2,6 max 6 paliers,
limite journalière -15% avec pause. C'est la configuration validée ci-dessus.
`--mode penifx` conserve la mécanique d'origine (conf ≥ 65, expiration fixe).

## Licence

Usage personnel. Aucun conseil financier. Tu restes seul responsable de tes ordres.
