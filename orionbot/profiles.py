"""Profils de stratégie — mêmes réglages que les 4 bots Penifx."""
PROFILES = {
    "beginner": {"name": "Beginner", "trades": 2, "steps": 3, "min_amount": 5,
                 "martingale": 2.3, "risk_tag": "Low"},
    "balance":  {"name": "Balance", "trades": 3, "steps": 4, "min_amount": 5,
                 "martingale": 2.4, "risk_tag": "Mid"},
    "pro":      {"name": "Pro", "trades": 4, "steps": 5, "min_amount": 5,
                 "martingale": 2.5, "risk_tag": "High"},
    "expert":   {"name": "Expert", "trades": 5, "steps": 6, "min_amount": 5,
                 "martingale": 2.6, "risk_tag": "Extreme"},
}


def get(profile):
    p = PROFILES.get(profile)
    if not p:
        raise SystemExit("Profil inconnu : %s (choisir parmi %s)"
                         % (profile, ", ".join(PROFILES)))
    return p
