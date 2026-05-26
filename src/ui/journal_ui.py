# =============================================================================
# ui/journal_ui.py
# Full-screen journal overlay — the living archive of long-term memories.
#
# Layout:
#   Left  column (260px): filter panel + search bar
#   Center column        : scrollable memory grid (cards)
#   Right column (320px) : memory detail view, merge interface
#
# Design rationale:
#   The journal is a push-down overlay — it lives on top of any base state.
#   It reads from player.long_term (read-only during most phases).
#   In the Night phase, it also accepts merge confirmations.
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import C, SCREEN_W, SCREEN_H
from src.fonts import get_font, FS_HEADING, FS_BODY, FS_LABEL, FS_SMALL
from src.models.memory import Memory, MemoryCategory, MemoryStatus, MasteryLevel
from src.models.player import PlayerState
from src.systems.merge_system import MergeSystem, MergeCandidate
from src.ui.components.button import Button
from src.ui.components.panel import Panel
from src.ui.components.scroll_view import ScrollView
from src.ui.components.memory_card import MemoryCard


# ---------------------------------------------------------------------------
# Memory folder / grouping
# ---------------------------------------------------------------------------

class MemoryGroup:
    """A thematic cluster of related memories shown as a collapsible folder."""
    __slots__ = ("label", "members")

    def __init__(self, label: str, members: list) -> None:
        self.label   = label
        self.members = members  # list[Memory]


# Theme keyword sets — a memory is placed in the FIRST group whose keywords
# match any whole word in its title + traits (first-match-wins priority).
_GROUP_THEMES: list[tuple[str, set[str]]] = [
    ("Edible",     {"edible", "forage", "safe to eat", "food source",
                    "safe berries", "nutritious", "harvest", "honey"}),
    ("Avoid",      {"avoid", "toxic", "poisonous", "irritant", "rash",
                    "nettles", "thorns", "dangerous plant", "do not touch"}),
    ("Insects",    {"bees", "wasp", "wasps", "hornet", "bee sting"}),
    ("Predators",  {"bear", "wolf", "wolves", "boar", "predator", "venomous"}),
    ("Fire",       {"fire", "flame", "ember", "torch", "campfire"}),
    ("Water",      {"flood", "stagnant", "crossing", "river", "stream"}),
    ("Plants",     {"mushroom", "berry", "berries", "fungus", "herb",
                    "nut", "nuts", "bark", "root"}),
    ("Navigation", {"cliff", "ridge", "landmark", "navigation", "lost", "fog"}),
    ("Shelter",    {"shelter", "camp", "bivouac", "warmth"}),
    ("Weather",    {"rain", "storm", "cold", "frost", "ice", "wind"}),
]


# Column geometry
_FILTER_W  = 200
_DETAIL_W  = 320
_GRID_W    = SCREEN_W - _FILTER_W - _DETAIL_W
_HEADER_H  = 50
_CONTENT_H = SCREEN_H - _HEADER_H

# Category filter options
_CATEGORIES = ["all"] + [c.value for c in MemoryCategory]
_STATUS_FILTERS = ["all", "active", "uncertain", "false", "fading"]


class JournalUI:
    """
    Full-screen journal overlay.
    Call open(player, merge_candidates) to display.
    on_close callback fires when the player dismisses it.
    on_merge callback fires when a merge is confirmed.
    """

    def __init__(self, on_close=None, on_merge=None) -> None:
        self.on_close = on_close
        self.on_merge = on_merge
        self._is_open = False

        self._player:      PlayerState | None = None
        self._merge_cands: list[MergeCandidate] = []
        self._memories:    list[Memory]        = []
        self._filtered:    list[Memory]        = []

        self._f_heading = get_font(FS_HEADING, bold=True)
        self._f_body    = get_font(FS_BODY)
        self._f_label   = get_font(FS_LABEL)
        self._f_small   = get_font(FS_SMALL)

        # Filter state
        self._active_category = "all"
        self._active_status   = "all"
        self._search_text     = ""
        self._search_active   = False

        # Selection
        self._selected_memory: Memory | None = None
        self._cards: list[MemoryCard]        = []

        # Folder / group state
        self._group_items:     list                  = []
        self._expanded_groups: set[str]              = set()
        self._folder_rects:    dict[str, pygame.Rect] = {}

        # Merge mode
        self._pending_merge: MergeCandidate | None = None

        # Overlay surface (semi-transparent background)
        self._overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self._overlay.fill((0, 0, 0, 210))

        # Panels
        self._filter_panel = Panel(
            rect=(_FILTER_W, _HEADER_H, _FILTER_W, _CONTENT_H),
            bg_colour=C["bg_dark"],
            border_colour=C["border"],
        )
        self._detail_panel = Panel(
            rect=(SCREEN_W - _DETAIL_W, _HEADER_H, _DETAIL_W, _CONTENT_H),
            bg_colour=C["bg_dark"],
            border_colour=C["border"],
        )

        # Close button
        self._close_btn = Button(
            rect=(SCREEN_W - 60, 8, 44, 34),
            text="X",
            on_click=self._close,
            colour=C["btn_danger"],
            hover_colour=C["btn_danger_hover"],
            font_size=FS_LABEL,
            bold=True,
        )

        # Scroll view for the grid
        self._scroll = ScrollView(
            rect=(_FILTER_W * 2, _HEADER_H, _GRID_W, _CONTENT_H),
            content_height=_CONTENT_H,
        )

        # Category filter buttons
        self._cat_buttons: list[Button] = []
        self._rebuild_filter_buttons()

        # Merge confirm buttons
        self._merge_confirm_btn: Button | None = None
        self._merge_cancel_btn:  Button | None = None

    # -----------------------------------------------------------------------
    # Open / Close
    # -----------------------------------------------------------------------

    def open(self, player: PlayerState,
             merge_candidates: list[MergeCandidate] = None) -> None:
        self._player      = player
        self._merge_cands = merge_candidates or []
        self._memories    = list(player.long_term)
        self._is_open     = True
        self._selected_memory = None
        self._pending_merge   = None
        self._apply_filters()

    def _close(self) -> None:
        self._is_open = False
        if self.on_close:
            self.on_close()

    @property
    def is_open(self) -> bool:
        return self._is_open

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> bool:
        if not self._is_open:
            return False

        self._close_btn.handle_event(event)
        self._scroll.handle_event(event)

        for btn in self._cat_buttons:
            btn.handle_event(event)

        for card in self._cards:
            if card.handle_event(event):
                return True

        if self._merge_confirm_btn:
            self._merge_confirm_btn.handle_event(event)
        if self._merge_cancel_btn:
            self._merge_cancel_btn.handle_event(event)

        # Search input
        if event.type == pygame.KEYDOWN and self._search_active:
            if event.key == pygame.K_BACKSPACE:
                self._search_text = self._search_text[:-1]
            elif event.key == pygame.K_ESCAPE:
                self._search_active = False
                self._search_text   = ""
            elif event.unicode and len(self._search_text) < 30:
                self._search_text += event.unicode
            self._apply_filters()

        if event.type == pygame.MOUSEBUTTONDOWN:
            # Folder header click — toggle expand / collapse
            if event.button == 1:
                for label, rect in self._folder_rects.items():
                    if rect.collidepoint(event.pos):
                        self._toggle_group(label)
                        return True

            # Detect click in search bar area
            sb_rect = pygame.Rect(_FILTER_W + 4, _HEADER_H + 8, _FILTER_W - 8, 28)
            if sb_rect.collidepoint(event.pos):
                self._search_active = True
                return True

        return True  # always consume events when open

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(self, dt: float) -> None:
        if not self._is_open:
            return
        for card in self._cards:
            card.update(dt)

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        if not self._is_open:
            return

        surface.blit(self._overlay, (0, 0))

        # Header bar
        pygame.draw.rect(surface, C["bg_dark"], (0, 0, SCREEN_W, _HEADER_H))
        pygame.draw.line(surface, C["border_focus"], (0, _HEADER_H - 1),
                         (SCREEN_W, _HEADER_H - 1))

        title = self._f_heading.render("— Memory Journal (Long-Term Store) —", True, C["ltm"])
        surface.blit(title, (SCREEN_W // 2 - title.get_width() // 2, 8))

        count_s = self._f_small.render(
            f"{len(self._memories)} long-term memories  ·  Neocortex & Hippocampal Index", True, C["text_dim"])
        surface.blit(count_s, (SCREEN_W // 2 - count_s.get_width() // 2, 34))

        self._close_btn.render(surface)

        # Filter panel
        self._filter_panel.render(surface)
        self._render_filters(surface)

        # Grid (center)
        self._render_grid(surface)

        # Detail panel (right)
        self._detail_panel.render(surface)
        if self._selected_memory:
            self._render_detail(surface, self._selected_memory)
        elif self._merge_cands:
            self._render_merge_list(surface)
        else:
            self._render_detail_empty(surface)

    def _render_filters(self, surface: pygame.Surface) -> None:
        fx  = _FILTER_W + 6
        fy  = _HEADER_H + 8

        # Search bar
        sb_rect = pygame.Rect(fx - 2, fy, _FILTER_W - 8, 28)
        pygame.draw.rect(surface, C["bg_card"] if not self._search_active
                         else C["bg_card_alt"], sb_rect, border_radius=4)
        pygame.draw.rect(surface, C["border_focus"] if self._search_active
                         else C["border"], sb_rect, width=1, border_radius=4)
        display = self._search_text or ("Search..." if not self._search_active else "")
        tc = C["text"] if self._search_text else C["text_dim"]
        st = self._f_small.render(display, True, tc)
        surface.blit(st, (fx + 2, fy + 6))
        fy += 38

        # Category buttons
        cat_label = self._f_small.render("Filter by type:", True, C["text_dim"])
        surface.blit(cat_label, (fx, fy));  fy += cat_label.get_height() + 4

        for btn in self._cat_buttons:
            btn.rect.y = fy
            btn.render(surface)
            fy += btn.rect.height + 3

        fy += 8
        # Merge section
        if self._merge_cands:
            ml = self._f_small.render(
                f"{len(self._merge_cands)} merge(s) available", True, C["merge_glow"])
            surface.blit(ml, (fx, fy))

    def _render_grid(self, surface: pygame.Surface) -> None:
        total_h = self._calc_content_height()
        if total_h != self._scroll.content_height:
            self._scroll.resize_content(total_h)

        cs = self._scroll.content_surface
        cs.fill((0, 0, 0, 0))

        card_w   = _GRID_W - 24
        card_h   = 72
        folder_h = 44
        member_h = 64
        card_x   = 8
        y        = 8
        padding  = 6
        scroll_y = self._scroll._scroll_y

        self._cards        = []
        self._folder_rects = {}

        for item in self._group_items:
            if isinstance(item, MemoryGroup):
                expanded = item.label in self._expanded_groups
                r = pygame.Rect(card_x, y, card_w, folder_h)
                self._render_folder_card(cs, r, item, expanded)
                # Real-screen rect for hit-testing
                self._folder_rects[item.label] = pygame.Rect(
                    _FILTER_W * 2 + card_x,
                    _HEADER_H + y - scroll_y,
                    card_w, folder_h,
                )
                y += folder_h + padding

                if expanded:
                    for m in item.members:
                        mr = pygame.Rect(card_x + 16, y, card_w - 16, member_h)
                        card = MemoryCard(mr, m, on_click=self._on_card_click)
                        card.selected = (self._selected_memory is not None and
                                         self._selected_memory.id == m.id)
                        card.update(0)
                        card.render(cs)
                        real_mr = pygame.Rect(
                            _FILTER_W * 2 + card_x + 16,
                            _HEADER_H + y - scroll_y,
                            card_w - 16, member_h,
                        )
                        card.rect = real_mr
                        self._cards.append(card)
                        y += member_h + 4
            else:
                m = item
                r = pygame.Rect(card_x, y, card_w, card_h)
                card = MemoryCard(r, m, on_click=self._on_card_click)
                card.selected = (self._selected_memory is not None and
                                 self._selected_memory.id == m.id)
                card.update(0)
                card.render(cs)
                real_r = pygame.Rect(
                    _FILTER_W * 2 + card_x,
                    _HEADER_H + y - scroll_y,
                    card_w, card_h,
                )
                card.rect = real_r
                self._cards.append(card)
                y += card_h + padding

        self._scroll.render(surface)

    # -----------------------------------------------------------------------
    # Folder / group helpers
    # -----------------------------------------------------------------------

    def _compute_groups(self, memories: list) -> list:
        """Cluster memories by shared theme keywords into MemoryGroup folders."""
        group_members: dict[str, list] = {}
        assigned: set[str] = set()

        for m in memories:
            if m.id in assigned:
                continue
            # Build a word-set from title + all traits
            words: set[str] = set()
            for part in [m.title] + list(m.traits):
                words.update(part.lower().split())

            for label, keywords in _GROUP_THEMES:
                if any(kw in words for kw in keywords):
                    group_members.setdefault(label, []).append(m)
                    assigned.add(m.id)
                    break  # first matching group wins

        # Build item list: folders (2+ members) then ungrouped memories
        grouped_ids: set[str] = set()
        items: list = []
        for label, _ in _GROUP_THEMES:
            members = group_members.get(label, [])
            if len(members) >= 2:
                items.append(MemoryGroup(label=label, members=members))
                grouped_ids.update(m.id for m in members)

        for m in memories:
            if m.id not in grouped_ids:
                items.append(m)

        return items

    def _calc_content_height(self) -> int:
        """Calculate the total scroll content height for the current group items."""
        card_h   = 72
        folder_h = 44
        member_h = 64
        padding  = 6
        h = 8
        for item in self._group_items:
            if isinstance(item, MemoryGroup):
                h += folder_h + padding
                if item.label in self._expanded_groups:
                    h += len(item.members) * (member_h + 4)
            else:
                h += card_h + padding
        h += 20
        return max(h, _CONTENT_H)

    def _toggle_group(self, label: str) -> None:
        if label in self._expanded_groups:
            self._expanded_groups.discard(label)
        else:
            self._expanded_groups.add(label)

    def _render_folder_card(self, surface: pygame.Surface, rect: pygame.Rect,
                             group: MemoryGroup, expanded: bool) -> None:
        pygame.draw.rect(surface, (28, 24, 18), rect, border_radius=6)
        border_col = C["merge_glow"] if expanded else C["border_focus"]
        pygame.draw.rect(surface, border_col, rect, width=1, border_radius=6)
        arrow = "▼" if expanded else "▶"
        text  = f"{arrow}  {group.label.upper()}   —  {len(group.members)} memories"
        col   = C["merge_glow"] if expanded else C["ltm"]
        ts    = self._f_label.render(text, True, col)
        cy    = rect.y + rect.height // 2 - ts.get_height() // 2
        surface.blit(ts, (rect.x + 12, cy))

    # -----------------------------------------------------------------------
    # Card interaction
    # -----------------------------------------------------------------------

    def _on_card_click(self, memory: Memory) -> None:
        self._selected_memory = memory
        # Check if any merge candidate involves this memory
        for cand in self._merge_cands:
            if cand.source_id == memory.id or cand.target_id == memory.id:
                self._pending_merge = cand
                self._build_merge_buttons()
                return
        self._pending_merge = None

    def _render_detail(self, surface: pygame.Surface, m: Memory) -> None:
        dx  = SCREEN_W - _DETAIL_W + 12
        dy  = _HEADER_H + 12
        dw  = _DETAIL_W - 24

        # Title
        ts = self._f_label.render(m.title, True,
                                   C["ltm"] if m.is_long_term else C["stm"])
        surface.blit(ts, (dx, dy));  dy += ts.get_height() + 6

        # Status badge
        status_text = m.status.value.upper()
        if m.is_false:
            status_text = "FALSE MEMORY"
        sc = C["false"] if m.is_false else C["text_dim"]
        ss = self._f_small.render(status_text, True, sc)
        surface.blit(ss, (dx, dy));  dy += ss.get_height() + 10

        # Description
        dy = self._draw_wrapped_detail(surface, m.description, dx, dy, dw,
                                        self._f_small, C["text_dim"]) + 8

        # Strength / Confidence
        self._detail_bar(surface, dx, dy, "Strength",   m.memory_strength, C["stm"])
        dy += 18
        self._detail_bar(surface, dx, dy, "Confidence", m.confidence,      C["ltm"])
        dy += 18
        self._detail_bar(surface, dx, dy, "Uncertainty",m.uncertainty,     C["uncertain"])
        dy += 24

        # Mastery
        ml = self._f_small.render(f"Mastery: {m.mastery_label}", True, C["text"])
        surface.blit(ml, (dx, dy));  dy += ml.get_height() + 4

        ew = self._f_small.render(
            f"Emotional weight: {m.emotional_weight:+.2f}", True,
            C["emotional"] if m.is_emotional else C["text_dim"])
        surface.blit(ew, (dx, dy));  dy += ew.get_height() + 10

        # Traits
        if m.traits:
            tl = self._f_small.render("Known traits:", True, C["text_dim"])
            surface.blit(tl, (dx, dy));  dy += tl.get_height() + 3
            for trait in m.traits[:6]:
                ts2 = self._f_small.render(f"  • {trait}", True, C["text"])
                surface.blit(ts2, (dx, dy));  dy += ts2.get_height() + 2
            if len(m.traits) > 6:
                more = self._f_small.render(
                    f"  … +{len(m.traits)-6} more", True, C["text_dim"])
                surface.blit(more, (dx, dy));  dy += more.get_height()
            dy += 8

        # Context rules
        discovered = m.discovered_context_rules()
        if discovered:
            cl = self._f_small.render("Context rules:", True, C["text_dim"])
            surface.blit(cl, (dx, dy));  dy += cl.get_height() + 3
            for rule in discovered[:4]:
                rt = self._f_small.render(
                    f"  If {rule.condition}={rule.value}: {rule.modifier}", True,
                    C["text"])
                surface.blit(rt, (dx, dy));  dy += rt.get_height() + 2
            dy += 8

        # Cues
        if m.cue_tags:
            cu = self._f_small.render("Retrieval cues:", True, C["text_dim"])
            surface.blit(cu, (dx, dy));  dy += cu.get_height() + 3
            for cue in m.cue_tags[:4]:
                cts = self._f_small.render(
                    f"  [{cue.sense}] {cue.description}", True, C["text"])
                surface.blit(cts, (dx, dy));  dy += cts.get_height() + 2
            dy += 8

        # Pending merge
        if self._pending_merge:
            self._render_merge_confirm(surface, dx, dy)

    def _render_merge_list(self, surface: pygame.Surface) -> None:
        dx = SCREEN_W - _DETAIL_W + 12
        dy = _HEADER_H + 12

        hl = self._f_label.render("Merge Opportunities", True, C["merge_glow"])
        surface.blit(hl, (dx, dy));  dy += hl.get_height() + 8

        for cand in self._merge_cands[:5]:
            # Get source / target titles
            sm = self._player.find_memory(cand.source_id) if self._player else None
            tm = self._player.find_memory(cand.target_id) if self._player else None
            if not sm or not tm:
                continue

            ct_col = C["health_low"] if cand.risk > 0.3 else C["health_full"]
            type_s = self._f_small.render(
                f"[{cand.merge_type.value.upper()}]  risk: {cand.risk:.0%}",
                True, ct_col)
            surface.blit(type_s, (dx, dy));  dy += type_s.get_height() + 2
            desc_s = self._f_small.render(
                f'{sm.title} + {tm.title}', True, C["text"])
            surface.blit(desc_s, (dx, dy));  dy += desc_s.get_height() + 2
            pygame.draw.line(surface, C["border"],
                             (dx, dy), (dx + _DETAIL_W - 24, dy))
            dy += 8

        il = self._f_small.render(
            "Click a memory card to see merge options.", True, C["text_dim"])
        surface.blit(il, (dx, dy))

    def _render_merge_confirm(self, surface: pygame.Surface, dx: int, dy: int) -> None:
        cand = self._pending_merge
        pygame.draw.line(surface, C["border_focus"],
                         (dx, dy), (dx + _DETAIL_W - 24, dy))
        dy += 8

        mh = self._f_small.render("Merge available:", True, C["merge_glow"])
        surface.blit(mh, (dx, dy));  dy += mh.get_height() + 4

        desc = cand.description[:80] + "…" if len(cand.description) > 80 else cand.description
        ds = self._f_small.render(desc, True, C["text"])
        surface.blit(ds, (dx, dy));  dy += ds.get_height() + 4

        if cand.risk > 0.3:
            wr = self._f_small.render(
                f"⚠ Risk: {cand.risk:.0%} chance of false memory", True, C["health_low"])
            surface.blit(wr, (dx, dy));  dy += wr.get_height() + 4

        if self._merge_confirm_btn:
            self._merge_confirm_btn.rect.topleft = (dx, dy)
            self._merge_confirm_btn.render(surface)
        if self._merge_cancel_btn:
            self._merge_cancel_btn.rect.topleft = (dx + 90, dy)
            self._merge_cancel_btn.render(surface)

    def _render_detail_empty(self, surface: pygame.Surface) -> None:
        dx = SCREEN_W - _DETAIL_W + 12
        dy = _HEADER_H + SCREEN_H // 2 - 30
        s = self._f_small.render("Select a memory to view details.", True, C["text_dim"])
        surface.blit(s, (dx, dy))

    # -----------------------------------------------------------------------
    # Merge button logic
    # -----------------------------------------------------------------------

    def _build_merge_buttons(self) -> None:
        self._merge_confirm_btn = Button(
            rect=(0, 0, 80, 26),
            text="Merge",
            on_click=self._confirm_merge,
            colour=C["btn_gold"],
            hover_colour=C["btn_gold_hover"],
            font_size=FS_SMALL,
        )
        self._merge_cancel_btn = Button(
            rect=(0, 0, 72, 26),
            text="Cancel",
            on_click=self._cancel_merge,
            colour=C["btn"],
            font_size=FS_SMALL,
        )

    def _confirm_merge(self) -> None:
        if self._pending_merge and self.on_merge:
            confirmed = self._pending_merge
            self._pending_merge = None
            self._merge_cands   = [c for c in self._merge_cands if c is not confirmed]
            self.on_merge(confirmed)
            self._memories = list(self._player.long_term) if self._player else []
            self._apply_filters()

    def _cancel_merge(self) -> None:
        self._pending_merge = None

    # -----------------------------------------------------------------------
    # Filter logic
    # -----------------------------------------------------------------------

    def _apply_filters(self) -> None:
        result = list(self._memories)

        if self._active_category != "all":
            result = [m for m in result if m.category.value == self._active_category]

        if self._active_status != "all":
            if self._active_status == "uncertain":
                result = [m for m in result if m.is_uncertain]
            elif self._active_status == "false":
                result = [m for m in result if m.is_false]
            elif self._active_status == "fading":
                result = [m for m in result if m.is_fading]
            else:
                result = [m for m in result if m.status.value == self._active_status]

        if self._search_text:
            q = self._search_text.lower()
            result = [
                m for m in result
                if (q in m.title.lower() or
                    q in m.description.lower() or
                    any(q in t.lower() for t in m.traits))
            ]

        self._filtered   = result
        self._group_items = self._compute_groups(result)

    def _rebuild_filter_buttons(self) -> None:
        bw = _FILTER_W - 12
        bh = 24
        bx = _FILTER_W + 6
        by = _HEADER_H + 52  # below search bar (placeholder y, adjusted in render)

        self._cat_buttons = []
        for i, cat in enumerate(_CATEGORIES[:8]):  # limit display
            def make_cb(c=cat):
                def cb():
                    self._active_category = c
                    self._apply_filters()
                return cb
            btn = Button(
                rect=(bx, by + i * (bh + 3), bw, bh),
                text=cat.upper(),
                on_click=make_cb(),
                colour=C["btn"],
                hover_colour=C["btn_hover"],
                font_size=FS_SMALL,
                border_radius=4,
            )
            self._cat_buttons.append(btn)

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    def _detail_bar(self, surface, x, y, label, value, colour):
        ls = self._f_small.render(f"{label}: ", True, C["text_dim"])
        surface.blit(ls, (x, y))
        bx = x + ls.get_width()
        bw = _DETAIL_W - 24 - ls.get_width()
        bh = 9
        pygame.draw.rect(surface, C["health_bg"], (bx, y + 2, bw, bh), border_radius=3)
        fw = int(bw * max(0, min(1, value)))
        if fw > 0:
            pygame.draw.rect(surface, colour, (bx, y + 2, fw, bh), border_radius=3)

    def _draw_wrapped_detail(self, surface, text, x, y, max_w, font, colour) -> int:
        words = text.split()
        line  = ""
        lh    = font.get_linesize()
        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    surface.blit(font.render(line, True, colour), (x, y))
                    y += lh
                line = word
        if line:
            surface.blit(font.render(line, True, colour), (x, y))
            y += lh
        return y
