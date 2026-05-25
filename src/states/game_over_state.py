# =============================================================================
# states/game_over_state.py
# Final screen for both victory and defeat.
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import C, SCREEN_W, SCREEN_H, BAL
from src.fonts import get_font, FS_TITLE, FS_HEADING, FS_BODY, FS_LABEL, FS_SMALL
from src.models.player import PlayerState
from src.states.base_state import BaseState
from src.systems.progression import ProgressionSystem
from src.ui.components.button import Button


class GameOverState(BaseState):

    def __init__(self, progression: ProgressionSystem) -> None:
        super().__init__()
        self._prog    = progression
        self._player: PlayerState | None = None
        self._victory: bool = False

        self._f_huge    = get_font(FS_TITLE, bold=True)
        self._f_heading = get_font(FS_HEADING, bold=True)
        self._f_body    = get_font(FS_BODY)
        self._f_small   = get_font(FS_SMALL)

        bw = 220
        bx = SCREEN_W // 2 - bw // 2

        self._menu_btn = Button(
            rect=(bx, SCREEN_H - 100, bw, 44),
            text="Return to Menu",
            on_click=self._to_menu,
            colour=C["btn"],
            hover_colour=C["btn_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=8,
        )

    def on_enter(self, data: dict) -> None:
        self._player  = data.get("player")
        self._victory = data.get("victory", False)

    def handle_event(self, event: pygame.event.Event) -> None:
        self._menu_btn.handle_event(event)

    def update(self, dt: float) -> None:
        pass

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(C["bg_night"] if not self._victory else C["bg"])

        cx = SCREEN_W // 2
        y  = SCREEN_H // 5

        if self._victory:
            title = "YOU SURVIVED"
            col   = C["ltm"]
        else:
            title = "YOUR JOURNEY ENDS"
            col   = C["health_low"]

        ts = self._f_huge.render(title, True, col)
        surface.blit(ts, (cx - ts.get_width() // 2, y))
        y += ts.get_height() + 20

        if self._player:
            score = self._prog.score(self._player)
            ss    = self._f_heading.render(f"Score: {score:,}", True, C["text"])
            surface.blit(ss, (cx - ss.get_width() // 2, y))
            y += ss.get_height() + 14

            rows = [
                ("Nights survived",    str(self._player.current_night)),
                ("Memories encoded",   str(self._player.memories_encoded)),
                ("Merges performed",   str(self._player.merges_performed)),
                ("False memories",     str(self._player.false_memories_formed)),
                ("Long-term memories", str(len(self._player.long_term))),
            ]
            for label, val in rows:
                ls = self._f_body.render(f"{label}:  {val}", True, C["text_dim"])
                surface.blit(ls, (cx - ls.get_width() // 2, y))
                y += ls.get_height() + 6

            y += 14
            # Educational takeaway
            edu_lines = self._education_lines()
            for line in edu_lines:
                es = self._f_small.render(line, True, C["text_dim"])
                surface.blit(es, (cx - es.get_width() // 2, y))
                y += es.get_height() + 3

        self._menu_btn.render(surface)

    def _education_lines(self) -> list[str]:
        """Return contextual neuroscience takeaway lines based on run stats."""
        lines = []
        if not self._player:
            return lines

        ltm = len(self._player.long_term)
        false = self._player.false_memories_formed
        merges = self._player.merges_performed

        if false > 3:
            lines += [
                "Science note: False memories arise when similar",
                "memory traces are over-merged during reconsolidation.",
            ]
        elif merges > 5:
            lines += [
                "Science note: Memory merging mirrors schema formation —",
                "the brain integrates related experiences into general knowledge.",
            ]
        elif ltm >= 8:
            lines += [
                "Science note: Long-term memories are held in distributed",
                "neocortical networks, not a single brain region.",
            ]
        else:
            lines += [
                "Science note: Miller's Law — working memory holds ~7 items.",
                "Sleep consolidation moves the most important ones to long-term storage.",
            ]
        return lines

    def _to_menu(self) -> None:
        self._goto("menu", {})
