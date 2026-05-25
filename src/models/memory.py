# =============================================================================
# models/memory.py
# The core Memory data model — the most important class in the entire game.
#
# Design rationale:
#   A memory is not a simple label.  It carries uncertainty, emotional colour,
#   context rules, exposure history, merge lineage, and mastery level.
#   Everything the UI, merge system, and encounter resolver reads comes from
#   this object — so it must be rich, serialisable, and self-describing.
# =============================================================================

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any
from src.constants import BAL


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class MemoryCategory(Enum):
    DANGER     = "danger"
    FOOD       = "food"
    NEUTRAL    = "neutral"
    SENSORY    = "sensory"
    EMOTIONAL  = "emotional"
    AMBIGUOUS  = "ambiguous"
    CONTEXTUAL = "contextual"
    TOOL       = "tool"
    PERSON     = "person"
    PLACE      = "place"


class MemoryStatus(Enum):
    """Runtime status that drives rendering and system behaviour."""
    ACTIVE    = "active"       # healthy, usable
    FADING    = "fading"       # low strength, will decay next night
    FALSE     = "false"        # bad merge produced a false memory
    UNCERTAIN = "uncertain"    # low confidence, may be wrong
    MERGED    = "merged"       # consumed into another memory (soft-deleted)
    DREAM     = "dream"        # currently being dream-replayed (cosmetic)


class MasteryLevel(Enum):
    """Represents depth of understanding, not just recall count."""
    LABEL       = 0   # "Bear = danger"
    PATTERN     = 1   # "Bears are dangerous animals"
    CONTEXTUAL  = 2   # "Bears are dangerous in forests"
    RELATIONAL  = 3   # "Bears are dangerous when approached at night"
    MASTERY     = 4   # "Growling + claw marks = nearby bear; back away slowly"


# ---------------------------------------------------------------------------
# Sub-structures
# ---------------------------------------------------------------------------

@dataclass
class ContextRule:
    """
    A conditional modifier on memory meaning.
    Example: condition="proximity", value="close", modifier="dangerous"
    means: this thing is dangerous when close.
    """
    condition: str           # e.g. "proximity", "time_of_day", "weather", "with"
    value: str               # e.g. "close", "night", "rain", "honey"
    modifier: str            # e.g. "dangerous", "safe", "flee", "edible"
    confidence: float = 0.5  # how sure we are this rule is correct (0–1)
    discovered: bool = False # has the player revealed this rule yet?

    def to_dict(self) -> dict:
        return {
            "condition":  self.condition,
            "value":      self.value,
            "modifier":   self.modifier,
            "confidence": self.confidence,
            "discovered": self.discovered,
        }

    @staticmethod
    def from_dict(d: dict) -> "ContextRule":
        return ContextRule(
            condition=d["condition"], value=d["value"],
            modifier=d["modifier"],   confidence=d.get("confidence", 0.5),
            discovered=d.get("discovered", False),
        )


@dataclass
class CueTag:
    """A retrieval cue — something that triggers recall of this memory."""
    sense:       str   # "visual", "sound", "smell", "tactile", "contextual"
    description: str   # e.g. "low growling sound", "claw marks on bark"
    reliability: float = 0.8  # how reliably this cue triggers recall (0–1)

    def to_dict(self) -> dict:
        return {"sense": self.sense, "description": self.description,
                "reliability": self.reliability}

    @staticmethod
    def from_dict(d: dict) -> "CueTag":
        return CueTag(sense=d["sense"], description=d["description"],
                      reliability=d.get("reliability", 0.8))


@dataclass
class MergeLink:
    """Records a relationship to another memory for the knowledge graph."""
    target_id:    str   # memory id of the related memory
    relation:     str   # e.g. "warns_of", "requires", "contradicts", "source_of"
    confidence:   float = 0.5

    def to_dict(self) -> dict:
        return {"target_id": self.target_id, "relation": self.relation,
                "confidence": self.confidence}

    @staticmethod
    def from_dict(d: dict) -> "MergeLink":
        return MergeLink(target_id=d["target_id"], relation=d["relation"],
                         confidence=d.get("confidence", 0.5))


# ---------------------------------------------------------------------------
# Core Memory class
# ---------------------------------------------------------------------------

@dataclass
class Memory:
    """
    Full memory object.  Everything the game knows about one concept or
    experience lives here.  Both STM and LTM share this class; is_long_term
    distinguishes storage tier.
    """
    # Identity
    id:              str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title:           str = ""
    description:     str = ""

    # Classification
    category:        MemoryCategory = MemoryCategory.NEUTRAL
    status:          MemoryStatus   = MemoryStatus.ACTIVE

    # Knowledge state
    traits:          list[str] = field(default_factory=list)  # known traits
    hidden_traits:   list[str] = field(default_factory=list)  # undiscovered traits
    context_rules:   list[ContextRule] = field(default_factory=list)
    cue_tags:        list[CueTag]      = field(default_factory=list)
    merge_links:     list[MergeLink]   = field(default_factory=list)
    conditions:      dict[str, Any]    = field(default_factory=dict)

    # Quantitative state
    confidence:      float = 0.5   # 0–1: how certain the player feels
    emotional_weight: float = 0.0  # –1 (fear/aversion) … +1 (joy/attraction)
    memory_strength: float = 0.5   # 0–1: decays each night if not consolidated
    uncertainty:     float = 0.5   # 0–1: inverse of confidence (kept separate
                                   #      because they can diverge after false merges)
    reliability:     float = 0.8   # 0–1: true accuracy (hidden from player)

    # Exposure / mastery
    exposure_count:  int   = 1
    mastery_level:   MasteryLevel = MasteryLevel.LABEL
    days_seen:       list[int] = field(default_factory=list)
    last_reinforced: int   = 0     # night number

    # Storage tier
    is_long_term:    bool  = False
    is_false:        bool  = False  # a false memory the player believes is true

    # Memory type and encoding meta
    memory_type:     str  = "episodic"  # "episodic" | "semantic"
    has_mnemonic:    bool = False        # encoded with a vivid mnemonic cue
    scene_formed_in: str  = ""           # SceneType.value at time of encoding

    # Provenance
    source_events:   list[str] = field(default_factory=list)  # event ids
    merged_from:     list[str] = field(default_factory=list)  # source memory ids

    # -----------------------------------------------------------------------
    # Derived helpers
    # -----------------------------------------------------------------------

    @property
    def is_emotional(self) -> bool:
        return abs(self.emotional_weight) > 0.4

    @property
    def is_uncertain(self) -> bool:
        return self.uncertainty > 0.6 or self.confidence < 0.35

    @property
    def is_fading(self) -> bool:
        return self.memory_strength < 0.25

    @property
    def effective_strength(self) -> float:
        """Adjusted strength: emotional memories resist decay."""
        if self.is_emotional:
            return min(1.0, self.memory_strength * (1.0 + 0.3 * abs(self.emotional_weight)))
        return self.memory_strength

    @property
    def mastery_label(self) -> str:
        return {
            MasteryLevel.LABEL:      "Label",
            MasteryLevel.PATTERN:    "Pattern",
            MasteryLevel.CONTEXTUAL: "Contextual",
            MasteryLevel.RELATIONAL: "Relational",
            MasteryLevel.MASTERY:    "Mastery",
        }[self.mastery_level]

    def discovered_context_rules(self) -> list[ContextRule]:
        return [r for r in self.context_rules if r.discovered]

    def undiscovered_context_rules(self) -> list[ContextRule]:
        return [r for r in self.context_rules if not r.discovered]

    # -----------------------------------------------------------------------
    # Mutation helpers  (all mutations go through these to stay auditable)
    # -----------------------------------------------------------------------

    def reinforce(self, boost: float = 0.15, night: int = 0) -> None:
        """Strengthen this memory (from repetition or consolidation)."""
        self.memory_strength = min(1.0, self.memory_strength + boost)
        self.confidence       = min(1.0, self.confidence + boost * 0.5)
        self.uncertainty      = max(0.0, self.uncertainty - boost * 0.4)
        self.exposure_count  += 1
        self.last_reinforced  = night
        self._update_mastery()
        # Episodic → semantic graduation: enough reinforcement consolidates a
        # general rule (semantic) from repeated specific episodes.
        if (self.memory_type == "episodic"
                and self.exposure_count >= BAL["semantic_graduation_threshold"]
                and self.confidence >= 0.75):
            self.memory_type = "semantic"

    def decay(self, rate: float, emotional_resist: float = 0.4) -> None:
        """Weaken this memory (nightly decay of unprotected STM)."""
        # Semantic memories represent stable general knowledge — they don't decay.
        if self.memory_type == "semantic":
            return
        # Mnemonic encoding anchors the trace — decay is greatly reduced.
        if self.has_mnemonic:
            rate *= BAL["mnemonic_decay_mult"]
        effective_rate = rate * (1.0 - emotional_resist * abs(self.emotional_weight))
        self.memory_strength = max(0.0, self.memory_strength - effective_rate)
        if self.memory_strength < 0.1:
            self.status = MemoryStatus.FADING

    def add_trait(self, trait: str) -> None:
        if trait not in self.traits:
            self.traits.append(trait)

    def reveal_hidden_trait(self) -> str | None:
        """Reveal one hidden trait (returns the revealed trait or None)."""
        if self.hidden_traits:
            trait = self.hidden_traits.pop(0)
            self.traits.append(trait)
            return trait
        return None

    def add_context_rule(self, rule: ContextRule) -> None:
        # Avoid exact duplicates
        for existing in self.context_rules:
            if existing.condition == rule.condition and existing.value == rule.value:
                existing.confidence = max(existing.confidence, rule.confidence)
                return
        self.context_rules.append(rule)

    def add_cue(self, cue: CueTag) -> None:
        for existing in self.cue_tags:
            if existing.description == cue.description:
                existing.reliability = max(existing.reliability, cue.reliability)
                return
        self.cue_tags.append(cue)

    def link_to(self, target_id: str, relation: str, confidence: float = 0.5) -> None:
        for link in self.merge_links:
            if link.target_id == target_id:
                link.confidence = max(link.confidence, confidence)
                return
        self.merge_links.append(MergeLink(target_id, relation, confidence))

    def _update_mastery(self) -> None:
        discovered = len(self.discovered_context_rules())
        n = self.exposure_count
        if n >= 5 and discovered >= 3:
            self.mastery_level = MasteryLevel.MASTERY
        elif n >= 4 and discovered >= 2:
            self.mastery_level = MasteryLevel.RELATIONAL
        elif n >= 3 and discovered >= 1:
            self.mastery_level = MasteryLevel.CONTEXTUAL
        elif n >= 2:
            self.mastery_level = MasteryLevel.PATTERN
        else:
            self.mastery_level = MasteryLevel.LABEL

    # -----------------------------------------------------------------------
    # Serialisation
    # -----------------------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "title":            self.title,
            "description":      self.description,
            "category":         self.category.value,
            "status":           self.status.value,
            "traits":           list(self.traits),
            "hidden_traits":    list(self.hidden_traits),
            "context_rules":    [r.to_dict() for r in self.context_rules],
            "cue_tags":         [c.to_dict() for c in self.cue_tags],
            "merge_links":      [m.to_dict() for m in self.merge_links],
            "conditions":       dict(self.conditions),
            "confidence":       self.confidence,
            "emotional_weight": self.emotional_weight,
            "memory_strength":  self.memory_strength,
            "uncertainty":      self.uncertainty,
            "reliability":      self.reliability,
            "exposure_count":   self.exposure_count,
            "mastery_level":    self.mastery_level.value,
            "days_seen":        list(self.days_seen),
            "last_reinforced":  self.last_reinforced,
            "is_long_term":     self.is_long_term,
            "is_false":         self.is_false,
            "memory_type":      self.memory_type,
            "has_mnemonic":     self.has_mnemonic,
            "scene_formed_in":  self.scene_formed_in,
            "source_events":    list(self.source_events),
            "merged_from":      list(self.merged_from),
        }

    @staticmethod
    def from_dict(d: dict) -> "Memory":
        m = Memory(
            id=d.get("id", str(uuid.uuid4())[:8]),
            title=d.get("title", ""),
            description=d.get("description", ""),
            category=MemoryCategory(d.get("category", "neutral")),
            status=MemoryStatus(d.get("status", "active")),
            traits=list(d.get("traits", [])),
            hidden_traits=list(d.get("hidden_traits", [])),
            context_rules=[ContextRule.from_dict(r) for r in d.get("context_rules", [])],
            cue_tags=[CueTag.from_dict(c) for c in d.get("cue_tags", [])],
            merge_links=[MergeLink.from_dict(ml) for ml in d.get("merge_links", [])],
            conditions=dict(d.get("conditions", {})),
            confidence=d.get("confidence", 0.5),
            emotional_weight=d.get("emotional_weight", 0.0),
            memory_strength=d.get("memory_strength", 0.5),
            uncertainty=d.get("uncertainty", 0.5),
            reliability=d.get("reliability", 0.8),
            exposure_count=d.get("exposure_count", 1),
            mastery_level=MasteryLevel(d.get("mastery_level", 0)),
            days_seen=list(d.get("days_seen", [])),
            last_reinforced=d.get("last_reinforced", 0),
            is_long_term=d.get("is_long_term", False),
            is_false=d.get("is_false", False),
            memory_type=d.get("memory_type", "episodic"),
            has_mnemonic=d.get("has_mnemonic", False),
            scene_formed_in=d.get("scene_formed_in", ""),
            source_events=list(d.get("source_events", [])),
            merged_from=list(d.get("merged_from", [])),
        )
        return m

    def __repr__(self) -> str:
        return (f"Memory({self.id!r}, {self.title!r}, "
                f"str={self.memory_strength:.2f}, ltm={self.is_long_term})")
