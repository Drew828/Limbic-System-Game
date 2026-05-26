# =============================================================================
# ui/components/button.py
# Reusable button component with hover, press, and disabled states.
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import C
from src.fonts import get_font, FS_LABEL


class Button:
    """
    Self-contained button component.
    Supports: normal, hover, pressed, disabled visual states.
    Fires an on_click callback when clicked.
    Supports optional icon text prefix (emoji-style single char).
    """

    def __init__(
        self,
        rect:          pygame.Rect,
        text:          str,
        on_click=None,
        colour:        tuple[int,int,int] = None,
        hover_colour:  tuple[int,int,int] = None,
        text_colour:   tuple[int,int,int] = None,
        font_size:     int = FS_LABEL,
        bold:          bool = False,
        border_radius: int = 6,
        border_colour: tuple[int,int,int] = None,
        disabled:      bool = False,
        tooltip:       str = "",
    ) -> None:
        self.rect           = pygame.Rect(rect)
        self.text           = text
        self.on_click       = on_click
        self.colour         = colour or C["btn"]
        self.hover_colour   = hover_colour or C["btn_hover"]
        self.text_colour    = text_colour or C["text"]
        self.font           = get_font(font_size, bold=bold)
        self.border_radius  = border_radius
        self.border_colour  = border_colour
        self.disabled       = disabled
        self.tooltip        = tooltip

        self._hovered  = False
        self._pressed  = False

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Returns True if the button consumed the event (was clicked)."""
        if self.disabled:
            return False

        if event.type == pygame.MOUSEMOTION:
            self._hovered = self.rect.collidepoint(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self._pressed = True
                return False  # consume but don't fire yet (fire on release)

        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self.rect.collidepoint(event.pos):
                self._pressed = False
                if self.on_click:
                    self.on_click()
                return True
            self._pressed = False

        return False

    # -----------------------------------------------------------------------
    # Rendering
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        if self.disabled:
            bg = C["btn_disabled"]
        elif self._pressed:
            bg = C["btn_press"]
        elif self._hovered:
            bg = self.hover_colour
        else:
            bg = self.colour

        pygame.draw.rect(surface, bg, self.rect, border_radius=self.border_radius)

        # Border
        bc = self.border_colour or (C["border_focus"] if self._hovered else C["border"])
        pygame.draw.rect(surface, bc, self.rect, width=1, border_radius=self.border_radius)

        # Text (word-wrap in the rect width)
        self._render_text(surface)

    def _render_text(self, surface: pygame.Surface) -> None:
        lines = self._wrap(self.text, self.rect.width - 16)
        line_h = self.font.get_linesize()
        total_h = line_h * len(lines)
        start_y = self.rect.centery - total_h // 2

        tc = C["text_dim"] if self.disabled else self.text_colour
        for i, line in enumerate(lines):
            surf = self.font.render(line, True, tc)
            x = self.rect.centerx - surf.get_width() // 2
            y = start_y + i * line_h
            surface.blit(surf, (x, y))

    def _wrap(self, text: str, max_w: int) -> list[str]:
        words  = text.split()
        lines  = []
        current = ""
        for word in words:
            test = (current + " " + word).strip()
            if self.font.size(test)[0] <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def update(self, dt: float) -> None:
        """Refresh hover state from current mouse position (call each frame)."""
        self._hovered = self.rect.collidepoint(pygame.mouse.get_pos())

    def set_disabled(self, val: bool) -> None:
        self.disabled = val

    def move(self, x: int, y: int) -> None:
        self.rect.topleft = (x, y)
