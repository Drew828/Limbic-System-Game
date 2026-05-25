# =============================================================================
# ui/hud.py
# Persistent heads-up display: health bar, night counter, phase label,
# Journal button, and Save button.
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import C, SCREEN_W, HUD_H, BAL
from src.fonts import get_font, FS_LABEL, FS_SMALL, FS_BODY
from src.ui.components.button import Button
from src.models.player import PlayerState
from src.systems.progression import ProgressionSystem


class HUD:
    """
    Drawn at the very top of the screen every frame.
    Provides callbacks: on_journal_click, on_save_click.
    """

    HEALTH_BAR_W = 200
    HEALTH_BAR_H = 16

    def __init__(
        self,
        on_journal_click=None,
        on_save_click=None,
    ) -> None:
        self.on_journal_click  = on_journal_click
        self.on_save_click     = on_save_click
        self.journal_requested = False
        self.save_requested    = False
        self._f_body  = get_font(FS_BODY, bold=True)
        self._f_small = get_font(FS_SMALL)
        self._f_label = get_font(FS_LABEL)

        btn_y = (HUD_H - 28) // 2
        self._journal_btn = Button(
            rect=(SCREEN_W - 220, btn_y, 100, 28),
            text="Journal",
            on_click=self._on_journal,
            colour=C["btn_gold"],
            hover_colour=C["btn_gold_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=5,
        )
        self._save_btn = Button(
            rect=(SCREEN_W - 112, btn_y, 80, 28),
            text="Save",
            on_click=self._on_save,
            colour=C["btn"],
            font_size=FS_LABEL,
            border_radius=5,
        )

    def _on_journal(self) -> None:
        self.journal_requested = True
        if self.on_journal_click:
            self.on_journal_click()

    def _on_save(self) -> None:
        self.save_requested = True
        if self.on_save_click:
            self.on_save_click()

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        self._journal_btn.handle_event(event)
        self._save_btn.handle_event(event)

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface,
               player: PlayerState,
               progression: ProgressionSystem) -> None:
        # Background bar
        pygame.draw.rect(surface, C["bg_dark"], (0, 0, SCREEN_W, HUD_H))
        pygame.draw.line(surface, C["border"], (0, HUD_H - 1), (SCREEN_W, HUD_H - 1))

        pad = 14
        cy  = HUD_H // 2

        # --- Health ---
        hx = pad
        hlabel = self._f_small.render("HEALTH", True, C["text_dim"])
        surface.blit(hlabel, (hx, cy - 12))

        bar_y = cy + 1
        bw    = self.HEALTH_BAR_W
        bh    = self.HEALTH_BAR_H

        # Background
        pygame.draw.rect(surface, C["health_bg"], (hx, bar_y, bw, bh), border_radius=4)

        # Fill
        frac = player.health_fraction
        fw   = int(bw * frac)
        if frac > 0.5:
            bar_col = C["health_full"]
        elif frac > 0.25:
            bar_col = C["health_mid"]
        else:
            bar_col = C["health_low"]
        if fw > 0:
            pygame.draw.rect(surface, bar_col, (hx, bar_y, fw, bh), border_radius=4)
        pygame.draw.rect(surface, C["border"], (hx, bar_y, bw, bh),
                         width=1, border_radius=4)

        # HP text over bar
        hp_text = self._f_small.render(f"{player.health}/{player.health_max}", True,
                                        C["text_bright"])
        surface.blit(hp_text, (hx + bw // 2 - hp_text.get_width() // 2,
                                bar_y + 1))

        # --- STM indicator + cortisol warning ---
        stm_x = hx + bw + 20
        stm_label = self._f_small.render(
            f"STM: {player.stm_count}/{player.stm_capacity}", True, C["stm"])
        surface.blit(stm_label, (stm_x, cy - 8))

        # Cortisol warning: only shown when health is critically low
        if player.health <= BAL["cortisol_threshold"]:
            cortisol_s = self._f_small.render(
                "⚠ HIGH CORTISOL — encoding impaired", True, C["health_low"])
            surface.blit(cortisol_s, (stm_x, cy + 6))

        # --- Night + Phase ---
        night_str = progression.night_label(player)
        ns = self._f_body.render(night_str, True, C["text_bright"])
        nx = SCREEN_W // 2 - ns.get_width() // 2
        surface.blit(ns, (nx, cy - ns.get_height() // 2))

        phase_str = progression.phase_label(player)
        ps = self._f_small.render(phase_str, True, progression.phase_colour(player))
        surface.blit(ps, (SCREEN_W // 2 - ps.get_width() // 2, cy + 10))

        # --- Buttons ---
        self._journal_btn.render(surface)
        self._save_btn.render(surface)
