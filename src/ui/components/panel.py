# =============================================================================
# ui/components/panel.py
# Rounded rectangle panel with optional title bar and shadow.
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import C
from src.fonts import get_font, FS_LABEL, FS_SMALL


class Panel:
    """Background panel with optional header text and thin border."""

    def __init__(
        self,
        rect:          pygame.Rect,
        bg_colour:     tuple = None,
        border_colour: tuple = None,
        border_radius: int   = 8,
        title:         str   = "",
        title_colour:  tuple = None,
    ) -> None:
        self.rect          = pygame.Rect(rect)
        self.bg_colour     = bg_colour     or C["bg_panel"]
        self.border_colour = border_colour or C["border"]
        self.border_radius = border_radius
        self.title         = title
        self.title_colour  = title_colour  or C["text_dim"]
        self._title_font   = get_font(FS_SMALL)

    def render(self, surface: pygame.Surface) -> None:
        # Drop shadow (4px offset)
        shadow_r = self.rect.move(3, 3)
        shadow_s = pygame.Surface(shadow_r.size, pygame.SRCALPHA)
        pygame.draw.rect(shadow_s, (0, 0, 0, 60), shadow_s.get_rect(),
                         border_radius=self.border_radius)
        surface.blit(shadow_s, shadow_r.topleft)

        # Body
        pygame.draw.rect(surface, self.bg_colour, self.rect,
                         border_radius=self.border_radius)
        pygame.draw.rect(surface, self.border_colour, self.rect,
                         width=1, border_radius=self.border_radius)

        # Title
        if self.title:
            ts = self._title_font.render(self.title, True, self.title_colour)
            surface.blit(ts, (self.rect.x + 10, self.rect.y + 7))
