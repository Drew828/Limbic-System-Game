# =============================================================================
# states/menu_state.py
# Title screen — New Game, Continue, Quit.
# =============================================================================

from __future__ import annotations
import math
import pygame
from src.constants import C, SCREEN_W, SCREEN_H
from src.fonts import get_font, FS_TITLE, FS_HEADING, FS_BODY, FS_LABEL, FS_SMALL
from src.states.base_state import BaseState
from src.systems.save_system import SaveSystem
from src.ui.components.button import Button

_SUBTITLE = (
    "Fifteen nights in the wild. Everything you remember shapes your survival.\n"
    "Encode, consolidate, and trust your instincts — or pay the price."
)


class MenuState(BaseState):

    def __init__(self, save_system: SaveSystem) -> None:
        super().__init__()
        self._save  = save_system
        self._time  = 0.0  # accumulated seconds for animations

        self._f_title   = get_font(FS_TITLE,    bold=True)
        self._f_heading = get_font(FS_HEADING, bold=True)
        self._f_body    = get_font(FS_BODY)
        self._f_small   = get_font(FS_SMALL)

        cy = SCREEN_H // 2 + 30
        bw = 260
        bx = SCREEN_W // 2 - bw // 2

        self._btn_new = Button(
            rect=(bx, cy, bw, 44),
            text="New Game",
            on_click=self._new_game,
            colour=C["btn_positive"],
            hover_colour=C["btn_positive_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=8,
        )
        self._btn_continue = Button(
            rect=(bx, cy + 54, bw, 44),
            text="Continue",
            on_click=self._continue_game,
            colour=C["btn"],
            hover_colour=C["btn_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=8,
            disabled=not self._save.has_save(0),
        )
        self._btn_quit = Button(
            rect=(bx, cy + 108, bw, 44),
            text="Quit",
            on_click=self._quit,
            colour=C["btn_danger"],
            hover_colour=C["btn_danger_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=8,
        )

    # -----------------------------------------------------------------------
    # Transitions
    # -----------------------------------------------------------------------

    def _new_game(self) -> None:
        self._goto("intro", {})

    def _continue_game(self) -> None:
        self._goto("day", {"load_slot": 0})

    def _quit(self) -> None:
        self._goto("quit", {})

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def on_enter(self, data: dict) -> None:
        # Refresh continue button availability on each visit
        self._btn_continue.disabled = not self._save.has_save(0)

    # -----------------------------------------------------------------------
    # BaseState interface
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        self._btn_new.handle_event(event)
        self._btn_continue.handle_event(event)
        self._btn_quit.handle_event(event)

    def update(self, dt: float) -> None:
        self._time += dt

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(C["bg"])

        # Animated starfield-style particles (simple sine drift)
        self._draw_particles(surface)

        # Title
        title_text = "LIMBIC JOURNEY"
        tw = 0
        # Subtle oscillation
        pulse = 1.0 + 0.015 * math.sin(self._time * 1.4)

        title_surf = self._f_title.render(title_text, True, C["ltm"])
        sw = int(title_surf.get_width() * pulse)
        sh = int(title_surf.get_height() * pulse)
        scaled = pygame.transform.smoothscale(title_surf, (sw, sh))
        tx = SCREEN_W // 2 - sw // 2
        ty = SCREEN_H // 4 - sh // 2
        surface.blit(scaled, (tx, ty))

        # Subtitle
        lines = _SUBTITLE.split("\n")
        sy    = ty + sh + 18
        for line in lines:
            ls = self._f_body.render(line, True, C["text_dim"])
            surface.blit(ls, (SCREEN_W // 2 - ls.get_width() // 2, sy))
            sy += ls.get_height() + 4

        # Buttons
        self._btn_new.render(surface)
        self._btn_continue.render(surface)
        self._btn_quit.render(surface)

        # Version watermark
        vs = self._f_small.render("v0.1  prototype", True, C["text_dim"])
        surface.blit(vs, (SCREEN_W - vs.get_width() - 10,
                           SCREEN_H - vs.get_height() - 8))

    def _draw_particles(self, surface: pygame.Surface) -> None:
        """Very cheap ambient particles — no allocation per frame."""
        import random
        rng = random.Random(42)
        for _ in range(60):
            px = rng.randint(0, SCREEN_W)
            py = rng.randint(0, SCREEN_H)
            # Drift based on time
            px = int((px + self._time * 4) % SCREEN_W)
            py = int((py + self._time * 1.5) % SCREEN_H)
            alpha = 40 + int(30 * math.sin(self._time + rng.random() * 6.28))
            r = max(0, min(255, alpha))
            pygame.draw.circle(surface, (r, r, r + 30), (px, py), 1)
