# =============================================================================
# ui/event_panel.py
# Displays the current day event: scene, title, description, cues, and
# outcome result.  Does NOT show choice buttons — those are owned by day_state.
#
# Design rationale:
#   The event panel focuses on information display only.  The day_state
#   composes choice buttons below the panel.  This separation lets the
#   panel be reused for outcome display (after choice) without duplication.
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import C, SCREEN_W, HUD_H, CONTENT_H, CHOICE_BAR_H, MEMORY_PANEL_W
from src.fonts import get_font, FS_HEADING, FS_BODY, FS_LABEL, FS_SMALL
from src.models.event import Event, Cue, OutcomeType, SceneType
from src.ui.components.panel import Panel


# Scene type → background colour (when no art assets)
_SCENE_BG: dict[str, tuple] = {
    "forest":  (18, 30, 22),
    "river":   (16, 26, 38),
    "meadow":  (24, 32, 18),
    "cave":    (18, 16, 22),
    "village": (28, 26, 20),
    "road":    (22, 22, 22),
    "camp":    (26, 22, 16),
    "ruins":   (24, 20, 20),
    "night":   (10, 10, 18),
    "dream":   (16, 14, 28),
}

_SENSE_ICONS: dict[str, str] = {
    "visual":    "[V]",
    "sound":     "[S]",
    "smell":     "[~]",
    "tactile":   "[T]",
    "contextual":"[C]",
}


class EventPanel:
    """
    Left 2/3 of the screen during the day phase.
    Shows: scene header, title, description, visible cues.
    After a choice: shows outcome text with colour coding.
    """

    # Panel geometry  (stays within left 2/3 of content area)
    PANEL_X = 0
    PANEL_Y = HUD_H
    PANEL_W = SCREEN_W - MEMORY_PANEL_W
    PANEL_H = CONTENT_H + CHOICE_BAR_H  # extends to bottom

    def __init__(self) -> None:
        self._panel   = Panel(
            rect=(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H),
            bg_colour=C["bg_panel"],
            border_colour=C["border"],
            border_radius=0,
        )
        self._f_heading = get_font(FS_HEADING, bold=True)
        self._f_body    = get_font(FS_BODY)
        self._f_label   = get_font(FS_LABEL)
        self._f_small   = get_font(FS_SMALL)

        # State
        self._event:         Event | None   = None
        self._outcome_text:  str | None     = None
        self._outcome_type:  OutcomeType | None = None
        self._outcome_note:  str | None     = None
        self._outcome_health: int | None    = None
        self._visible_cues: list[Cue]      = []
        self._event_index:  int            = 0
        self._total_events: int            = 10

    # -----------------------------------------------------------------------
    # State setters (called by day_state)
    # -----------------------------------------------------------------------

    def show_event(self, event: Event, visible_cues: list[Cue],
                   index: int, total: int) -> None:
        self._event         = event
        self._visible_cues  = visible_cues
        self._outcome_text   = None
        self._outcome_type   = None
        self._outcome_note   = None
        self._outcome_health = None
        self._event_index   = index
        self._total_events  = total

    def show_outcome(self, text: str, outcome_type: OutcomeType,
                     health_delta: int = 0) -> None:
        self._outcome_text   = text
        self._outcome_type   = outcome_type
        self._outcome_note   = None
        self._outcome_health = health_delta if health_delta != 0 else None

    def show_outcome_note(self, text: str) -> None:
        """Append a secondary note below the outcome text (e.g. which memory was dropped)."""
        self._outcome_note = text

    def clear(self) -> None:
        self._event = None
        self._outcome_text = None
        self._outcome_note = None

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        if not self._event:
            return

        e   = self._event
        pad = 24

        # --- Scene header band ---
        scene_bg = _SCENE_BG.get(e.scene_type.value, C["bg_dark"])
        scene_rect = pygame.Rect(self.PANEL_X, self.PANEL_Y,
                                 self.PANEL_W, 90)
        pygame.draw.rect(surface, scene_bg, scene_rect)

        # Scene type label
        scene_label = self._f_small.render(
            e.scene_type.value.upper(), True, C["text_dim"])
        surface.blit(scene_label, (pad, self.PANEL_Y + 10))

        # Event counter
        counter = self._f_small.render(
            f"Event {self._event_index + 1} / {self._total_events}", True, C["text_dim"])
        surface.blit(counter, (self.PANEL_W - counter.get_width() - pad,
                                self.PANEL_Y + 10))

        # Category badge
        cat_col = C.get(f"cat_{e.category.value}", C["cat_neutral"])
        badge   = self._f_small.render(
            f"  {e.category.value.upper()}  ", True, cat_col)
        badge_rect = pygame.Rect(pad - 4,
                                  self.PANEL_Y + 28,
                                  badge.get_width() + 8, 20)
        pygame.draw.rect(surface, (*cat_col[:3], 40),
                         badge_rect, border_radius=4)
        surface.blit(badge, (pad, self.PANEL_Y + 30))

        # Event title
        ts = self._f_heading.render(e.title, True, C["text_bright"])
        surface.blit(ts, (pad, self.PANEL_Y + 56))

        # --- Body area ---
        body_y = self.PANEL_Y + 100
        body_w = self.PANEL_W - pad * 2

        # Description (word-wrapped)
        body_y = self._draw_wrapped(surface, e.description, pad, body_y,
                                    body_w, self._f_body, C["text"], 22) + 18

        # --- Cues ---
        if self._visible_cues:
            cue_label = self._f_label.render("Cues observed:", True, C["text_dim"])
            surface.blit(cue_label, (pad, body_y))
            body_y += cue_label.get_height() + 6

            for cue in self._visible_cues:
                icon   = _SENSE_ICONS.get(cue.sense, "[?]")
                icon_s = self._f_small.render(icon, True, C["text_dim"])
                desc_s = self._f_small.render(cue.description, True, C["text"])
                surface.blit(icon_s, (pad + 4, body_y))
                surface.blit(desc_s, (pad + 4 + icon_s.get_width() + 6, body_y))
                body_y += desc_s.get_height() + 4

        body_y += 12

        # --- Outcome text ---
        if self._outcome_text:
            outcome_col = {
                OutcomeType.SUCCESS: C["health_full"],
                OutcomeType.FAILURE: C["health_low"],
                OutcomeType.MIXED:   C["health_mid"],
                OutcomeType.NEUTRAL: C["text_dim"],
            }.get(self._outcome_type, C["text"])

            # Outcome header
            o_header = {
                OutcomeType.SUCCESS: "— SUCCESS —",
                OutcomeType.FAILURE: "— FAILURE —",
                OutcomeType.MIXED:   "— MIXED OUTCOME —",
                OutcomeType.NEUTRAL: "— OUTCOME —",
            }.get(self._outcome_type, "— OUTCOME —")
            oh = self._f_label.render(o_header, True, outcome_col)
            surface.blit(oh, (pad, body_y))
            body_y += oh.get_height() + 8

            body_y = self._draw_wrapped(surface, self._outcome_text, pad, body_y,
                                        body_w, self._f_body, outcome_col, 22)

            # Health delta badge
            if self._outcome_health is not None:
                body_y += 10
                if self._outcome_health > 0:
                    hp_text = f"+{self._outcome_health} health"
                    hp_col  = C["health_full"]
                else:
                    hp_text = f"{self._outcome_health} health"
                    hp_col  = C["health_low"]
                hp_s = self._f_label.render(hp_text, True, hp_col)
                surface.blit(hp_s, (pad, body_y))
                body_y += hp_s.get_height()

            if self._outcome_note:
                body_y += 10
                note_s = self._f_small.render(self._outcome_note, True, C["stm"])
                surface.blit(note_s, (pad, body_y))

    def _draw_wrapped(self, surface, text, x, y, max_w, font, colour, line_h) -> int:
        words = text.split()
        line  = ""
        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    s = font.render(line, True, colour)
                    surface.blit(s, (x, y))
                    y += line_h
                line = word
        if line:
            s = font.render(line, True, colour)
            surface.blit(s, (x, y))
            y += line_h
        return y
