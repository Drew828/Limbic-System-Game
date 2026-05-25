# =============================================================================
# game.py
# Main Game class — owns pygame init, the main loop, and all systems.
#
# Architecture:
#   - Stack-based state machine.  Active state is _state_stack[-1].
#   - Journal is NOT a separate state — it is a push-down overlay managed
#     by each state (DayState, NightState, TravelState).
#   - All systems are instantiated once and injected into states.
#   - Transitions are read from state.next_state after each frame.
# =============================================================================

from __future__ import annotations
import sys
import pygame
from src.constants import SCREEN_W, SCREEN_H, C
from src.systems.event_system import EventSystem
from src.systems.memory_manager import MemoryManager
from src.systems.merge_system import MergeSystem
from src.systems.progression import ProgressionSystem
from src.systems.save_system import SaveSystem
from src.states.base_state import BaseState
from src.states.menu_state import MenuState
from src.states.intro_state import IntroState
from src.states.day_state import DayState
from src.states.night_state import NightState
from src.states.travel_state import TravelState
from src.states.game_over_state import GameOverState

_FPS = 60


class Game:
    """
    Owns pygame lifecycle, the state machine, and all system singletons.
    Call game.run() to start the main loop.
    """

    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Limbic Journey")
        self._screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
        self._clock  = pygame.time.Clock()

        # ---- Systems ----
        self._save_sys  = SaveSystem()
        self._event_sys = EventSystem()
        self._mm        = MemoryManager()
        self._ms        = MergeSystem()
        self._prog      = ProgressionSystem()

        # ---- State registry ----
        self._states: dict[str, BaseState] = {
            "menu": MenuState(self._save_sys),
            "intro": IntroState(),
            "day":  DayState(self._event_sys, self._mm, self._ms,
                             self._prog, self._save_sys),
            "night": NightState(self._mm, self._ms, self._prog, self._save_sys),
            "travel": TravelState(self._event_sys, self._mm,
                                  self._prog, self._save_sys),
            "game_over": GameOverState(self._prog),
        }

        # Start at menu
        self._state_stack: list[tuple[str, BaseState]] = []
        self._push_state("menu", {})

    # -----------------------------------------------------------------------
    # Public
    # -----------------------------------------------------------------------

    def run(self) -> None:
        while True:
            dt = self._clock.tick(_FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._shutdown()

                current = self._current_state
                if current:
                    current.handle_event(event)

            current = self._current_state
            if current:
                current.update(dt)

                # Transition
                if current.next_state:
                    target = current.next_state
                    data   = current.transition_data
                    current._clear_transition()

                    if target == "quit":
                        self._shutdown()

                    self._push_state(target, data)

            self._screen.fill(C["bg"])
            if self._current_state:
                self._current_state.render(self._screen)

            pygame.display.flip()

    # -----------------------------------------------------------------------
    # State machine
    # -----------------------------------------------------------------------

    @property
    def _current_state(self) -> BaseState | None:
        return self._state_stack[-1][1] if self._state_stack else None

    def _push_state(self, name: str, data: dict) -> None:
        if name not in self._states:
            raise ValueError(f"Unknown state: {name!r}")
        state = self._states[name]
        self._state_stack.append((name, state))
        state.on_enter(data)

    def _pop_state(self) -> None:
        if self._state_stack:
            _, state = self._state_stack.pop()
            state.on_exit()

    def _replace_state(self, name: str, data: dict) -> None:
        """Pop current and push new — used for linear transitions."""
        if self._state_stack:
            _, old = self._state_stack.pop()
            old.on_exit()
        self._push_state(name, data)

    # -----------------------------------------------------------------------
    # Quit
    # -----------------------------------------------------------------------

    def _shutdown(self) -> None:
        pygame.quit()
        sys.exit(0)
