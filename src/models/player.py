# =============================================================================
# models/player.py
# All mutable player state — health, current night, active memories, flags.
#
# Design rationale:
#   PlayerState is the single source of truth for everything that can change
#   during a run.  Keeping it here (separate from systems) means:
#   - Save/load only needs to serialise this one object
#   - Systems never carry hidden mutable state
#   - UI can read health/night/memories from a single place
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from src.models.memory import Memory
from src.constants import BAL


@dataclass
class PlayerState:
    """
    Everything that changes during a playthrough.
    Both short-term and long-term memory collections live here.
    """
    # Meta
    current_night:      int  = 1
    current_day_event:  int  = 0    # index 0-9 into today's event list

    # Vitality
    health:     int = BAL["travel_health_start"]
    health_max: int = BAL["travel_health_max"]

    # Memory stores
    # short_term: cleared/decayed each night (max 7 by default)
    short_term:  list[Memory] = field(default_factory=list)
    # long_term: persistent across nights
    long_term:   list[Memory] = field(default_factory=list)

    # Tracking
    events_seen:      list[str] = field(default_factory=list)   # event ids
    encounters_seen:  list[str] = field(default_factory=list)   # encounter ids
    memories_encoded: int  = 0
    false_memories_formed: int = 0
    merges_performed: int  = 0

    # Flags
    game_over:   bool = False
    victory:     bool = False

    # -----------------------------------------------------------------------
    # Derived helpers
    # -----------------------------------------------------------------------

    @property
    def health_fraction(self) -> float:
        return max(0.0, self.health / self.health_max)

    @property
    def stm_full(self) -> bool:
        return sum(2 if m.has_mnemonic else 1 for m in self.short_term) >= BAL["stm_capacity"]

    @property
    def stm_count(self) -> int:
        return sum(2 if m.has_mnemonic else 1 for m in self.short_term)

    @property
    def stm_capacity(self) -> int:
        return BAL["stm_capacity"]

    def all_memories(self) -> list[Memory]:
        return self.short_term + self.long_term

    def find_memory(self, memory_id: str) -> Memory | None:
        for m in self.all_memories():
            if m.id == memory_id:
                return m
        return None

    def has_memory_tag(self, tag: str) -> bool:
        """Return True if any active memory carries the given tag."""
        for m in self.all_memories():
            if tag in m.cue_tags or tag in m.traits or tag == m.title.lower():
                return True
        return False

    def has_memory_with_tag(self, tag: str) -> bool:
        """Check cue_tags (CueTag objects or plain strings) and traits."""
        for m in self.all_memories():
            for ct in m.cue_tags:
                if hasattr(ct, "description"):
                    if tag.lower() in ct.description.lower():
                        return True
                elif tag.lower() in str(ct).lower():
                    return True
            if any(tag.lower() in t.lower() for t in m.traits):
                return True
        return False

    def memories_with_tag(self, tag: str) -> list[Memory]:
        results = []
        for m in self.all_memories():
            if any(tag.lower() in t.lower() for t in m.traits):
                results.append(m)
        return results

    # -----------------------------------------------------------------------
    # Health
    # -----------------------------------------------------------------------

    def change_health(self, delta: int) -> int:
        """Apply delta; clamp to [0, health_max]. Returns actual change."""
        old = self.health
        self.health = max(0, min(self.health_max, self.health + delta))
        if self.health <= 0:
            self.game_over = True
        return self.health - old

    # -----------------------------------------------------------------------
    # Memory operations (low-level; MemoryManager wraps these)
    # -----------------------------------------------------------------------

    def add_stm(self, memory: Memory) -> bool:
        """Add to STM. Returns False if full."""
        if self.stm_full:
            return False
        memory.is_long_term = False
        self.short_term.append(memory)
        self.memories_encoded += 1
        return True

    def remove_stm(self, memory_id: str) -> Memory | None:
        for i, m in enumerate(self.short_term):
            if m.id == memory_id:
                return self.short_term.pop(i)
        return None

    def promote_to_ltm(self, memory_id: str) -> bool:
        """Move a STM memory to LTM. Returns True on success."""
        m = self.remove_stm(memory_id)
        if m is None:
            return False
        m.is_long_term = True
        self.long_term.append(m)
        return True

    def add_ltm(self, memory: Memory) -> None:
        """Directly add (or update) a memory in LTM (used during merges)."""
        memory.is_long_term = True
        # Replace if ID already exists
        for i, m in enumerate(self.long_term):
            if m.id == memory.id:
                self.long_term[i] = memory
                return
        self.long_term.append(memory)

    def remove_ltm(self, memory_id: str) -> Memory | None:
        for i, m in enumerate(self.long_term):
            if m.id == memory_id:
                return self.long_term.pop(i)
        return None

    # -----------------------------------------------------------------------
    # Serialisation
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "current_night":        self.current_night,
            "current_day_event":    self.current_day_event,
            "health":               self.health,
            "health_max":           self.health_max,
            "short_term":           [m.to_dict() for m in self.short_term],
            "long_term":            [m.to_dict() for m in self.long_term],
            "events_seen":          list(self.events_seen),
            "encounters_seen":      list(self.encounters_seen),
            "memories_encoded":     self.memories_encoded,
            "false_memories_formed": self.false_memories_formed,
            "merges_performed":     self.merges_performed,
            "game_over":            self.game_over,
            "victory":              self.victory,
        }

    @staticmethod
    def from_dict(d: dict) -> "PlayerState":
        ps = PlayerState(
            current_night=d.get("current_night", 1),
            current_day_event=d.get("current_day_event", 0),
            health=d.get("health", BAL["travel_health_start"]),
            health_max=d.get("health_max", BAL["travel_health_max"]),
            short_term=[Memory.from_dict(m) for m in d.get("short_term", [])],
            long_term=[Memory.from_dict(m) for m in d.get("long_term", [])],
            events_seen=list(d.get("events_seen", [])),
            encounters_seen=list(d.get("encounters_seen", [])),
            memories_encoded=d.get("memories_encoded", 0),
            false_memories_formed=d.get("false_memories_formed", 0),
            merges_performed=d.get("merges_performed", 0),
            game_over=d.get("game_over", False),
            victory=d.get("victory", False),
        )
        return ps
