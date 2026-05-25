# =============================================================================
# systems/event_system.py
# Event pool management, procedural selection, and outcome processing.
#
# Design rationale:
#   Events are loaded from JSON and stored in a flat pool.  Selection is
#   weighted-random, but the weights are adjusted per-night using the
#   progression config so early nights emphasise simple danger and later
#   nights emphasise contextual/ambiguous events.
#   Prerequisite memory checking happens here — an event only appears if
#   the player has (or lacks) the required memories.
# =============================================================================

from __future__ import annotations
import json
import os
import random
from dataclasses import dataclass
from typing import Optional

from src.models.event import Event, Encounter, Choice, Outcome, OutcomeType, Cue
from src.models.memory import Memory
from src.models.player import PlayerState
from src.systems.memory_manager import MemoryManager
from src.constants import BAL


@dataclass
class ChoiceResult:
    """Return value of process_choice — bundles outcome data for day_state."""
    outcome_type:  OutcomeType
    description:   str
    health_delta:  int
    memory:        Optional[Memory]


_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "events")


class EventSystem:
    """
    Manages the pool of events and encounters.
    Provides daily event queues and encounter selection.
    """

    def __init__(self) -> None:
        self._events:     list[Event]     = []
        self._encounters: list[Encounter] = []
        self._load_all()

    # -----------------------------------------------------------------------
    # Loading
    # -----------------------------------------------------------------------

    def _load_all(self) -> None:
        event_dir = os.path.abspath(_DATA_DIR)
        if not os.path.isdir(event_dir):
            print(f"[EventSystem] Warning: data directory not found at {event_dir}")
            return

        for filename in sorted(os.listdir(event_dir)):
            if not filename.endswith(".json"):
                continue
            filepath = os.path.join(event_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for ed in data.get("events", []):
                    try:
                        self._events.append(Event.from_dict(ed))
                    except Exception as e:
                        print(f"[EventSystem] Failed to load event in {filename}: {e}")
                for enc in data.get("encounters", []):
                    try:
                        self._encounters.append(Encounter.from_dict(enc))
                    except Exception as e:
                        print(f"[EventSystem] Failed to load encounter in {filename}: {e}")
            except Exception as e:
                print(f"[EventSystem] Failed to open {filename}: {e}")

        print(f"[EventSystem] Loaded {len(self._events)} events, "
              f"{len(self._encounters)} encounters.")

    # -----------------------------------------------------------------------
    # Day queue generation
    # -----------------------------------------------------------------------

    def build_day_queue(self, player: PlayerState,
                        mm: MemoryManager,
                        count: int = None) -> list[Event]:
        """
        Select and return <count> events for today.
        Respects: night_range, prerequisite_memory_tags, previously seen ids,
        and category weighting for the current phase.
        """
        if count is None:
            count = BAL["events_per_day"]

        night    = player.current_night
        eligible = self._eligible_events(player, mm, night)

        if not eligible:
            # Fallback 1: drop cooldown but keep prerequisites + absent-tag checks
            eligible = [
                e for e in self._events
                if e.night_range[0] <= night <= e.night_range[1]
                and (not e.prerequisite_memory_tags or
                     all(mm.find_by_tags(player, [tag])
                         for tag in e.prerequisite_memory_tags))
                and not any(mm.find_by_tags(player, [tag])
                            for tag in e.requires_absent_tags)
            ]

        if not eligible:
            # Fallback 2: only respect night range and absent-tag rules
            eligible = [
                e for e in self._events
                if e.night_range[0] <= night <= e.night_range[1]
                and not any(mm.find_by_tags(player, [tag])
                            for tag in e.requires_absent_tags)
            ]

        # Apply category weighting
        weights  = [self._event_weight(e, night) for e in eligible]
        selected: list[Event] = []  
        ids_used:    set[str] = set()   # prevent same event twice
        titles_used: set[str] = set()   # prevent same memory title twice

        attempts = 0
        while len(selected) < count and attempts < count * 5:
            attempts += 1
            total = sum(w for e, w in zip(eligible, weights) if e.id not in ids_used)
            if total <= 0:
                break
            r = random.uniform(0, total)
            cumulative = 0.0
            for event, weight in zip(eligible, weights):
                if event.id in ids_used:
                    continue
                cumulative += weight
                if r <= cumulative:
                    # Collect all memory titles this event could award
                    event_titles = {
                        c.outcome.memory_reward.title.lower()
                        for c in event.choices
                        if c.outcome.memory_reward
                    }
                    if event_titles & titles_used:
                        # Would duplicate a memory already in today's queue
                        ids_used.add(event.id)  # mark ineligible for this pass
                        break
                    selected.append(event)
                    ids_used.add(event.id)
                    titles_used |= event_titles
                    break

        # Shuffle for variety, but guarantee at least one danger event early on
        random.shuffle(selected)
        return selected

    def _eligible_events(self, player: PlayerState,
                         mm: MemoryManager, night: int) -> list[Event]:
        """Return events that are within night range and meet prerequisites."""
        eligible: list[Event] = []
        # Events seen last night (1-night cooldown to prevent same-day repeat)
        recent_seen = set(player.events_seen[-BAL["events_per_day"]:])

        for event in self._events:
            if not (event.night_range[0] <= night <= event.night_range[1]):
                continue
            # Skip recently-seen events (cooldown), unless we have very few options
            if event.id in recent_seen:
                continue
            # Check prerequisite memories (must HAVE)
            prereqs = event.prerequisite_memory_tags
            if prereqs:
                if not all(mm.find_by_tags(player, [tag]) for tag in prereqs):
                    continue
            # Check absent-tag requirement (must NOT have)
            if event.requires_absent_tags:
                if any(mm.find_by_tags(player, [tag])
                       for tag in event.requires_absent_tags):
                    continue
            eligible.append(event)

        return eligible

    def _event_weight(self, event: Event, night: int) -> float:
        """Compute weight for this event at this night, using phase config."""
        base   = event.weight
        phase  = self._phase_for_night(night)
        cat_weights = _PHASE_CAT_WEIGHTS.get(phase, {})
        category_modifier = cat_weights.get(event.category.value, 1.0)
        return base * category_modifier

    @staticmethod
    def _phase_for_night(night: int) -> str:
        if night <= 3:   return "early"
        if night <= 6:   return "mid1"
        if night <= 9:   return "mid2"
        if night <= 12:  return "late1"
        return "late2"

    # -----------------------------------------------------------------------
    # Encounter selection
    # -----------------------------------------------------------------------

    def get_encounter(self, player: PlayerState,
                       progression=None) -> Optional[Encounter]:
        """Select one encounter appropriate for the current night."""
        night = player.current_night
        eligible = [
            e for e in self._encounters
            if e.night_range[0] <= night <= e.night_range[1]
            and e.id not in player.encounters_seen[-5:]
        ]
        if not eligible:
            eligible = self._encounters  # final fallback

        weights = [e.weight for e in eligible]
        total   = sum(weights)
        if total <= 0:
            return random.choice(self._encounters) if self._encounters else None

        r = random.uniform(0, total)
        cumulative = 0.0
        for enc, w in zip(eligible, weights):
            cumulative += w
            if r <= cumulative:
                return enc
        return eligible[-1]

    # -----------------------------------------------------------------------
    # Outcome processing
    # -----------------------------------------------------------------------

    def get_visible_cues(self, event: Event, player: PlayerState,
                          progression=None) -> list[Cue]:
        """Return the cues the player can perceive, capped by progression phase."""
        max_cues = progression.max_cues_shown(player) if progression else 3
        return list(event.cues[:max_cues])

    def process_choice(self, event: Event, choice: Choice,
                       player: PlayerState) -> ChoiceResult:
        """
        Record the choice and return a ChoiceResult.
        Does NOT apply health change — caller is responsible.
        """
        outcome = choice.outcome
        player.events_seen.append(event.id)

        new_memory: Optional[Memory] = None
        if outcome.memory_reward:
            new_memory = outcome.memory_reward.instantiate(event.id, player.current_night)

        return ChoiceResult(
            outcome_type=outcome.type,
            description=outcome.description,
            health_delta=outcome.health_change,
            memory=new_memory,
        )

    def process_choice_by_id(self, event: Event, choice_id: str,
                              player: PlayerState) -> ChoiceResult:
        """Convenience wrapper that looks up choice by id."""
        choice = next((c for c in event.choices if c.id == choice_id), None)
        if choice is None:
            raise ValueError(f"Choice {choice_id!r} not found in event {event.id!r}")
        return self.process_choice(event, choice, player)

    def get_visible_choices(self, event: Event, player: PlayerState,
                             mm: MemoryManager = None) -> list[Choice]:
        """
        Filter choices to only those the player can see based on their
        current memories and mastery levels.
        """
        visible: list[Choice] = []
        for choice in event.choices:
            if choice.mastery_required > 0 and mm is not None:
                rel = mm.find_by_tags(player, event.tags)
                max_mastery = max((m.mastery_level.value for m in rel), default=0)
                if max_mastery < choice.mastery_required:
                    continue
            visible.append(choice)
        return visible

    def resolve_encounter(self, encounter: Encounter, memory: Optional[Memory],
                           player: PlayerState) -> tuple[str, int, str]:
        """
        Resolve a travel encounter.
        Does NOT apply health change — caller is responsible.
        Returns: (result_type, health_delta, result_description)
        """
        player.encounters_seen.append(encounter.id)

        if memory is None:
            return ("none", encounter.health_on_no_memory, encounter.failure_text)

        # Check if the chosen memory helps or misleads
        mem_tags = (
            [t.lower() for t in memory.traits] +
            [memory.title.lower()] +
            [ct.description.lower() for ct in memory.cue_tags]
        )

        relevant_match  = any(
            any(tag.lower() in mem_tag for mem_tag in mem_tags)
            for tag in encounter.relevant_memory_tags
        )
        mislead_match   = any(
            any(tag.lower() in mem_tag for mem_tag in mem_tags)
            for tag in encounter.misleading_memory_tags
        )

        if memory.is_false:
            # False memory always misleads — caller applies health change
            return ("failure", encounter.health_on_failure,
                    encounter.failure_text + " (A false assumption led you astray.)")

        if relevant_match and not mislead_match:
            if memory.memory_strength >= 0.4 and memory.confidence >= 0.4:
                return ("success", encounter.health_on_success, encounter.success_text)
            else:
                delta = encounter.health_on_failure // 2
                return ("partial", delta, encounter.partial_text)

        elif mislead_match:
            return ("failure", encounter.health_on_failure, encounter.failure_text)

        else:
            delta = encounter.health_on_no_memory // 2
            return ("partial", delta, encounter.partial_text)


# ---------------------------------------------------------------------------
# Phase → category weight tables
# (mirrors data/config.json but loaded here for performance)
# ---------------------------------------------------------------------------
_PHASE_CAT_WEIGHTS: dict[str, dict[str, float]] = {
    "early": {"danger": 2.0, "food": 1.5, "neutral": 1.0, "sensory": 0.5,
              "emotional": 0.5, "ambiguous": 0.2, "contextual": 0.1},
    "mid1":  {"danger": 1.8, "food": 1.5, "neutral": 0.8, "sensory": 1.0,
              "emotional": 1.2, "ambiguous": 0.5, "contextual": 0.5},
    "mid2":  {"danger": 1.5, "food": 1.2, "neutral": 0.6, "sensory": 1.2,
              "emotional": 1.0, "ambiguous": 1.0, "contextual": 1.5},
    "late1": {"danger": 1.2, "food": 1.0, "neutral": 0.5, "sensory": 1.0,
              "emotional": 1.5, "ambiguous": 1.5, "contextual": 2.0},
    "late2": {"danger": 1.0, "food": 1.0, "neutral": 0.5, "sensory": 0.8,
              "emotional": 1.2, "ambiguous": 1.8, "contextual": 2.5},
}
