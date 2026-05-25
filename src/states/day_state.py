# =============================================================================
# states/day_state.py
# Core day loop.
#
# Flow:
#   on_enter → load or create player → build event queue
#   For each event in queue:
#     1. show_event (panel + choices)
#     2. player picks choice
#     3. show_outcome
#     4. offer encode (if memory reward exists)
#        a. if STM full → drop dialog first
#     5. next event
#   After final event → transition to "night"
#
# Journal is available any time (push-down overlay via game.push_journal).
# =============================================================================

from __future__ import annotations
import pygame
from src.constants import (C, SCREEN_W, SCREEN_H, HUD_H, CONTENT_H,
                            CHOICE_BAR_H, MEMORY_PANEL_W)
from src.fonts import get_font, FS_LABEL, FS_SMALL
from src.models.event import Event, Choice, OutcomeType
from src.models.memory import Memory
from src.models.player import PlayerState
from src.states.base_state import BaseState
from src.systems.event_system import EventSystem
from src.systems.memory_manager import MemoryManager
from src.systems.merge_system import MergeSystem
from src.systems.progression import ProgressionSystem
from src.systems.save_system import SaveSystem
from src.ui.hud import HUD
from src.ui.event_panel import EventPanel
from src.ui.memory_panel import MemoryPanel
from src.ui.components.button import Button
from src.ui.journal_ui import JournalUI


_SUB_IDLE       = "idle"        # waiting for event to show
_SUB_EVENT      = "event"       # event visible, showing choices
_SUB_OUTCOME    = "outcome"     # outcome displayed, waiting for "next"
_SUB_ENCODE     = "encode"      # encode offer in memory panel
_SUB_DROP       = "drop"        # drop-memory dialog
_SUB_DONE       = "done"        # all events complete, transitioning


class DayState(BaseState):

    def __init__(self,
                 event_system:  EventSystem,
                 memory_manager: MemoryManager,
                 merge_system:  MergeSystem,
                 progression:   ProgressionSystem,
                 save_system:   SaveSystem) -> None:
        super().__init__()
        self._evs  = event_system
        self._mm   = memory_manager
        self._ms   = merge_system
        self._prog = progression
        self._save = save_system

        self._player:  PlayerState | None = None
        self._queue:   list[Event]        = []
        self._q_index: int                = 0
        self._sub:     str                = _SUB_IDLE

        # Current event context
        self._current_event:   Event  | None   = None
        self._choices:         list[Choice]    = []
        self._pending_memory:  Memory | None   = None
        self._last_outcome_type: OutcomeType | None = None

        # UI
        self._hud         = HUD()
        self._event_panel = EventPanel()
        self._mem_panel   = MemoryPanel()
        self._journal     = JournalUI(
            on_close=self._close_journal,
            on_merge=None,  # no merge in day phase
        )

        # Choice buttons (rebuilt per event)
        self._choice_buttons: list[Button] = []

        # "Next" / "Continue" button shown after outcome
        bw = SCREEN_W - MEMORY_PANEL_W - 48
        self._next_btn = Button(
            rect=(24, SCREEN_H - CHOICE_BAR_H + 20, bw, 44),
            text="Continue →",
            on_click=self._advance,
            colour=C["btn"],
            hover_colour=C["btn_hover"],
            font_size=FS_LABEL,
            bold=True,
            border_radius=8,
        )

        self._journal_open = False

    # -----------------------------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------------------------

    def on_enter(self, data: dict) -> None:
        from src.models.player import PlayerState

        if data.get("new_game"):
            self._player = PlayerState()
            self._prog.reset(self._player)
        elif "load_slot" in data:
            loaded = self._save.load(data["load_slot"])
            self._player = loaded if loaded else PlayerState()
            self._prog.reset(self._player)
        elif "player" in data:
            self._player = data["player"]
        else:
            # Re-enter from night/travel — player already exists
            self._player = data.get("player", self._player)

        self._queue   = self._evs.build_day_queue(self._player, self._mm)
        self._q_index = 0
        self._sub     = _SUB_IDLE
        self._mem_panel.set_memories(self._player.short_term)
        self._advance()  # show first event immediately

    def on_exit(self) -> None:
        pass

    # -----------------------------------------------------------------------
    # Input
    # -----------------------------------------------------------------------

    def handle_event(self, event: pygame.event.Event) -> None:
        if self._journal_open:
            self._journal.handle_event(event)
            return

        self._hud.handle_event(event)
        self._mem_panel.handle_event(event)

        if self._sub == _SUB_EVENT:
            for btn in self._choice_buttons:
                btn.handle_event(event)

        elif self._sub in (_SUB_OUTCOME, _SUB_IDLE):
            self._next_btn.handle_event(event)

        elif self._sub in (_SUB_ENCODE, _SUB_DROP):
            self._mem_panel.handle_event(event)

        # Journal hotkey
        if event.type == pygame.KEYDOWN and event.key == pygame.K_j:
            self._open_journal()

    # -----------------------------------------------------------------------
    # Update
    # -----------------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self._journal_open:
            self._journal.update(dt)
            return

        self._mem_panel.update(dt)

        if self._sub == _SUB_DONE:
            # Transition to night
            self._goto("night", {"player": self._player})

        # HUD save button callback
        if self._hud.save_requested:
            self._save.save(self._player, slot=0)
            self._hud.save_requested = False

        if self._hud.journal_requested:
            self._open_journal()
            self._hud.journal_requested = False

    # -----------------------------------------------------------------------
    # Render
    # -----------------------------------------------------------------------

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(C["bg"])

        self._event_panel.render(surface)
        self._mem_panel.render(surface)

        # Choice buttons or next button
        if self._sub == _SUB_EVENT:
            for btn in self._choice_buttons:
                btn.render(surface)
        elif self._sub in (_SUB_OUTCOME,):
            self._next_btn.render(surface)

        self._hud.render(surface, self._player, self._prog)

        if self._journal_open:
            self._journal.render(surface)

    # -----------------------------------------------------------------------
    # Advance logic
    # -----------------------------------------------------------------------

    def _advance(self) -> None:
        """Progress to the next stage of the day loop."""
        if self._q_index >= len(self._queue):
            self._sub = _SUB_DONE
            return

        event = self._queue[self._q_index]
        self._q_index       += 1
        self._current_event  = event

        visible_cues = self._evs.get_visible_cues(event, self._player, self._prog)
        self._event_panel.show_event(
            event, visible_cues,
            self._q_index - 1, len(self._queue),
        )

        choices = self._evs.get_visible_choices(event, self._player, self._mm)
        self._choices = choices
        self._rebuild_choice_buttons(choices)
        self._sub = _SUB_EVENT

    def _rebuild_choice_buttons(self, choices: list[Choice]) -> None:
        self._choice_buttons = []
        if not choices:
            return

        bar_y  = SCREEN_H - CHOICE_BAR_H
        bar_w  = SCREEN_W - MEMORY_PANEL_W
        bw     = (bar_w - 24) // max(len(choices), 1)
        pad    = 12
        bh     = CHOICE_BAR_H - 16

        for i, choice in enumerate(choices):
            bx = pad + i * (bw + 4)
            btn = Button(
                rect=(bx, bar_y + 8, bw - 4, bh),
                text=choice.text,
                on_click=self._make_choice_cb(choice),
                colour=C["btn"],
                hover_colour=C["btn_hover"],
                font_size=FS_SMALL,
                border_radius=6,
            )
            self._choice_buttons.append(btn)

    def _make_choice_cb(self, choice: Choice):
        def cb():
            self._on_choice_made(choice)
        return cb

    def _on_choice_made(self, choice: Choice) -> None:
        result = self._evs.process_choice(self._current_event, choice, self._player)

        # Apply health delta
        self._player.change_health(result.health_delta)

        # Check for death immediately
        if self._prog.check_game_over(self._player):
            self._goto("game_over", {"player": self._player, "victory": False})
            return

        # Show outcome
        self._event_panel.show_outcome(
            result.description, result.outcome_type, result.health_delta)
        self._last_outcome_type = result.outcome_type
        self._sub = _SUB_OUTCOME

        # Save pending memory reward
        self._pending_memory = result.memory if result.memory else None
        if self._pending_memory:
            # Tag the memory with the scene where it was formed
            if self._current_event:
                self._pending_memory.scene_formed_in = (
                    self._current_event.scene_type.value)
            self._offer_encode()

    def _offer_encode(self) -> None:
        m = self._pending_memory
        if m is None:
            return

        if not self._mm.can_encode(self._player):
            # STM full — ask player to drop one
            self._sub = _SUB_DROP
            self._mem_panel.set_mode("select", max_select=1)
            self._mem_panel.offer_encode(
                m,
                on_encode=self._do_encode,
                on_skip=self._skip_encode,
                drop_needed=True,
                on_drop=self._do_drop_encode,
            )
        else:
            self._sub = _SUB_ENCODE
            self._mem_panel.offer_encode(
                m,
                on_encode=self._do_encode,
                on_skip=self._skip_encode,
                on_encode_mnemonic=self._do_encode_mnemonic,
            )

    def _do_encode(self, memory: Memory) -> None:
        self._mm.encode(self._player, memory)
        self._mm.apply_interference(self._player, memory)
        self._pending_memory = None
        self._mem_panel.set_memories(self._player.short_term)
        self._mem_panel.clear_encode_offer()
        self._sub = _SUB_OUTCOME  # back to "press Continue"

    def _do_encode_mnemonic(self, memory: Memory) -> None:
        """Encode with a mnemonic anchor: slower decay, better LTM chance."""
        memory.has_mnemonic = True
        self._mm.encode(self._player, memory)
        self._mm.apply_interference(self._player, memory)
        self._pending_memory = None
        self._mem_panel.set_memories(self._player.short_term)
        self._mem_panel.clear_encode_offer()
        self._sub = _SUB_OUTCOME  # back to "press Continue"

    def _do_drop_encode(self, drop_id: str, new_memory: Memory) -> None:
        # Record the title before replacing
        old_title = next(
            (m.title for m in self._player.short_term if m.id == drop_id),
            "a memory"
        )
        self._mm.replace_stm(self._player, drop_id, new_memory)
        self._mm.apply_interference(self._player, new_memory)
        self._pending_memory = None
        self._mem_panel.set_memories(self._player.short_term)
        self._mem_panel.clear_encode_offer()
        self._mem_panel.set_mode("view")
        self._event_panel.show_outcome_note(
            f"\u2193 '{old_title}' was forgotten to make room for '{new_memory.title}'."
        )
        self._sub = _SUB_OUTCOME

    def _skip_encode(self) -> None:
        self._pending_memory = None
        self._mem_panel.clear_encode_offer()
        self._mem_panel.set_mode("view")
        self._advance()   # skip → go straight to next event

    # -----------------------------------------------------------------------
    # Journal helpers
    # -----------------------------------------------------------------------

    def _open_journal(self) -> None:
        if not self._player:
            return
        self._journal.open(self._player)
        self._journal_open = True

    def _close_journal(self) -> None:
        self._journal_open = False
