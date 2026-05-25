# =============================================================================
# ui/components/scroll_view.py
# Vertically scrollable container for arbitrary child surfaces.
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import C


class ScrollView:
    """
    Clips a tall virtual surface to a visible rect and allows mouse-wheel
    scrolling.  Children render to a separate surface; ScrollView blits only
    the visible portion.
    """

    SCROLL_SPEED = 24   # pixels per mouse-wheel tick

    def __init__(self, rect: pygame.Rect, content_height: int = 0) -> None:
        self.rect           = pygame.Rect(rect)
        self.content_height = max(content_height, self.rect.height)
        self._scroll_y      = 0
        self._content_surf  = pygame.Surface((self.rect.width, self.content_height),
                                             pygame.SRCALPHA)
        self._scroll_bar_w  = 6

    @property
    def content_surface(self) -> pygame.Surface:
        """Caller draws into this surface, then calls render()."""
        return self._content_surf

    def resize_content(self, new_height: int) -> None:
        self.content_height = max(new_height, self.rect.height)
        self._content_surf  = pygame.Surface(
            (self.rect.width, self.content_height), pygame.SRCALPHA)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEWHEEL:
            if self.rect.collidepoint(pygame.mouse.get_pos()):
                self._scroll_y = max(
                    0,
                    min(
                        self.content_height - self.rect.height,
                        self._scroll_y - event.y * self.SCROLL_SPEED,
                    ),
                )
                return True
        return False

    def scroll_to_top(self) -> None:
        self._scroll_y = 0

    def render(self, surface: pygame.Surface) -> None:
        # Blit visible slice of content
        src_rect = pygame.Rect(0, self._scroll_y, self.rect.width, self.rect.height)
        surface.blit(self._content_surf, self.rect.topleft, area=src_rect)

        # Scroll bar
        if self.content_height > self.rect.height:
            bar_h    = int(self.rect.height * self.rect.height / self.content_height)
            bar_y    = int(self._scroll_y / self.content_height * self.rect.height)
            bar_rect = pygame.Rect(
                self.rect.right - self._scroll_bar_w - 2,
                self.rect.y + bar_y,
                self._scroll_bar_w,
                max(bar_h, 20),
            )
            pygame.draw.rect(surface, C["border"], bar_rect, border_radius=3)
