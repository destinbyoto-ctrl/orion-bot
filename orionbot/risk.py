"""Garde-fous : limite de perte journalière, cap de mise, pause auto."""


class Risk:
    def __init__(self, daily_loss_pct=15.0, max_stake_pct=25.0, cooldown_after_streak=10):
        self.daily_loss_pct = daily_loss_pct      # pause si perte jour >= X%
        self.max_stake_pct = max_stake_pct        # mise max d'un trade : X% du capital
        self.cooldown = cooldown_after_streak    # barres de pause après série max
        self.day_start_equity = None
        self.day = None
        self.paused_until = 0

    def gate(self, t_ms, equity):
        """True si le trading est autorisé à l'instant t."""
        day = t_ms // 86400000
        if self.day != day:
            self.day, self.day_start_equity = day, equity
        if equity <= 0:
            return False
        if self.day_start_equity and \
           (self.day_start_equity - equity) / self.day_start_equity * 100 >= self.daily_loss_pct:
            return False           # limite journalière touchée -> pause jusqu'au lendemain
        return True

    def cap_stake(self, stake, equity):
        return max(0.0, min(stake, equity * self.max_stake_pct / 100.0))

    def hit_streak(self, bar_idx):
        """Série de pertes maximale atteinte : pause de `cooldown` barres."""
        self.paused_until = bar_idx + self.cooldown
