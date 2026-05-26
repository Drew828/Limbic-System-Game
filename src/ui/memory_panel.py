# =============================================================================
# ui/memory_panel.py
# Right-side panel showing current STM memories during the day phase.
# Also used in the Night phase to let the player pick consolidation targets.
# =============================================================================

from __future__ import annotations
import random
import pygame
from src.constants import C, SCREEN_W, HUD_H, CONTENT_H, CHOICE_BAR_H, MEMORY_PANEL_W, BAL
from src.fonts import get_font, FS_LABEL, FS_SMALL, FS_BODY
from src.models.memory import Memory
from src.ui.components.memory_card import MemoryCard
from src.ui.components.panel import Panel
from src.ui.components.button import Button


class MemoryPanel:
    """
    Right sidebar showing Short-Term Memory cards.

    Modes:
      "view"       — read-only list (day phase, travel phase)
      "select"     — player picks memories for a purpose (consolidation, travel)
      "encode"     — player decides whether to encode a new memory
    """

    PANEL_X = SCREEN_W - MEMORY_PANEL_W
    PANEL_Y = HUD_H
    PANEL_W = MEMORY_PANEL_W
    PANEL_H = CONTENT_H + CHOICE_BAR_H

    CARD_H   = 66
    CARD_PAD = 6

    def __init__(self) -> None:
        self._panel = Panel(
            rect=(self.PANEL_X, self.PANEL_Y, self.PANEL_W, self.PANEL_H),
            bg_colour=C["bg_dark"],
            border_colour=C["border"],
        )
        self._f_label = get_font(FS_LABEL, bold=True)
        self._f_small = get_font(FS_SMALL)
        self._f_body  = get_font(FS_BODY)

        self._memories:   list[Memory]     = []
        self._cards:      list[MemoryCard] = []
        self._mode:       str              = "view"
        self._selected:   set[str]         = set()   # ids of selected memories
        self._max_select: int              = 1
        self._on_select_cb = None

        # Pending encode offer
        self._pending_memory:  Memory | None = None
        self._encode_btn:       Button | None = None
        self._skip_btn:         Button | None = None
        self._mnemonic_btn:     Button | None = None
        self._drop_mode:        bool          = False   # pick which to drop
        self._on_encode_cb      = None
        self._on_skip_cb        = None
        self._on_drop_cb        = None
        self._on_encode_mnemonic_cb = None

    # -----------------------------------------------------------------------
    # State setters
    # -----------------------------------------------------------------------

    def set_memories(self, memories: list[Memory]) -> None:
        self._memories = list(memories)
        self._rebuild_cards()

    def set_mode(self, mode: str, max_select: int = 1,
                 on_select=None) -> None:
        """
        mode: "view" | "select" | "encode"
        on_select: callback(list[Memory]) when selection confirmed
        """
        self._mode       = mode
        self._max_select = max_select
        self._selected   = set()
        self._on_select_cb = on_select
        for card in self._cards:
            card.selected  = False
            card.selectable = (mode == "select")

    def offer_encode(self, new_memory: Memory, on_encode, on_skip,
                     drop_needed: bool = False, on_drop=None,
                     on_encode_mnemonic=None) -> None:
        self._pending_memory        = new_memory
        self._on_encode_cb          = on_encode
        self._on_skip_cb            = on_skip
        self._on_drop_cb            = on_drop
        self._drop_mode             = drop_needed
        self._on_encode_mnemonic_cb = on_encode_mnemonic

        bw = (self.PANEL_W - 24) // 2

        # Mnemonic encoding available when 2+ STM slots are free and not in drop mode
        mnemonic_available = (
            on_encode_mnemonic is not None
            and not drop_needed
            and (BAL["stm_capacity"] - sum(2 if m.has_mnemonic else 1 for m in self._memories) >= 2)
        )

        if mnemonic_available:
            # Three-button layout: [Encode][Skip] on top row, [Mnemonic] below
            by = self.PANEL_Y + self.PANEL_H - 112
            self._encode_btn = Button(
                rect=(self.PANEL_X + 8, by, bw, 30),
                text="Encode",
                on_click=self._confirm_encode,
                colour=C["btn_positive"],
                hover_colour=C["btn_positive_hover"],
                font_size=FS_LABEL,
            )
            self._skip_btn = Button(
                rect=(self.PANEL_X + 16 + bw, by, bw, 30),
                text="Skip",
                on_click=self._skip_encode,
                colour=C["btn"],
                font_size=FS_LABEL,
            )
            mn_bw = self.PANEL_W - 16
            mn_by = by + 38
            self._mnemonic_btn = Button(
                rect=(self.PANEL_X + 8, mn_by, mn_bw, 30),
                text="Encode + Mnemonic  [2 STM slots]",
                on_click=self._confirm_encode_mnemonic,
                colour=(120, 90, 20),
                hover_colour=(160, 125, 30),
                font_size=FS_LABEL,
            )
        else:
            # Original two-button layout
            by = self.PANEL_Y + self.PANEL_H - 74
            self._encode_btn = Button(
                rect=(self.PANEL_X + 8, by, bw, 30),
                text="Encode" if not drop_needed else "Replace",
                on_click=self._confirm_encode,
                colour=C["btn_positive"],
                hover_colour=C["btn_positive_hover"],
                font_size=FS_LABEL,
            )
            self._skip_btn = Button(
                rect=(self.PANEL_X + 16 + bw, by, bw, 30),
                text="Skip",
                on_click=self._skip_encode,
                colour=C["btn"],
                font_size=FS_LABEL,
            )
            self._mnemonic_btn = None

        if drop_needed:
            # Enable selection so player can pick which to drop
            self.set_mode("select", max_select=1, on_select=None)

    def clear_encode_offer(self) -> None:
        self._pending_memory        = None
        self._encode_btn            = None
        self._skip_btn              = None
        self._mnemonic_btn          = None
        self._drop_mode             = False
        self._on_skip_cb            = None
        self._on_encode_mnemonic_cb = None

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        for card in self._cards:
            if card.handle_event(event):
                if self._mode == "select":
                    cid = card.memory.id
                    if card.selected:
                        if len(self._selected) >= self._max_select:
                            # Deselect oldest
                            old_id = next(iter(self._selected))
                            self._selected.discard(old_id)
                            for c in self._cards:
                                if c.memory.id == old_id:
                                    c.selected = False
                        self._selected.add(cid)
                    else:
                        self._selected.discard(cid)
                return True

        if self._encode_btn:
            self._encode_btn.handle_event(event)
        if self._skip_btn:
            self._skip_btn.handle_event(event)
        if self._mnemonic_btn:
            self._mnemonic_btn.handle_event(event)

        return False

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(self, dt: float) -> None:
        for card in self._cards:
            card.update(dt)

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        self._panel.render(surface)

        pad = self.PANEL_X + 8
        y   = self.PANEL_Y + 8

        # Header
        capacity   = BAL["stm_capacity"]
        slots_used = sum(2 if m.has_mnemonic else 1 for m in self._memories)
        label = self._f_label.render(
            f"Short-Term Memory  {slots_used}/{capacity}", True, C["text_dim"])
        surface.blit(label, (pad, y));  y += label.get_height() + 6

        # Capacity bar
        bw = self.PANEL_W - 16
        pygame.draw.rect(surface, C["health_bg"], (pad, y, bw, 5), border_radius=2)
        fw = int(bw * slots_used / capacity)
        if fw > 0:
            col = C["stm"] if slots_used < capacity else C["health_low"]
            pygame.draw.rect(surface, col, (pad, y, fw, 5), border_radius=2)
        y += 12

        # Memory cards
        for card in self._cards:
            card.rect.y = y
            card.render(surface)
            y += self.CARD_H + self.CARD_PAD

        # Pending encode offer
        if self._pending_memory:
            self._render_encode_offer(surface, y)

        # Encode / Skip / Mnemonic buttons
        if self._encode_btn:
            self._encode_btn.render(surface)
        if self._skip_btn:
            self._skip_btn.render(surface)
        if self._mnemonic_btn:
            self._mnemonic_btn.render(surface)

    def _render_encode_offer(self, surface: pygame.Surface, y: int) -> None:
        m   = self._pending_memory
        pad = self.PANEL_X + 8

        # Separator
        pygame.draw.line(surface, C["border_focus"],
                         (self.PANEL_X, y + 6), (self.PANEL_X + self.PANEL_W, y + 6))
        y += 14

        action = "Replace a memory?" if self._drop_mode else "Encode this memory?"
        qs = self._f_small.render(action, True, C["text_warn"])
        surface.blit(qs, (pad, y));  y += qs.get_height() + 4

        ms = self._f_label.render(m.title, True, C["stm"])
        surface.blit(ms, (pad, y));  y += ms.get_height() + 2

        desc = m.description[:60] + "…" if len(m.description) > 60 else m.description
        ds = self._f_small.render(desc, True, C["text_dim"])
        surface.blit(ds, (pad, y))

    # -----------------------------------------------------------------------
    # Selection helpers (for Night phase consolidation)
    # -----------------------------------------------------------------------

    def get_selected_memories(self) -> list[Memory]:
        return [m for m in self._memories if m.id in self._selected]

    # -----------------------------------------------------------------------
    # Private
    # -----------------------------------------------------------------------

    def _rebuild_cards(self) -> None:
        self._cards = []
        for i, m in enumerate(self._memories):
            rect = pygame.Rect(
                self.PANEL_X + 4,
                self.PANEL_Y + 30 + i * (self.CARD_H + self.CARD_PAD),
                self.PANEL_W - 8,
                self.CARD_H,
            )
            card = MemoryCard(rect, m, selectable=(self._mode == "select"))
            self._cards.append(card)

    def _confirm_encode(self) -> None:
        if self._drop_mode:
            selected = self.get_selected_memories()
            # Auto-pick a random memory if the player didn't select one
            target = selected[0] if selected else (
                random.choice(self._memories) if self._memories else None
            )
            if target and self._on_drop_cb:
                self._on_drop_cb(target.id, self._pending_memory)
        else:
            if self._on_encode_cb:
                self._on_encode_cb(self._pending_memory)
        self.clear_encode_offer()

    def _confirm_encode_mnemonic(self) -> None:
        if self._on_encode_mnemonic_cb and self._pending_memory:
            self._on_encode_mnemonic_cb(self._pending_memory)
        self.clear_encode_offer()

    def _skip_encode(self) -> None:
        cb = self._on_skip_cb
        self.clear_encode_offer()
        if cb:
            cb()
