# =============================================================================
# states/base_state.py
# Abstract base for all game states.
# =============================================================================

from __future__ import annotations
from abc import ABC, abstractmethod
import pygame


class BaseState(ABC):
    """
    All game states inherit from this class.
    The Game class holds a stack of states and delegates events/update/render
    to the top-most state.

    State transitions are communicated back to the Game via the transition
    property — the Game checks it each frame and performs the switch.
    """

    def __init__(self) -> None:
        self._next_state: str | None = None
        self._transition_data: dict  = {}

    # -----------------------------------------------------------------------
    # Lifecycle hooks
    # -----------------------------------------------------------------------

    def on_enter(self, data: dict = None) -> None:
        """Called once when this state becomes active."""
        pass

    def on_exit(self) -> None:
        """Called once when transitioning away from this state."""
        pass

    # -----------------------------------------------------------------------
    # Per-frame interface
    # -----------------------------------------------------------------------

    @abstractmethod
    def handle_event(self, event: pygame.event.Event) -> None: ...

    @abstractmethod
    def update(self, dt: float) -> None: ...

    @abstractmethod
    def render(self, surface: pygame.Surface) -> None: ...

    # -----------------------------------------------------------------------
    # Transition helpers
    # -----------------------------------------------------------------------

    @property
    def next_state(self) -> str | None:
        return self._next_state

    @property
    def transition_data(self) -> dict:
        return self._transition_data

    def _goto(self, state_name: str, data: dict = None) -> None:
        self._next_state     = state_name
        self._transition_data = data or {}

    def _clear_transition(self) -> None:
        self._next_state      = None
        self._transition_data = {}
