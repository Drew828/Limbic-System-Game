# =============================================================================
# systems/progression.py
# Night progression, phase tracking, difficulty scaling, and win/loss logic.
# =============================================================================

from __future__ import annotations
from src.models.player import PlayerState
from src.constants import BAL, PHASE_CONFIG


class ProgressionSystem:
    """
    Stateless service — all methods receive the player explicitly.
    Tracks which game phase the player is in, applies end-of-night transitions,
    and determines win/loss conditions.
    """

    def __init__(self) -> None:
        pass

    # -----------------------------------------------------------------------
    # Phase queries
    # -----------------------------------------------------------------------

    def current_phase(self, player: PlayerState) -> str:
        night = player.current_night
        for phase_id, cfg in PHASE_CONFIG.items():
            lo, hi = cfg["nights"]
            if lo <= night <= hi:
                return phase_id
        return "late2"

    def phase_label(self, player: PlayerState) -> str:
        return PHASE_CONFIG[self.current_phase(player)]["label"]

    def phase_colour(self, player: PlayerState) -> tuple[int, int, int]:
        return PHASE_CONFIG[self.current_phase(player)]["colour"]

    def context_rules_visible(self, player: PlayerState) -> bool:
        """Whether context rules are shown in the Journal this phase."""
        return self.current_phase(player) in ("mid2", "late1", "late2")

    def max_cues_shown(self, player: PlayerState) -> int:
        """How many event cues are shown per event (increases with phase)."""
        return {"early": 2, "mid1": 3, "mid2": 4, "late1": 5, "late2": 6}[
            self.current_phase(player)]

    # -----------------------------------------------------------------------
    # Difficulty scaling helpers
    # -----------------------------------------------------------------------

    def stm_capacity(self, player: PlayerState) -> int:
        """STM capacity may be reduced temporarily in late phases."""
        base = BAL["stm_capacity"]
        if self.current_phase(player) == "late1":
            return base - 1
        return base

    def consolidation_slots(self, player: PlayerState) -> int:
        return BAL["consolidation_slots"]

    def decay_rate(self, player: PlayerState) -> float:
        """Nightly decay increases in later phases."""
        base = BAL["memory_decay_per_night"]
        modifiers = {
            "early":  0.8,
            "mid1":   0.9,
            "mid2":   1.0,
            "late1":  1.15,
            "late2":  1.10,
        }
        return base * modifiers.get(self.current_phase(player), 1.0)

    # -----------------------------------------------------------------------
    # Night transition
    # -----------------------------------------------------------------------

    def advance_night(self, player: PlayerState) -> None:
        """Call at the END of the travel phase, before the next day begins."""
        player.current_night += 1
        player.current_day_event = 0

        if player.current_night > BAL["total_nights"]:
            player.victory   = True
            player.game_over = False

    def reset(self, player: PlayerState) -> None:
        """Called when starting or loading a game."""
        pass  # Player state is the source of truth; nothing to reset here.

    # -----------------------------------------------------------------------
    # Win / Loss
    # -----------------------------------------------------------------------

    def check_game_over(self, player: PlayerState) -> bool:
        return player.health <= 0

    def check_victory(self, player: PlayerState) -> bool:
        return player.victory

    def score(self, player: PlayerState) -> int:
        """
        Final score: weighted sum of health, LTM count, mastery levels,
        and correct memories formed.
        """
        health_score   = player.health * 2
        ltm_score      = len(player.long_term) * 10
        mastery_score  = sum(m.mastery_level.value * 5 for m in player.long_term)
        false_penalty  = player.false_memories_formed * -15
        merge_bonus    = player.merges_performed * 8
        return max(0, health_score + ltm_score + mastery_score +
                   false_penalty + merge_bonus)

    def progress_fraction(self, player: PlayerState) -> float:
        """0.0 at start, 1.0 at end of night 15."""
        return min(1.0, (player.current_night - 1) / BAL["total_nights"])

    def night_label(self, player: PlayerState) -> str:
        return f"Night {player.current_night} / {BAL['total_nights']}"
