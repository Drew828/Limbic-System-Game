# =============================================================================
# ui/components/memory_card.py
# A compact card widget that displays one Memory object.
# Used in both the STM panel (day phase) and the Journal.
# =============================================================================

from __future__ import annotations
import math
import pygame
from src.constants import C
from src.fonts import get_font, FS_LABEL, FS_SMALL
from src.models.memory import Memory, MemoryCategory, MemoryStatus


# Category → colour lookup
_CAT_COLOURS: dict[str, tuple] = {
    "danger":     C["cat_danger"],
    "food":       C["cat_food"],
    "neutral":    C["cat_neutral"],
    "sensory":    C["cat_sensory"],
    "emotional":  C["cat_emotional"],
    "ambiguous":  C["cat_ambiguous"],
    "contextual": C["cat_contextual"],
    "tool":       C["cat_neutral"],
    "person":     C["cat_sensory"],
    "place":      C["cat_contextual"],
}


class MemoryCard:
    """
    A compact memory card.  Can be shown in a list (compact mode)
    or expanded (shows traits, cues, context rules).
    Supports selection highlight and click callback.
    """

    COMPACT_H  = 64    # height in list mode
    EXPANDED_H = 160   # height in detail mode

    def __init__(
        self,
        rect:      pygame.Rect,
        memory:    Memory,
        on_click=None,
        expanded:  bool = False,
        selectable: bool = True,
    ) -> None:
        self.rect       = pygame.Rect(rect)
        self.memory     = memory
        self.on_click   = on_click
        self.expanded   = expanded
        self.selectable = selectable
        self.selected   = False
        self._hovered   = False
        self._pulse_t   = 0.0

        self._f_label  = get_font(FS_LABEL)
        self._f_small  = get_font(FS_SMALL)

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.rect.collidepoint(event.pos):
                if self.selectable:
                    self.selected = not self.selected
                if self.on_click:
                    self.on_click(self.memory)
                return True
        return False

    # -----------------------------------------------------------------------
    # Update (for pulse animation)
    # -----------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._pulse_t += dt

    # -----------------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        m = self.memory

        # Background colour based on memory status/type
        bg = self._bg_colour()

        # Pulse for dream replay
        if m.status == MemoryStatus.DREAM:
            pulse = (math.sin(self._pulse_t * 4) + 1) / 2
            bg = self._lerp_colour(bg, C["ltm"], pulse * 0.5)

        pygame.draw.rect(surface, bg, self.rect, border_radius=6)

        # Left accent bar (category colour)
        cat_col = _CAT_COLOURS.get(m.category.value, C["cat_neutral"])
        accent  = pygame.Rect(self.rect.x, self.rect.y,
                              4, self.rect.height)
        pygame.draw.rect(surface, cat_col, accent, border_radius=3)

        # Selection / hover border
        if self.selected:
            pygame.draw.rect(surface, C["border_hot"], self.rect,
                             width=2, border_radius=6)
        elif self._hovered:
            pygame.draw.rect(surface, C["border_focus"], self.rect,
                             width=1, border_radius=6)
        else:
            pygame.draw.rect(surface, C["border"], self.rect,
                             width=1, border_radius=6)

        if self.expanded:
            self._render_expanded(surface)
        else:
            self._render_compact(surface)

    def _render_compact(self, surface: pygame.Surface) -> None:
        m   = self.memory
        pad = 10
        x0  = self.rect.x + pad + 6   # skip accent bar
        cy  = self.rect.centery

        # Title
        title_col = C["ltm"] if m.is_long_term else C["stm"]
        if m.is_false:
            title_col = C["false"]
        if m.status == MemoryStatus.FADING:
            title_col = C["fading"]
        ts = self._f_label.render(m.title, True, title_col)
        surface.blit(ts, (x0, cy - ts.get_height()))

        # Memory-type badge: S=semantic (stable), E=episodic (can decay)
        mt_char  = "S" if m.memory_type == "semantic" else "E"
        mt_col   = C["ltm"] if m.memory_type == "semantic" else C["text_dim"]
        mt_badge = self._f_small.render(mt_char, True, mt_col)
        surface.blit(mt_badge, (self.rect.right - mt_badge.get_width() - 8,
                                 cy + ts.get_height() // 2 - 2))

        # Mnemonic badge: [M] shown in gold when the memory has a mnemonic anchor
        if m.has_mnemonic:
            mn_badge = self._f_small.render("[M]", True, (220, 185, 60))
            surface.blit(mn_badge,
                         (self.rect.right - mn_badge.get_width() - 22,
                          cy - ts.get_height() - 2))

        # Strength bar (bottom of card)
        bar_w  = self.rect.width - 60
        bar_h  = 4
        bar_y  = self.rect.bottom - 10
        pygame.draw.rect(surface, C["health_bg"],
                         (x0, bar_y, bar_w, bar_h), border_radius=2)
        fill_w = int(bar_w * m.memory_strength)
        bar_col = C["health_full"] if m.memory_strength > 0.5 else (
                  C["health_mid"] if m.memory_strength > 0.25 else C["health_low"])
        if fill_w > 0:
            pygame.draw.rect(surface, bar_col,
                             (x0, bar_y, fill_w, bar_h), border_radius=2)

        # LTM badge
        if m.is_long_term:
            badge = self._f_small.render("LTM", True, C["ltm"])
            surface.blit(badge, (self.rect.right - badge.get_width() - 26, cy - 6))
        elif m.is_uncertain:
            badge = self._f_small.render("?", True, C["uncertain"])
            surface.blit(badge, (self.rect.right - badge.get_width() - 26, cy - 6))

    def _render_expanded(self, surface: pygame.Surface) -> None:
        m   = self.memory
        pad = 10
        x0  = self.rect.x + pad + 6
        y   = self.rect.y + 8

        # Title
        title_col = C["ltm"] if m.is_long_term else C["stm"]
        if m.is_false:
            title_col = C["false"]
        ts = self._f_label.render(m.title, True, title_col)
        surface.blit(ts, (x0, y));  y += ts.get_height() + 4

        # Description (one line clipped)
        desc = m.description[:80] + "…" if len(m.description) > 80 else m.description
        ds = self._f_small.render(desc, True, C["text_dim"])
        surface.blit(ds, (x0, y));  y += ds.get_height() + 4

        # Traits
        trait_text = "  ".join(m.traits[:4]) or "(no known traits)"
        tt = self._f_small.render(trait_text, True, C["text"])
        surface.blit(tt, (x0, y));  y += tt.get_height() + 3

        # Strength / confidence bars
        self._mini_bar(surface, x0, y, "STR", m.memory_strength, C["stm"])
        self._mini_bar(surface, x0 + 100, y, "CON", m.confidence, C["ltm"])
        y += 14

        # Mastery level
        ml = self._f_small.render(f"Mastery: {m.mastery_label}", True, C["text_dim"])
        surface.blit(ml, (x0, y))

    def _mini_bar(self, surface, x, y, label, value, colour):
        lf = self._f_small.render(f"{label} ", True, C["text_dim"])
        surface.blit(lf, (x, y))
        bx = x + lf.get_width()
        pygame.draw.rect(surface, C["health_bg"], (bx, y + 3, 60, 7), border_radius=3)
        fw = int(60 * value)
        if fw > 0:
            pygame.draw.rect(surface, colour, (bx, y + 3, fw, 7), border_radius=3)

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _bg_colour(self) -> tuple:
        m = self.memory
        if m.is_false:
            return (40, 20, 20)
        if m.status == MemoryStatus.FADING:
            return (22, 22, 30)
        if m.is_emotional:
            return (35, 22, 32)
        if m.is_long_term:
            return (30, 26, 16)
        return C["bg_card"]

    @staticmethod
    def _lerp_colour(a: tuple, b: tuple, t: float) -> tuple:
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
