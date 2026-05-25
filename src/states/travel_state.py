# =============================================================================
# states/travel_state.py
# Travel encounter phase — one encounter per night, tests memory recall.
#
# Flow:
#   1. Draw encounter from event_system
#   2. Show encounter description and context cues
#   3. List relevant memories (via memory_manager.get_relevant_memories_for_encounter)
#   4. Player selects one memory to act on (or "Improvise" with no memory)
#   5. Resolve encounter → health delta, result description
#   6. Advance night counter; check win/loss
#   7. Transition to "day" or "game_over"
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import C, SCREEN_W, SCREEN_H, HUD_H, MEMORY_PANEL_W, BAL
from src.fonts import get_font, FS_HEADING, FS_BODY, FS_LABEL, FS_SMALL
from src.models.memory import Memory, ContextRule
from src.models.player import PlayerState
from src.models.event import Encounter
from src.states.base_state import BaseState
from src.systems.event_system import EventSystem
from src.systems.memory_manager import MemoryManager
from src.systems.progression import ProgressionSystem
from src.systems.save_system import SaveSystem
from src.ui.hud import HUD
from src.ui.components.button import Button
from src.ui.components.panel import Panel
from src.ui.components.memory_card import MemoryCard
from src.ui.journal_ui import JournalUI


_SUB_ENCOUNTER  = "encounter"   # show encounter, memory choices
_SUB_RESULT     = "result"      # show resolution
_SUB_DONE       = "done"


class TravelState(BaseState):

    def __init__(self,
                 event_system:   EventSystem,
                 memory_manager: MemoryManager,
                 progression:    ProgressionSystem,
                 save_system:    SaveSystem) -> None:
        super().__init__()
        self._evs  = event_system
        self._mm   = memory_manager
        self._prog = progression
        self._save = save_system

        self._player:    PlayerState | None = None
        self._encounter: Encounter  | None  = None
        self._relevant:  list[Memory]       = []
        self._sub:       str                = _SUB_ENCOUNTER

        self._selected_memory:    Memory | None = None
        self._ltm_choices:       list[Memory]  = []
        self._result_text:       str           = ""
        self._result_health:     int           = 0
        self._result_bonus_trait: str | None   = None
        self._tot_hint:          str | None    = None   # tip-of-tongue hint
        self._context_note:      str | None    = None   # context mismatch note
        self._reconsolidation_mutated: bool    = False

        self._hud     = HUD()
        self._journal = JournalUI(on_close=self._close_journal)
        self._journal_open = False

        self._f_heading = get_font(FS_HEADING, bold=True)
        self._f_body    = get_font(FS_BODY)
        self._f_label   = get_font(FS_LABEL)
        self._f_small   = get_font(FS_SMALL)

        # Memory selection cards (rebuilt per encounter)
        self._mem_cards:    list[MemoryCard] = []
        self._mem_btns:     list[Button]     = []

        # Improvise button (no memory)
        self._improvise_btn = Button(
            rect=(0, 0, 200, 40),
            text="Improvise (no memory)",
            on_click=self._resolve_with_none,
            colour=C["btn"],
            hover_colour=C["btn_hover"],
            font_size=FS_SMALL,
            border_radius=6,
        )

        # Continue / next button
        self._continue_btn = Button(
            rect=(SCREEN_W // 2 - 140, SCREEN_H - 80, 280, 44),
            text="Continue →",
            on_click=self._advance,
            colour=C["btn_positive"],
            hover_colour=C["btn_positive_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=8,
        )

        self._main_panel = Panel(
            rect=(20, HUD_H + 10, SCREEN_W - 40, SCREEN_H - HUD_H - 100),
            bg_colour=C["bg_panel"],
            border_colour=C["border"],
        )

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def on_enter(self, data: dict) -> None:
        self._player    = data["player"]
        self._encounter = self._evs.get_encounter(self._player, self._prog)
        if self._encounter:
            # Show ALL long-term memories — player must judge which is relevant
            self._ltm_choices = list(self._player.long_term)
            enc_tags = list(self._encounter.relevant_memory_tags)
            self._relevant = self._mm.get_relevant_memories_for_encounter(
                self._player, enc_tags)
        else:
            self._ltm_choices = []
            self._relevant = []
        self._selected_memory    = None
        self._result_text        = ""
        self._result_bonus_trait = None
        self._tot_hint           = None
        self._context_note       = None
        self._reconsolidation_mutated = False
        self._sub = _SUB_ENCOUNTER
        self._rebuild_memory_buttons()

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._journal_open:
            self._journal.handle_event(event)
            return

        self._hud.handle_event(event)

        if self._sub == _SUB_ENCOUNTER:
            self._improvise_btn.handle_event(event)
            for btn in self._mem_btns:
                btn.handle_event(event)

        elif self._sub == _SUB_RESULT:
            self._continue_btn.handle_event(event)

        if event.type == pygame.KEYDOWN and event.key == pygame.K_j:
            self._open_journal()

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self._journal_open:
            self._journal.update(dt)
            return

        if self._sub == _SUB_DONE:
            # Advance progression
            self._prog.advance_night(self._player)

            # Check win/loss
            if self._prog.check_game_over(self._player):
                self._goto("game_over", {"player": self._player, "victory": False})
                return
            if self._prog.check_victory(self._player):
                self._goto("game_over", {"player": self._player, "victory": True})
                return

            self._goto("day", {"player": self._player})

        if self._hud.journal_requested:
            self._open_journal()
            self._hud.journal_requested = False

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(C["bg_travel"])
        self._main_panel.render(surface)
        self._hud.render(surface, self._player, self._prog)

        if not self._encounter:
            self._render_no_encounter(surface)
            self._continue_btn.render(surface)
            return

        if self._sub == _SUB_ENCOUNTER:
            self._render_encounter(surface)
        elif self._sub == _SUB_RESULT:
            self._render_result(surface)
            self._continue_btn.render(surface)

        if self._journal_open:
            self._journal.render(surface)

    # -----------------------------------------------------------------------
    # Sub-phase rendering
    # -----------------------------------------------------------------------

    def _render_encounter(self, surface: pygame.Surface) -> None:
        enc = self._encounter
        pad = 40
        y   = HUD_H + 24
        cx  = SCREEN_W // 2

        # Title
        ts = self._f_heading.render("— Travel Encounter —", True, C["text_warn"])
        surface.blit(ts, (cx - ts.get_width() // 2, y));  y += ts.get_height() + 10

        # Encounter title
        et = self._f_label.render(enc.title, True, C["text_bright"])
        surface.blit(et, (pad, y));  y += et.get_height() + 8

        # Description
        y = self._draw_wrapped(surface, enc.description, pad, y,
                                SCREEN_W - pad * 2, self._f_body, C["text"], 22) + 16

        # Memory choices — all LTM memories
        if self._ltm_choices:
            mh = self._f_label.render(
                "Which long-term memory applies here?", True, C["text_dim"])
            surface.blit(mh, (pad, y));  y += mh.get_height() + 8

            for btn in self._mem_btns:
                btn.rect.y = y
                btn.render(surface)
                y += btn.rect.height + 6

            y += 8
            # Improvise as a risky fallback
            self._improvise_btn.text         = "Improvise (skip memory — risks health loss)"
            self._improvise_btn.colour       = C["btn_danger"]
            self._improvise_btn.hover_colour = C["btn_danger_hover"]
        else:
            # No LTM yet — improvise is the only option
            hint = self._f_small.render(
                "No long-term memories yet — consolidate some tonight.", True, C["text_dim"])
            surface.blit(hint, (pad, y));  y += hint.get_height() + 10
            self._improvise_btn.text         = "Improvise (no long-term memory yet)"
            self._improvise_btn.colour       = C["btn"]
            self._improvise_btn.hover_colour = C["btn_hover"]

        self._improvise_btn.rect.x = pad
        self._improvise_btn.rect.y = y
        self._improvise_btn.render(surface)

    def _render_result(self, surface: pygame.Surface) -> None:
        pad = 40
        y   = HUD_H + 24
        cx  = SCREEN_W // 2

        ts  = self._f_heading.render("— Encounter Result —", True, C["text_dim"])
        surface.blit(ts, (cx - ts.get_width() // 2, y));  y += ts.get_height() + 14

        if self._result_health > 0:
            hcol = C["health_full"]
            label = f"+{self._result_health} health"
        elif self._result_health < 0:
            hcol  = C["health_low"]
            label = f"{self._result_health} health"
        else:
            hcol  = C["text_dim"]
            label = "No health change"

        hs = self._f_label.render(label, True, hcol)
        surface.blit(hs, (cx - hs.get_width() // 2, y));  y += hs.get_height() + 12

        y = self._draw_wrapped(surface, self._result_text, pad, y,
                           SCREEN_W - pad * 2, self._f_body, C["text"], 22)

        # Educational note: memory retrieval cue
        if self._selected_memory is not None:
            y += 16
            note = (f"Memory used: \"{self._selected_memory.title}\"  "
                    f"[Mastery: {self._selected_memory.mastery_label}  "
                    f"Strength: {self._selected_memory.memory_strength:.0%}]")
            ns = self._f_small.render(note, True, C["text_dim"])
            surface.blit(ns, (cx - ns.get_width() // 2, y))
            y += ns.get_height() + 4

        if self._result_bonus_trait:
            ts2 = self._f_small.render(
                f"Memory reinforced — new trait gained: \"{self._result_bonus_trait}\"",
                True, C["ltm"])
            surface.blit(ts2, (cx - ts2.get_width() // 2, y))
            y += ts2.get_height() + 4

        # Tip of the tongue
        if self._tot_hint:
            y += 6
            tot_s = self._f_small.render(
                f"Tip of the tongue: \"...{self._tot_hint}...\" \u2014"
                " the trace is there but too weak to act on.",
                True, C["uncertain"])
            surface.blit(tot_s, (cx - tot_s.get_width() // 2, y))
            y += tot_s.get_height() + 4

        # Context mismatch note
        if self._context_note:
            ctx_s = self._f_small.render(self._context_note, True, C["text_warn"])
            surface.blit(ctx_s, (cx - ctx_s.get_width() // 2, y))
            y += ctx_s.get_height() + 4

        # Reconsolidation note
        if self._reconsolidation_mutated:
            rc_s = self._f_small.render(
                "Reconsolidation: retrieving this memory slightly altered its trace.",
                True, C["false"])
            surface.blit(rc_s, (cx - rc_s.get_width() // 2, y))
    def _render_no_encounter(self, surface: pygame.Surface) -> None:
        cx = SCREEN_W // 2
        y  = SCREEN_H // 2 - 20
        s  = self._f_body.render("A quiet night passes uneventfully.", True, C["text_dim"])
        surface.blit(s, (cx - s.get_width() // 2, y))

    # -----------------------------------------------------------------------
    # Encounter logic
    # -----------------------------------------------------------------------

    def _resolve_with_none(self) -> None:
        self._selected_memory = None
        self._resolve(None)

    def _resolve_with_memory(self, memory: Memory):
        def cb():
            self._selected_memory = memory
            self._resolve(memory)
        return cb

    def _resolve(self, memory: Memory | None) -> None:
        enc = self._encounter
        self._result_bonus_trait      = None
        self._tot_hint                = None
        self._context_note            = None
        self._reconsolidation_mutated = False

        # --- Context-dependent retrieval ---
        # Memories formed in a different scene type are harder to access.
        orig_strength = None
        if memory is not None and memory.scene_formed_in:
            if memory.scene_formed_in != enc.scene_type.value:
                orig_strength = memory.memory_strength
                memory.memory_strength = max(
                    0.0,
                    memory.memory_strength - BAL["context_mismatch_debuff"])
                self._context_note = (
                    f"Context mismatch: this memory formed in '{memory.scene_formed_in}' "
                    f"\u2014 harder to recall in '{enc.scene_type.value}'.")

        result_type, health_delta, desc = self._evs.resolve_encounter(
            enc, memory, self._player)

        # Restore original strength after the check
        if orig_strength is not None:
            memory.memory_strength = orig_strength
            # If the player still got a result (partial or success), the scene
            # context is now associated with this memory — add a context rule.
            if result_type in ("success", "partial"):
                memory.add_context_rule(ContextRule(
                    condition="scene",
                    value=enc.scene_type.value,
                    modifier="applicable",
                    confidence=0.5,
                    discovered=True,
                ))

        # --- Tip of the tongue ---
        # Partial result with a memory: we know something is there but can't
        # fully retrieve it — surface a matching trait as a hint.
        if result_type == "partial" and memory is not None:
            enc_tags_lower = [t.lower() for t in enc.relevant_memory_tags]
            for trait in memory.traits:
                if any(tag in trait.lower() for tag in enc_tags_lower):
                    self._tot_hint = trait
                    break
            if self._tot_hint is None and memory.traits:
                self._tot_hint = memory.traits[0]

        # --- Reconsolidation ---
        # Using a memory re-opens it to modification (slight confidence drop).
        if memory is not None:
            self._reconsolidation_mutated = self._mm.apply_reconsolidation(
                memory, self._player.current_night)

        # On a correct memory: reinforce it and add a new trait
        if result_type == "success" and memory is not None:
            for tag in enc.relevant_memory_tags:
                if tag not in memory.traits:
                    memory.add_trait(tag)
                    self._result_bonus_trait = tag
                    break
            memory.reinforce(0.15, self._player.current_night)

        self._player.change_health(health_delta)
        self._result_health = health_delta
        self._result_text   = desc
        self._sub = _SUB_RESULT

    def _advance(self) -> None:
        self._sub = _SUB_DONE

    def _rebuild_memory_buttons(self) -> None:
        self._mem_btns = []
        pad = 40
        bw  = SCREEN_W - pad * 2

        for m in self._ltm_choices[:7]:  # cap at 7 (Miller's Law)
            btn = Button(
                rect=(pad, 0, bw, 38),  # y set in render
                text=f"{m.title}  [{m.mastery_label}]",
                on_click=self._resolve_with_memory(m),
                colour=C["btn_gold"],
                hover_colour=C["btn_gold_hover"],
                font_size=FS_SMALL,
                border_radius=6,
            )
            self._mem_btns.append(btn)

    # -----------------------------------------------------------------------
    # Journal helpers
    # -----------------------------------------------------------------------

    def _open_journal(self) -> None:
        if self._player and not self._journal_open:
            self._journal.open(self._player)
            self._journal_open = True

    def _close_journal(self) -> None:
        self._journal_open = False

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    def _draw_wrapped(self, surface, text, x, y, max_w, font, colour, line_h) -> int:
        words = text.split()
        line  = ""
        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    surface.blit(font.render(line, True, colour), (x, y))
                    y += line_h
                line = word
        if line:
            surface.blit(font.render(line, True, colour), (x, y))
            y += line_h
        return y
