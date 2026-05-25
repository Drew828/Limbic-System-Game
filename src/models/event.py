# =============================================================================
# models/event.py
# Event and choice data models.
#
# Design rationale:
#   Events are fully data-driven (loaded from JSON) so designers can add
#   content without touching code.  The Python models here are the in-memory
#   representations after deserialisation, with helper methods the day-state
#   calls directly.  Choices carry outcome specs; the event system resolves
#   them into actual game-state mutations.
# =============================================================================

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.models.memory import (
    Memory, MemoryCategory, ContextRule, CueTag, MasteryLevel, MemoryStatus
)


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class SceneType(Enum):
    FOREST   = "forest"
    RIVER    = "river"
    MEADOW   = "meadow"
    CAVE     = "cave"
    VILLAGE  = "village"
    ROAD     = "road"
    CAMP     = "camp"
    RUINS    = "ruins"
    NIGHT    = "night"
    DREAM    = "dream"


class EventCategory(Enum):
    DANGER     = "danger"
    FOOD       = "food"
    NEUTRAL    = "neutral"
    SENSORY    = "sensory"
    EMOTIONAL  = "emotional"
    AMBIGUOUS  = "ambiguous"
    CONTEXTUAL = "contextual"


class OutcomeType(Enum):
    SUCCESS  = "success"
    FAILURE  = "failure"
    NEUTRAL  = "neutral"
    MIXED    = "mixed"


# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------

@dataclass
class Cue:
    """A perceptual cue available in the scene before the player chooses."""
    sense:       str   # "visual", "sound", "smell", "tactile", "contextual"
    description: str
    visible:     bool = True   # Some cues are hidden (revealed by memory/mastery)
    reveal_memory_tag: str = ""  # memory tag required to notice this cue

    def to_dict(self) -> dict:
        return {"sense": self.sense, "description": self.description,
                "visible": self.visible, "reveal_memory_tag": self.reveal_memory_tag}

    @staticmethod
    def from_dict(d: dict) -> "Cue":
        return Cue(sense=d["sense"], description=d["description"],
                   visible=d.get("visible", True),
                   reveal_memory_tag=d.get("reveal_memory_tag", ""))


@dataclass
class MemoryReward:
    """
    Specifies what memory the player may encode after an event.
    This is a template; the memory_manager instantiates the real Memory.
    """
    title:           str
    description:     str
    category:        str = "neutral"
    traits:          list[str] = field(default_factory=list)
    hidden_traits:   list[str] = field(default_factory=list)
    cue_tags:        list[dict] = field(default_factory=list)
    context_rules:   list[dict] = field(default_factory=list)
    emotional_weight: float = 0.0
    confidence:      float = 0.6
    memory_strength: float = 0.5
    uncertainty:     float = 0.4
    reliability:     float = 0.8
    conditions:      dict = field(default_factory=dict)
    merge_hint:      str = ""   # id of memory this might merge with

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}

    @staticmethod
    def from_dict(d: dict) -> "MemoryReward":
        return MemoryReward(
            title=d.get("title", ""),
            description=d.get("description", ""),
            category=d.get("category", "neutral"),
            traits=list(d.get("traits", [])),
            hidden_traits=list(d.get("hidden_traits", [])),
            cue_tags=list(d.get("cue_tags", [])),
            context_rules=list(d.get("context_rules", [])),
            emotional_weight=d.get("emotional_weight", 0.0),
            confidence=d.get("confidence", 0.6),
            memory_strength=d.get("memory_strength", 0.5),
            uncertainty=d.get("uncertainty", 0.4),
            reliability=d.get("reliability", 0.8),
            conditions=dict(d.get("conditions", {})),
            merge_hint=d.get("merge_hint", ""),
        )

    def instantiate(self, event_id: str, night: int) -> Memory:
        """Create a real Memory object from this reward template."""
        m = Memory(
            title=self.title,
            description=self.description,
            category=MemoryCategory(self.category),
            traits=list(self.traits),
            hidden_traits=list(self.hidden_traits),
            emotional_weight=self.emotional_weight,
            confidence=self.confidence,
            memory_strength=self.memory_strength,
            uncertainty=self.uncertainty,
            reliability=self.reliability,
            conditions=dict(self.conditions),
            source_events=[event_id],
            days_seen=[night],
            is_long_term=False,
        )
        for cd in self.cue_tags:
            m.add_cue(CueTag.from_dict(cd))
        for rd in self.context_rules:
            m.add_context_rule(ContextRule.from_dict(rd))
        return m


@dataclass
class Outcome:
    """The result of a player choice."""
    type:           OutcomeType
    description:    str
    health_change:  int = 0
    memory_reward:  MemoryReward | None = None
    reveals_cue:    str = ""    # cue description that becomes visible
    unlocks_tag:    str = ""    # memory tag that gets discovered

    def to_dict(self) -> dict:
        d = {
            "type":          self.type.value,
            "description":   self.description,
            "health_change": self.health_change,
            "reveals_cue":   self.reveals_cue,
            "unlocks_tag":   self.unlocks_tag,
        }
        if self.memory_reward:
            d["memory_reward"] = self.memory_reward.to_dict()
        return d

    @staticmethod
    def from_dict(d: dict) -> "Outcome":
        mr = None
        if "memory_reward" in d and d["memory_reward"]:
            mr = MemoryReward.from_dict(d["memory_reward"])
        return Outcome(
            type=OutcomeType(d.get("type", "neutral")),
            description=d.get("description", ""),
            health_change=d.get("health_change", 0),
            memory_reward=mr,
            reveals_cue=d.get("reveals_cue", ""),
            unlocks_tag=d.get("unlocks_tag", ""),
        )


@dataclass
class Choice:
    """A single player option shown during an event."""
    id:             str
    text:           str
    outcome:        Outcome
    # If a prerequisite_memory_tag is set, this choice only appears
    # (or appears differently) when the player has the matching memory
    prerequisite_memory_tag: str = ""
    # Hidden choices appear only when player has mastery level >= threshold
    mastery_required: int = 0   # 0 = always visible

    def to_dict(self) -> dict:
        return {
            "id":                       self.id,
            "text":                     self.text,
            "outcome":                  self.outcome.to_dict(),
            "prerequisite_memory_tag":  self.prerequisite_memory_tag,
            "mastery_required":         self.mastery_required,
        }

    @staticmethod
    def from_dict(d: dict) -> "Choice":
        return Choice(
            id=d["id"],
            text=d["text"],
            outcome=Outcome.from_dict(d["outcome"]),
            prerequisite_memory_tag=d.get("prerequisite_memory_tag", ""),
            mastery_required=d.get("mastery_required", 0),
        )


@dataclass
class ConditionalVariant:
    """Override parts of an event when specific conditions are met."""
    condition_memory_tag: str    # player must have memory with this tag
    override_description: str = ""
    extra_cues: list[dict] = field(default_factory=list)
    extra_choices: list[dict] = field(default_factory=list)

    @staticmethod
    def from_dict(d: dict) -> "ConditionalVariant":
        return ConditionalVariant(
            condition_memory_tag=d.get("condition_memory_tag", ""),
            override_description=d.get("override_description", ""),
            extra_cues=list(d.get("extra_cues", [])),
            extra_choices=list(d.get("extra_choices", [])),
        )


# ---------------------------------------------------------------------------
# Core Event class
# ---------------------------------------------------------------------------

@dataclass
class Event:
    """
    A fully data-driven game event.  Loaded from JSON; never constructed
    directly in gameplay code.
    """
    id:          str
    title:       str
    description: str
    scene_type:  SceneType
    tags:        list[str]
    cues:        list[Cue]
    choices:     list[Choice]
    category:    EventCategory

    emotional_value:    float = 0.0  # baseline emotional impact
    night_range:        tuple[int, int] = (1, 15)
    weight:             float = 1.0
    prerequisite_memory_tags: list[str] = field(default_factory=list)
    requires_absent_tags:     list[str] = field(default_factory=list)  # event hidden once player knows these
    conditional_variants: list[ConditionalVariant] = field(default_factory=list)
    # Tags that the event reveals if the player has them (strengthens cue associations)
    relation_rules:     list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "title":        self.title,
            "description":  self.description,
            "scene_type":   self.scene_type.value,
            "tags":         list(self.tags),
            "cues":         [c.to_dict() for c in self.cues],
            "choices":      [ch.to_dict() for ch in self.choices],
            "category":     self.category.value,
            "emotional_value": self.emotional_value,
            "night_range":  list(self.night_range),
            "weight":       self.weight,
            "prerequisite_memory_tags": list(self.prerequisite_memory_tags),
            "relation_rules": list(self.relation_rules),
        }

    @staticmethod
    def from_dict(d: dict) -> "Event":
        nr = d.get("night_range", [1, 15])
        return Event(
            id=d["id"],
            title=d["title"],
            description=d["description"],
            scene_type=SceneType(d.get("scene_type", "forest")),
            tags=list(d.get("tags", [])),
            cues=[Cue.from_dict(c) for c in d.get("cues", [])],
            choices=[Choice.from_dict(ch) for ch in d.get("choices", [])],
            category=EventCategory(d.get("category", "neutral")),
            emotional_value=d.get("emotional_value", 0.0),
            night_range=(int(nr[0]), int(nr[1])),
            weight=d.get("weight", 1.0),
            prerequisite_memory_tags=list(d.get("prerequisite_memory_tags", [])),
            requires_absent_tags=list(d.get("requires_absent_tags", [])),
            conditional_variants=[
                ConditionalVariant.from_dict(v)
                for v in d.get("conditional_variants", [])
            ],
            relation_rules=list(d.get("relation_rules", [])),
        )


# ---------------------------------------------------------------------------
# Encounter (Travel phase)
# ---------------------------------------------------------------------------

@dataclass
class Encounter:
    """
    A challenge in the Travel phase that the player resolves using memories.
    Analogous to an Event but resolved via memory recall rather than choice.
    """
    id:          str
    title:       str
    description: str
    scene_type:  SceneType
    tags:        list[str]          # memory tags that are relevant
    relevant_memory_tags: list[str] # specific tags that succeed
    misleading_memory_tags: list[str] = field(default_factory=list)
    success_text: str = "You handle the situation correctly."
    failure_text: str = "Something goes wrong."
    partial_text: str = "You manage, but barely."
    health_on_success: int = 0
    health_on_failure: int = -15
    health_on_no_memory: int = -20
    night_range:  tuple[int, int] = (1, 15)
    weight:       float = 1.0

    @staticmethod
    def from_dict(d: dict) -> "Encounter":
        nr = d.get("night_range", [1, 15])
        return Encounter(
            id=d["id"],
            title=d["title"],
            description=d["description"],
            scene_type=SceneType(d.get("scene_type", "road")),
            tags=list(d.get("tags", [])),
            relevant_memory_tags=list(d.get("relevant_memory_tags", [])),
            misleading_memory_tags=list(d.get("misleading_memory_tags", [])),
            success_text=d.get("success_text", ""),
            failure_text=d.get("failure_text", ""),
            partial_text=d.get("partial_text", ""),
            health_on_success=d.get("health_on_success", 0),
            health_on_failure=d.get("health_on_failure", -15),
            health_on_no_memory=d.get("health_on_no_memory", -20),
            night_range=(int(nr[0]), int(nr[1])),
            weight=d.get("weight", 1.0),
        )
