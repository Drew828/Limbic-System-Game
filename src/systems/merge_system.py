# =============================================================================
# systems/merge_system.py
# Memory merging logic — one of the most important systems in the game.
#
# Five merge types (matching design document):
#   1. Exact     — duplicate memories strengthen each other
#   2. Trait     — related memories combine known traits
#   3. Context   — complementary memories build context rules
#   4. Progressive — repeated exposures reveal hidden properties
#   5. Risky     — premature merge may produce false memory
#
# Design rationale:
#   Merging must feel meaningful, not automatic.  The system detects candidates
#   passively (during night phase) and presents them to the player to decide.
#   The player can decline any merge.  Risky merges show a clear warning.
#   False memories created by merging are a core mechanic — they should feel
#   plausible in hindsight, not arbitrary.
# =============================================================================

from __future__ import annotations
import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

from src.models.memory import Memory, MemoryStatus, ContextRule, CueTag, MergeLink
from src.models.player import PlayerState
from src.constants import BAL


# ---------------------------------------------------------------------------
# Merge type enum and result structures
# ---------------------------------------------------------------------------

class MergeType(Enum):
    EXACT       = "exact"
    TRAIT       = "trait"
    CONTEXT     = "context"
    PROGRESSIVE = "progressive"
    RISKY       = "risky"


@dataclass
class MergeCandidate:
    """A detected pair of memories that could be merged."""
    source_id:  str
    target_id:  str
    merge_type: MergeType
    confidence: float        # How likely this merge is beneficial (0–1)
    risk:       float        # Chance of creating a false memory (0–1)
    description: str         # Human-readable explanation for the UI


@dataclass
class MergeResult:
    """Outcome of performing a merge."""
    merged_memory:    Memory
    is_false:         bool
    false_trait_added: Optional[str]
    description:      str


# ---------------------------------------------------------------------------
# Merge System
# ---------------------------------------------------------------------------

class MergeSystem:
    """Detects and executes memory merges."""

    # Similarity thresholds
    EXACT_TITLE_MATCH   = True
    TRAIT_OVERLAP_MIN   = 2     # minimum shared traits for trait merge
    CONTEXT_HINT_MATCH  = True  # use merge_hint from event data

    def __init__(self) -> None:
        self.false_chance = 0.35   # risky merge false probability

    # -----------------------------------------------------------------------
    # Detection  (called once per night phase)
    # -----------------------------------------------------------------------

    def detect_candidates(self, player: PlayerState) -> list[MergeCandidate]:
        """
        Scan all STM + LTM memories and return merge candidates.
        Called at the start of the Night phase so the player can review them.
        """
        candidates: list[MergeCandidate] = []
        memories   = player.all_memories()

        # Only consider non-fading, non-merged memories
        valid = [m for m in memories
                 if m.status not in (MemoryStatus.FADING, MemoryStatus.MERGED)]

        checked: set[frozenset] = set()
        for i, a in enumerate(valid):
            for b in valid[i+1:]:
                pair = frozenset([a.id, b.id])
                if pair in checked:
                    continue
                checked.add(pair)

                candidate = self._evaluate_pair(a, b)
                if candidate:
                    candidates.append(candidate)

        # Sort by confidence descending
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates

    def _evaluate_pair(self, a: Memory, b: Memory) -> Optional[MergeCandidate]:
        """Evaluate one memory pair and return a MergeCandidate if appropriate."""

        # --- Exact merge: same title ---
        if a.title.lower() == b.title.lower():
            return MergeCandidate(
                source_id=a.id,
                target_id=b.id,
                merge_type=MergeType.EXACT,
                confidence=0.95,
                risk=0.0,
                description=(
                    f'Two memories of "{a.title}". '
                    f'Merging will strengthen both and combine known traits.'
                ),
            )

        # --- Progressive merge: same title keyword in both, one has hidden traits ---
        a_kw = set(a.title.lower().split())
        b_kw = set(b.title.lower().split())
        shared_kw = a_kw & b_kw - {"the","a","an","of","in","at","on","with"}
        if shared_kw and (a.hidden_traits or b.hidden_traits):
            conf = min(0.85, (a.confidence + b.confidence) / 2 + 0.1)
            risk = max(0.0, (a.uncertainty + b.uncertainty) / 2 - 0.2)
            return MergeCandidate(
                source_id=a.id,
                target_id=b.id,
                merge_type=MergeType.PROGRESSIVE,
                confidence=conf,
                risk=risk,
                description=(
                    f'Repeated exposure to "{a.title}" / "{b.title}". '
                    f'Merging may reveal hidden properties.'
                ),
            )

        # --- Trait merge: sufficient overlap in traits ---
        a_traits = set(t.lower() for t in a.traits)
        b_traits = set(t.lower() for t in b.traits)
        overlap  = a_traits & b_traits
        if len(overlap) >= self.TRAIT_OVERLAP_MIN:
            conf = min(0.80, len(overlap) * 0.15 + (a.confidence + b.confidence) * 0.25)
            risk = max(0.0, 0.5 - conf + (a.uncertainty + b.uncertainty) * 0.15)
            return MergeCandidate(
                source_id=a.id,
                target_id=b.id,
                merge_type=MergeType.TRAIT,
                confidence=conf,
                risk=risk,
                description=(
                    f'"{a.title}" and "{b.title}" share traits: '
                    f'{", ".join(list(overlap)[:3])}. Merging may deepen understanding.'
                ),
            )

        # --- Context merge: one memory has merge_hint pointing to related memory ---
        a_hint_matches_b = self._has_context_link(a, b)
        b_hint_matches_a = self._has_context_link(b, a)
        if a_hint_matches_b or b_hint_matches_a:
            src, tgt = (a, b) if a_hint_matches_b else (b, a)
            conf = min(0.75, (src.confidence + tgt.confidence) / 2 + 0.05)
            risk = 0.10 if conf > 0.5 else 0.25
            return MergeCandidate(
                source_id=src.id,
                target_id=tgt.id,
                merge_type=MergeType.CONTEXT,
                confidence=conf,
                risk=risk,
                description=(
                    f'"{src.title}" may provide context for "{tgt.title}". '
                    f'Combining them could reveal new rules.'
                ),
            )

        # --- Risky merge: low confidence pair with some trait overlap ---
        small_overlap = len(overlap) >= 1
        low_conf = a.confidence < 0.4 or b.confidence < 0.4
        if small_overlap and low_conf:
            conf = 0.30
            risk = 0.45
            return MergeCandidate(
                source_id=a.id,
                target_id=b.id,
                merge_type=MergeType.RISKY,
                confidence=conf,
                risk=risk,
                description=(
                    f'Uncertain memories of "{a.title}" and "{b.title}". '
                    f'WARNING: Merging with low confidence risks creating a false memory.'
                ),
            )

        return None

    def _has_context_link(self, source: Memory, target: Memory) -> bool:
        """Check if source memory references target by title keyword."""
        if not source.merge_links:
            return False
        target_lower = target.title.lower()
        for link in source.merge_links:
            if link.target_id == target.id:
                return True
            # Also check by name substring
            if target_lower in link.target_id.lower():
                return True
        return False

    # -----------------------------------------------------------------------
    # Execution  (called when player confirms a merge)
    # -----------------------------------------------------------------------

    def execute_merge(self, player: PlayerState, candidate: MergeCandidate) -> MergeResult:
        """
        Perform the merge described by the candidate.
        Removes the source memory, updates the target memory.
        Returns a MergeResult describing what happened.
        """
        source = player.find_memory(candidate.source_id)
        target = player.find_memory(candidate.target_id)

        if source is None or target is None:
            # Memories may have been removed between detection and execution
            return MergeResult(
                merged_memory=target or Memory(title="Unknown"),
                is_false=False,
                false_trait_added=None,
                description="Merge failed — memory no longer available.",
            )

        # Decide if this merge produces a false memory
        is_false     = False
        false_trait  = None
        if candidate.risk > 0 and random.random() < candidate.risk:
            is_false    = True
            false_trait = self._generate_false_trait(source, target)

        result_memory = self._do_merge(source, target, candidate.merge_type, is_false, false_trait)

        # Remove source from whichever pool it belongs to
        if source.is_long_term:
            player.remove_ltm(source.id)
        else:
            player.remove_stm(source.id)
        source.status = MemoryStatus.MERGED

        # Update target in place
        if result_memory.is_long_term:
            player.add_ltm(result_memory)
        else:
            # Keep in STM (replace)
            for i, m in enumerate(player.short_term):
                if m.id == result_memory.id:
                    player.short_term[i] = result_memory
                    break

        player.merges_performed += 1
        if is_false:
            player.false_memories_formed += 1

        desc = self._build_merge_description(candidate.merge_type, source, result_memory,
                                              is_false, false_trait)
        return MergeResult(
            merged_memory=result_memory,
            is_false=is_false,
            false_trait_added=false_trait,
            description=desc,
        )

    def _do_merge(self, source: Memory, target: Memory,
                  merge_type: MergeType, is_false: bool,
                  false_trait: Optional[str]) -> Memory:
        """Apply the merge mutations to target and return it."""
        # Absorb all source traits that target doesn't have
        for trait in source.traits:
            target.add_trait(trait)

        # Absorb cues
        for cue in source.cue_tags:
            target.add_cue(cue)

        # Absorb context rules
        for rule in source.context_rules:
            if rule.discovered:
                target.add_context_rule(rule)

        # Absorb merge links
        for link in source.merge_links:
            target.link_to(link.target_id, link.relation, link.confidence)

        # Record provenance
        target.merged_from.append(source.id)
        target.source_events.extend(source.source_events)

        # Type-specific boosts
        if merge_type == MergeType.EXACT:
            target.memory_strength = min(1.0, target.memory_strength + 0.25)
            target.confidence      = min(1.0, target.confidence + 0.15)
            target.uncertainty     = max(0.0, target.uncertainty - 0.15)

        elif merge_type in (MergeType.TRAIT, MergeType.PROGRESSIVE):
            target.memory_strength = min(1.0, target.memory_strength + 0.15)
            target.confidence      = min(1.0, target.confidence + 0.10)
            target.uncertainty     = max(0.0, target.uncertainty - 0.10)
            # Progressive: reveal one hidden trait
            if merge_type == MergeType.PROGRESSIVE and target.hidden_traits:
                revealed = target.reveal_hidden_trait()
                # (revealed trait is now in target.traits)

        elif merge_type == MergeType.CONTEXT:
            # Absorb hidden context rules from source
            for rule in source.context_rules:
                rule.discovered = True
                target.add_context_rule(rule)
            target.confidence      = min(1.0, target.confidence + 0.12)
            target.uncertainty     = max(0.0, target.uncertainty - 0.12)

        elif merge_type == MergeType.RISKY:
            target.memory_strength = min(1.0, target.memory_strength + 0.08)
            # Less confidence gain for risky merge
            target.confidence      = min(0.85, target.confidence + 0.05)

        # False memory injection
        if is_false and false_trait:
            target.traits.append(false_trait)
            target.is_false = True
            target.reliability = max(0.0, target.reliability - 0.25)
            # Don't tell the player it's false — that's the point

        target._update_mastery()
        return target

    def _generate_false_trait(self, source: Memory, target: Memory) -> str:
        """
        Generate a plausible-but-wrong trait for the false memory.
        It should sound reasonable — that's what makes it dangerous.
        """
        # Use the 'most confident' trait from the weaker memory
        # combined with the strongest known rule of the other
        false_pools = [
            # Overgeneralisation patterns
            f"always safe when {'near' if 'dangerous' in ' '.join(target.traits) else 'far from'} {source.title.lower()}",
            f"all {target.title.lower().split()[0]}s behave the same way",
            f"safe to approach if {source.title.lower()} is not present",
            f"{target.title} and {source.title} follow the same rules",
            f"no danger during daytime",
        ]
        return random.choice(false_pools)

    def _build_merge_description(self, merge_type: MergeType, source: Memory,
                                  result: Memory, is_false: bool,
                                  false_trait: Optional[str]) -> str:
        base = {
            MergeType.EXACT:       f'Memories of "{result.title}" combined. Strength increased.',
            MergeType.TRAIT:       f'Related knowledge merged. "{result.title}" now carries deeper traits.',
            MergeType.CONTEXT:     f'Context unlocked. "{result.title}" now includes new conditional rules.',
            MergeType.PROGRESSIVE: f'Repeated exposure revealed. A hidden property of "{result.title}" is now known.',
            MergeType.RISKY:       f'Memories combined under uncertainty.',
        }[merge_type]

        if is_false:
            return base + f' [The merge feels complete — but something may have been misunderstood.]'
        return base
