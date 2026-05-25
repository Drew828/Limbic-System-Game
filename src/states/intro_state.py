# =============================================================================
# states/intro_state.py
# Cinematic new-game opening screen.
# Mission briefing text is revealed paragraph-by-paragraph with a typewriter
# effect.  Click / SPACE skips straight to the full text; then a button
# transitions to the first day.
# =============================================================================

from __future__ import annotations
import math
import pygame
from src.constants import C, SCREEN_W, SCREEN_H, FS_TITLE, FS_BODY, FS_LABEL, FS_SMALL
from src.fonts import get_font
from src.states.base_state import BaseState
from src.ui.components.button import Button

# ---------------------------------------------------------------------------
# Briefing paragraphs  (empty string = blank line between sections)
# ---------------------------------------------------------------------------
_PARAGRAPHS: list[str] = [
    "Hello, new mind.",
    "",
    "You are about to become something remarkable —",
    "the hippocampus and amygdala of a traveler's brain.",
    "",
    "The hippocampus encodes new experiences into short-term memory.",
    "The amygdala tags memories with emotional weight —",
    "fear makes them stick; joy makes them vivid.",
    "",
    "Your task: help the traveler collect and use memories wisely.",
    "",
    "Each night, you enter the consolidation phase.",
    "Choose which short-term memories deserve a permanent home.",
    "The rest fade with the dawn — lost forever.",
    "",
    "But be careful.",
    "Memories are not recordings. They are reconstructions.",
    "Merge too carelessly, and false beliefs form.",
    "Ignore cues, and danger goes unrecognised.",
    "",
    "Learn the patterns. Build context. Sharpen recall.",
    "Each night makes the traveler more — or less — prepared.",
    "",
    "STM holds roughly 7 items. Choose what is worth keeping.",
    "",
    "Stay aware.",
    "",
    "Good luck.",
]

_CHARS_PER_SEC = 45    # typewriter speed (characters per second)
_LINE_H        = 24    # vertical gap between lines
_PARA_GAP      = 6     # extra gap after blank-line paragraphs
_TEXT_TOP      = 120   # y where text block starts
_TEXT_LEFT     = 160   # left margin
_TEXT_MAX_W    = SCREEN_W - 320


class IntroState(BaseState):
    """
    Cinematic briefing shown once at the start of a new game.
    Paragraphs appear via typewriter; player may click/SPACE to skip ahead.
    After all text is visible, a "Begin Your Journey" button appears.
    Transitions to "day" with new_game=True.
    """

    def __init__(self) -> None:
        super().__init__()
        self._f_title  = get_font(FS_TITLE,  bold=True)
        self._f_body   = get_font(FS_BODY)
        self._f_italic = get_font(FS_BODY,   italic=True)
        self._f_small  = get_font(FS_SMALL)

        self._begin_btn = Button(
            rect=((SCREEN_W - 300) // 2, SCREEN_H - 110, 300, 52),
            text="Begin Your Journey",
            on_click=self._start_game,
            colour=C["btn_gold"],
            hover_colour=C["btn_gold_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=10,
        )

        self._reset()

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def on_enter(self, data: dict = None) -> None:
        self._reset()

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._all_done:
            self._begin_btn.handle_event(event)
            if event.type == pygame.KEYDOWN and event.key in (
                    pygame.K_SPACE, pygame.K_RETURN):
                self._start_game()
            return

        # Any click or SPACE skips to full text instantly
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._skip_to_end()
        elif event.type == pygame.KEYDOWN and event.key in (
                pygame.K_SPACE, pygame.K_RETURN):
            self._skip_to_end()

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self._all_done:
            return

        self._char_timer += dt
        chars_to_add = int(self._char_timer * _CHARS_PER_SEC)
        if chars_to_add <= 0:
            return
        self._char_timer -= chars_to_add / _CHARS_PER_SEC

        for _ in range(chars_to_add):
            self._advance_char()
            if self._all_done:
                break

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        # Dark gradient background
        surface.fill(C["bg"])

        # Subtle animated vignette pulse
        t     = pygame.time.get_ticks() / 1000.0
        alpha = int(28 + 12 * math.sin(t * 0.6))
        vignette = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        vignette.fill((0, 0, 0, alpha))
        surface.blit(vignette, (0, 0))

        # Title
        title_surf = self._f_title.render("LIMBIC  JOURNEY", True, C["ltm"])
        tx = (SCREEN_W - title_surf.get_width()) // 2
        surface.blit(title_surf, (tx, 40))

        # Subtitle
        sub_surf = self._f_small.render(
            "A journey through memory", True, C["text_dim"])
        sx = (SCREEN_W - sub_surf.get_width()) // 2
        surface.blit(sub_surf, (sx, 40 + title_surf.get_height() + 6))

        # Divider
        pygame.draw.line(surface, C["border"],
                         (_TEXT_LEFT, _TEXT_TOP - 12),
                         (SCREEN_W - _TEXT_LEFT, _TEXT_TOP - 12))

        # Render visible paragraphs
        y = _TEXT_TOP
        for i, line in enumerate(self._revealed_lines):
            if not line:  # blank separator
                y += _PARA_GAP
                continue
            # Determine if this line is the very last non-blank paragraph
            # (rendered with italic style for dramatic effect)
            is_last = (i == len(self._revealed_lines) - 1 and self._all_done)
            font = self._f_italic if is_last else self._f_body

            colour = C["text_bright"] if i == 0 else (
                C["text_warn"] if "be careful" in line.lower() or
                                  "stay aware" in line.lower() or
                                  "good luck" in line.lower()
                else C["text"]
            )
            surf = font.render(line, True, colour)
            surface.blit(surf, (_TEXT_LEFT, y))
            y += _LINE_H

        # Typing cursor blink
        if not self._all_done:
            blink = (pygame.time.get_ticks() // 500) % 2 == 0
            if blink:
                cursor = self._f_body.render("▌", True, C["stm"])
                surface.blit(cursor, (_TEXT_LEFT + self._cursor_x_offset, y - _LINE_H))

            # Skip hint
            hint = self._f_small.render(
                "[ Click or press SPACE to skip ]", True, C["text_dim"])
            surface.blit(hint,
                         ((SCREEN_W - hint.get_width()) // 2, SCREEN_H - 50))
        else:
            self._begin_btn.render(surface)

    # -----------------------------------------------------------------------
    # Private
    # -----------------------------------------------------------------------

    def _reset(self) -> None:
        self._para_index:     int   = 0    # which paragraph we're typing
        self._char_index:     int   = 0    # chars revealed in current paragraph
        self._char_timer:     float = 0.0
        self._all_done:       bool  = False
        self._revealed_lines: list[str] = []  # fully or partially revealed
        self._cursor_x_offset: int = 0

        # Seed first line
        if _PARAGRAPHS:
            self._revealed_lines.append("")

    def _advance_char(self) -> None:
        """Reveal one character of the current paragraph."""
        if self._para_index >= len(_PARAGRAPHS):
            self._all_done = True
            return

        current_para = _PARAGRAPHS[self._para_index]

        if not current_para:
            # Blank line — mark it instantly and move to next
            if not self._revealed_lines or self._revealed_lines[-1] != "":
                self._revealed_lines.append("")
            self._para_index += 1
            self._char_index  = 0
            if self._para_index < len(_PARAGRAPHS):
                self._revealed_lines.append("")  # prepare next line
            return

        if self._char_index < len(current_para):
            # Add next character to current (last) line
            self._revealed_lines[-1] = current_para[: self._char_index + 1]
            # Measure cursor offset for blinking cursor
            self._cursor_x_offset = self._f_body.size(
                current_para[: self._char_index + 1])[0]
            self._char_index += 1
        else:
            # Paragraph fully typed — move to next
            self._para_index += 1
            self._char_index  = 0
            if self._para_index < len(_PARAGRAPHS):
                self._revealed_lines.append("")  # prepare next line slot
            else:
                self._all_done = True

    def _skip_to_end(self) -> None:
        """Instantly reveal all text."""
        self._revealed_lines = list(_PARAGRAPHS)
        self._para_index     = len(_PARAGRAPHS)
        self._char_index     = 0
        self._all_done       = True

    def _start_game(self) -> None:
        self._goto("day", {"new_game": True})
