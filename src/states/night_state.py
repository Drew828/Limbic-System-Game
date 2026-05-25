# =============================================================================
# states/night_state.py
# Night consolidation phase.
#
# Flow:
#   1. Show all STM memories
#   2. Player selects up to consolidation_slots (default 3) to consolidate → LTM
#   3. Dream replay animation for consolidated memories
#   4. Show merge candidates — player can accept/decline
#   5. Nightly decay on remaining STM; purge faded
#   6. Transition to "travel"
# =============================================================================

from __future__ import annotations
import math
import pygame
from src.constants import (C, SCREEN_W, SCREEN_H, HUD_H, BAL)
from src.fonts import get_font, FS_HEADING, FS_BODY, FS_LABEL, FS_SMALL
from src.models.memory import Memory
from src.models.player import PlayerState
from src.states.base_state import BaseState
from src.systems.memory_manager import MemoryManager
from src.systems.merge_system import MergeSystem, MergeCandidate
from src.systems.progression import ProgressionSystem
from src.systems.save_system import SaveSystem
from src.ui.hud import HUD
from src.ui.memory_panel import MemoryPanel
from src.ui.journal_ui import JournalUI
from src.ui.components.button import Button
from src.ui.components.panel import Panel


_SUB_SELECT    = "select"      # choose which memories to consolidate
_SUB_DREAM     = "dream"       # dream replay animation
_SUB_MERGE     = "merge"       # merge interface
_SUB_SUMMARY   = "summary"     # night summary before travel
_SUB_DONE      = "done"


class NightState(BaseState):

    def __init__(self,
                 memory_manager: MemoryManager,
                 merge_system:   MergeSystem,
                 progression:    ProgressionSystem,
                 save_system:    SaveSystem) -> None:
        super().__init__()
        self._mm   = memory_manager
        self._ms   = merge_system
        self._prog = progression
        self._save = save_system

        self._player: PlayerState | None = None
        self._sub:    str                = _SUB_SELECT
        self._time:   float              = 0.0

        self._selected_ids:  list[str]           = []
        self._merge_cands:   list[MergeCandidate] = []
        self._dream_mems:    list[Memory]         = []
        self._dream_timer:   float                = 0.0
        self._dream_per_mem: float                = 0.9  # seconds per memory
        self._dream_index:   int                  = 0
        self._consolidated_count:   int             = 0
        self._failed_consol_count:  int             = 0
        self._forgotten_count:      int             = 0

        self._hud      = HUD()
        self._mem_panel = MemoryPanel()
        self._journal   = JournalUI(on_close=self._close_journal)
        self._journal_open = False

        self._f_heading = get_font(FS_HEADING, bold=True)
        self._f_body    = get_font(FS_BODY)
        self._f_label   = get_font(FS_LABEL)
        self._f_small   = get_font(FS_SMALL)

        bw = 320
        bx = SCREEN_W // 2 - bw // 2

        self._confirm_btn = Button(
            rect=(bx, SCREEN_H - 80, bw, 44),
            text="Consolidate Selected",
            on_click=self._start_consolidation,
            colour=C["btn_gold"],
            hover_colour=C["btn_gold_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=8,
        )

        self._skip_merge_btn = Button(
            rect=(SCREEN_W // 2 + 10, SCREEN_H - 80, 200, 44),
            text="Skip Merges →",
            on_click=self._finish_night,
            colour=C["btn"],
            hover_colour=C["btn_hover"],
            font_size=FS_LABEL,
            border_radius=8,
        )

        self._travel_btn = Button(
            rect=(SCREEN_W // 2 - 140, SCREEN_H - 80, 280, 44),
            text="Begin Travel Phase →",
            on_click=self._go_to_travel,
            colour=C["btn_positive"],
            hover_colour=C["btn_positive_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=8,
        )

        # Panel for center area
        self._main_panel = Panel(
            rect=(20, HUD_H + 10, SCREEN_W - 40, SCREEN_H - HUD_H - 100),
            bg_colour=C["bg_panel"],
            border_colour=C["border"],
        )

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def on_enter(self, data: dict) -> None:
        self._player = data["player"]
        self._sub    = _SUB_SELECT
        self._time   = 0.0
        self._selected_ids = []
        self._dream_mems   = []

        max_slots = self._prog.consolidation_slots(self._player)
        self._mem_panel.set_memories(self._player.short_term)
        self._mem_panel.set_mode("select", max_select=max_slots)
        self._confirm_btn.text = f"Consolidate (0/{max_slots} selected)"

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._journal_open:
            self._journal.handle_event(event)
            # Skip button must still receive events when journal is open in merge mode
            if self._sub == _SUB_MERGE:
                self._skip_merge_btn.handle_event(event)
            return

        self._hud.handle_event(event)

        if self._sub == _SUB_SELECT:
            self._mem_panel.handle_event(event)
            self._confirm_btn.handle_event(event)
            # Update button label
            sel = self._mem_panel.get_selected_memories()
            max_s = self._prog.consolidation_slots(self._player)
            self._confirm_btn.text = f"Consolidate ({len(sel)}/{max_s} selected)"

        elif self._sub == _SUB_MERGE:
            self._journal.handle_event(event)   # journal doubles as merge UI
            self._skip_merge_btn.handle_event(event)

        elif self._sub == _SUB_SUMMARY:
            self._travel_btn.handle_event(event)

        if event.type == pygame.KEYDOWN and event.key == pygame.K_j:
            self._open_journal()

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self._time += dt
        if self._journal_open:
            self._journal.update(dt)
            return

        self._mem_panel.update(dt)

        if self._sub == _SUB_DREAM:
            self._dream_timer += dt
            if self._dream_timer >= self._dream_per_mem:
                self._dream_timer = 0.0
                self._dream_index += 1
                if self._dream_index >= len(self._dream_mems):
                    self._post_dream()

        elif self._sub == _SUB_DONE:
            self._goto("travel", {"player": self._player})

        if self._hud.journal_requested:
            self._open_journal()
            self._hud.journal_requested = False

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(C["bg_night"])

        self._main_panel.render(surface)
        self._mem_panel.render(surface)
        self._hud.render(surface, self._player, self._prog)

        if self._sub == _SUB_SELECT:
            self._render_select(surface)
            self._confirm_btn.render(surface)

        elif self._sub == _SUB_DREAM:
            self._render_dream(surface)

        elif self._sub == _SUB_MERGE:
            self._journal.render(surface)
            self._skip_merge_btn.render(surface)

        elif self._sub == _SUB_SUMMARY:
            self._render_summary(surface)
            self._travel_btn.render(surface)

        # Only render journal overlay when not already rendered as merge UI
        if self._journal_open and self._sub != _SUB_MERGE:
            self._journal.render(surface)

    # -----------------------------------------------------------------------
    # Sub-phase rendering
    # -----------------------------------------------------------------------

    def _render_select(self, surface: pygame.Surface) -> None:
        cx = SCREEN_W // 2
        y  = HUD_H + 20

        ts = self._f_heading.render("— Night Falls —", True, C["ltm"])
        surface.blit(ts, (cx - ts.get_width() // 2, y));  y += ts.get_height() + 8

        max_s = self._prog.consolidation_slots(self._player)
        sub   = self._f_body.render(
            f"Select up to {max_s} memories to consolidate into long-term storage.",
            True, C["text_dim"])
        surface.blit(sub, (cx - sub.get_width() // 2, y));  y += sub.get_height() + 6

        warn = self._f_small.render(
            "Unselected memories will be forgotten at dawn.",
            True, C["health_low"])
        surface.blit(warn, (cx - warn.get_width() // 2, y))

        # Cortisol warning — high stress impairs consolidation
        if self._player.health <= BAL["cortisol_threshold"]:
            cortisol_w = self._f_small.render(
                "⚠ HIGH CORTISOL: stress hormones weaken memory consolidation tonight.",
                True, C["health_low"])
            surface.blit(cortisol_w, (cx - cortisol_w.get_width() // 2, y + 20))

        # Brain science context
        fact = self._f_small.render(
            "(Hippocampus \u2192 Neocortex: sleep consolidation transfers STM to LTM)",
            True, C["text_dim"])
        surface.blit(fact, (cx - fact.get_width() // 2, y + 44))

    def _render_dream(self, surface: pygame.Surface) -> None:
        # Pulsing dream overlay
        alpha = int(80 + 60 * math.sin(self._time * 3.0))
        overlay = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        overlay.fill((20, 0, 50, alpha))
        surface.blit(overlay, (0, 0))

        y  = SCREEN_H // 2 - 60
        cx = SCREEN_W // 2

        ds = self._f_heading.render("Dream Replay", True, C["dream"])
        surface.blit(ds, (cx - ds.get_width() // 2, y));  y += ds.get_height() + 6

        sub = self._f_small.render(
            "The hippocampus replays today's experiences to strengthen long-term traces.",
            True, C["text_dim"])
        surface.blit(sub, (cx - sub.get_width() // 2, y));  y += sub.get_height() + 14

        if self._dream_index < len(self._dream_mems):
            m = self._dream_mems[self._dream_index]
            # Fade-in effect
            fade = min(1.0, self._dream_timer / 0.3)
            col  = tuple(int(c * fade) for c in C["ltm"])
            ms   = self._f_label.render(m.title, True, col)
            surface.blit(ms, (cx - ms.get_width() // 2, y));  y += ms.get_height() + 6
            desc = m.description[:80] + "\u2026" if len(m.description) > 80 else m.description
            ds2  = self._f_small.render(desc, True, C["text_dim"])
            surface.blit(ds2, (cx - ds2.get_width() // 2, y))

    def _render_summary(self, surface: pygame.Surface) -> None:
        y  = HUD_H + 20
        cx = SCREEN_W // 2

        ts = self._f_heading.render(
            f"Night {self._player.current_night} Complete", True, C["ltm"])
        surface.blit(ts, (cx - ts.get_width() // 2, y));  y += ts.get_height() + 16

        rows = [
            ("Consolidated tonight",   str(self._consolidated_count)),
            ("Failed to consolidate",  str(self._failed_consol_count)),
            ("Memories forgotten",     str(self._forgotten_count)),
            ("Total long-term",        str(len(self._player.long_term))),
            ("Nights remaining",
             str(BAL["total_nights"] - self._player.current_night)),
        ]
        for label, val in rows:
            ls = self._f_label.render(f"{label}:", True, C["text_dim"])
            vs = self._f_label.render(val, True, C["text"])
            surface.blit(ls, (cx - 140, y))
            surface.blit(vs, (cx + 20, y))
            y += ls.get_height() + 6

        y += 12
        # Educational note
        notes = [
            "Memory consolidation: during sleep, the hippocampus replays",
            "neural patterns so the neocortex can build long-term traces.",
            "Stronger emotional memories (amygdala-tagged) resist forgetting.",
        ]
        for note in notes:
            ns = self._f_small.render(note, True, C["text_dim"])
            surface.blit(ns, (cx - ns.get_width() // 2, y))
            y += ns.get_height() + 3

    # -----------------------------------------------------------------------
    # Night logic
    # -----------------------------------------------------------------------

    def _start_consolidation(self) -> None:
        selected   = self._mem_panel.get_selected_memories()
        consolidated           = []
        self._failed_consol_count = 0
        for m in selected:
            result_mem, succeeded = self._mm.consolidate(self._player, m.id)
            if succeeded and result_mem:
                consolidated.append(result_mem)
            elif not succeeded:
                self._failed_consol_count += 1

        self._consolidated_count = len(consolidated)
        self._dream_mems  = consolidated
        self._dream_index = 0
        self._dream_timer = 0.0
        self._mm.dream_replay(self._player)
        self._sub = _SUB_DREAM if consolidated else _SUB_MERGE
        self._mem_panel.set_mode("view")

    def _post_dream(self) -> None:
        self._mm.clear_dream_status(self._player)
        # Detect merge candidates
        self._merge_cands = self._ms.detect_candidates(self._player)
        if self._merge_cands:
            self._journal.open(self._player, self._merge_cands)
            self._journal._is_open = False  # open in overlay mode on demand
            self._sub = _SUB_MERGE
            # Show journal as merge UI
            self._open_journal_for_merge()
        else:
            self._finish_night()

    def _open_journal_for_merge(self) -> None:
        self._journal.open(self._player, self._merge_cands)
        self._journal.on_merge = self._on_merge_confirmed
        self._journal_open = True

    def _on_merge_confirmed(self, candidate: MergeCandidate) -> None:
        result = self._ms.execute_merge(self._player, candidate)
        if result:
            # Refresh candidates
            self._merge_cands = self._ms.detect_candidates(self._player)
            self._journal.open(self._player, self._merge_cands)

    def _finish_night(self) -> None:
        # Nightly decay and cleanup
        self._mm.apply_nightly_decay(self._player, self._prog)
        self._mm.purge_faded_stm(self._player)
        # Capture forgotten count before wiping — used in summary display
        self._forgotten_count = len(self._player.short_term)
        # Clear all remaining STM — only consolidated memories persist
        self._player.short_term.clear()
        self._mem_panel.set_memories(self._player.short_term)
        self._sub = _SUB_SUMMARY
        self._journal_open = False

    def _go_to_travel(self) -> None:
        self._sub = _SUB_DONE

    # -----------------------------------------------------------------------
    # Journal helpers
    # -----------------------------------------------------------------------

    def _open_journal(self) -> None:
        if not self._player:
            return
        if not self._journal_open:
            self._journal.open(self._player, self._merge_cands)
            self._journal_open = True

    def _close_journal(self) -> None:
        self._journal_open = False
