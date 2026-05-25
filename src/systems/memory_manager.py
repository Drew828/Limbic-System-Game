# =============================================================================
# systems/memory_manager.py
# All read/write operations on the memory stores.
#
# Design rationale:
#   Nothing outside this module mutates player.short_term or player.long_term
#   directly (except serialisation).  This keeps memory logic centralised:
#   decay, reinforcement, conflict detection, and the STM→LTM promotion flow
#   all have a single authoritative implementation here.
# =============================================================================

from __future__ import annotations
import random
from typing import Optional

from src.models.memory import Memory, MemoryCategory, MemoryStatus, MasteryLevel
from src.models.player import PlayerState
from src.constants import BAL


class MemoryManager:
    """
    Manages all memory operations for a single player session.
    Stateless beyond holding a reference to player_state.
    """

    def __init__(self) -> None:
        pass

    # -----------------------------------------------------------------------
    # Encoding  (Day phase)
    # -----------------------------------------------------------------------

    def can_encode(self, player: PlayerState) -> bool:
        return not player.stm_full

    def encode(self, player: PlayerState, memory: Memory) -> bool:
        """
        Add a new memory to STM.  Returns False if STM is full.
        The caller must handle the STM-full case by asking the player
        which existing memory to drop.
        Applies cortisol effect and spaced-repetition bonus automatically.
        """
        if not self.can_encode(player):
            return False

        # --- Cortisol effect (high stress = impaired encoding) ---
        # High cortisol (low health) weakens non-emotional memories and
        # hyper-encodes emotional/threatening ones (amygdala hijack).
        if player.health <= BAL["cortisol_threshold"]:
            if abs(memory.emotional_weight) > 0.3:
                memory.memory_strength = min(
                    1.0,
                    memory.memory_strength + BAL["cortisol_emotional_boost"] * 0.1)
            else:
                memory.memory_strength = max(
                    0.05,
                    memory.memory_strength * (1.0 - BAL["cortisol_encode_penalty"] * 0.5))

        # --- Spaced repetition bonus ---
        # If the player already has an LTM version of this memory and it has
        # not been reinforced for several nights, the re-encounter triggers a
        # spaced-repetition boost on the LTM trace.
        existing_ltm = self._find_ltm_by_title(player, memory.title)
        if existing_ltm is not None:
            gap = player.current_night - existing_ltm.last_reinforced
            if gap >= BAL["spaced_rep_gap"]:
                existing_ltm.reinforce(
                    BAL["spaced_rep_bonus"] * 2, night=player.current_night)

        memory.days_seen.append(player.current_night)
        player.add_stm(memory)
        return True

    def replace_stm(self, player: PlayerState, drop_id: str, new_memory: Memory) -> bool:
        """
        Drop an STM memory and insert a new one.
        Used when STM is at capacity and player wants to encode something new.
        """
        dropped = player.remove_stm(drop_id)
        if dropped is None:
            return False
        new_memory.days_seen.append(player.current_night)
        player.add_stm(new_memory)
        return True

    def reinforce_existing(self, player: PlayerState, memory_id: str, boost: float = None) -> bool:
        """
        Boost an existing memory (from repeat encounter).
        Searches both STM and LTM.
        """
        if boost is None:
            boost = BAL["repeat_exposure_boost"]
        m = player.find_memory(memory_id)
        if m is None:
            return False
        m.reinforce(boost, night=player.current_night)
        return True

    def find_by_title(self, player: PlayerState, title: str) -> Optional[Memory]:
        """Fuzzy match by title (case-insensitive, substring)."""
        title_lower = title.lower()
        for m in player.all_memories():
            if title_lower in m.title.lower():
                return m
        return None

    def find_by_tags(self, player: PlayerState, tags: list[str]) -> list[Memory]:
        """Return all memories whose traits or cue descriptions match any tag."""
        results = []
        for m in player.all_memories():
            for tag in tags:
                tag_l = tag.lower()
                # Match against traits
                if any(tag_l in t.lower() for t in m.traits):
                    results.append(m)
                    break
                # Match against cue descriptions
                if any(tag_l in ct.description.lower() for ct in m.cue_tags):
                    results.append(m)
                    break
                # Match against title
                if tag_l in m.title.lower():
                    results.append(m)
                    break
        return results

    # -----------------------------------------------------------------------
    # Night Phase  (decay, consolidation, dream replay)
    # -----------------------------------------------------------------------

    def apply_nightly_decay(self, player: PlayerState, progression=None) -> list[Memory]:
        """
        Decay all non-consolidated STM memories.
        Ebbinghaus forgetting curve: freshly encoded memories decay fastest;
        memories that have "survived" multiple nights lose strength more slowly.
        Returns list of memories that have faded below threshold.
        """
        base_rate   = progression.decay_rate(player) if progression else BAL["memory_decay_per_night"]
        emot_resist = BAL["emotional_decay_resist"]
        faded: list[Memory] = []

        # Ebbinghaus multipliers indexed by nights since last reinforcement
        _ebbinghaus = [
            BAL["decay_fresh_mult"],       # 0 nights = freshly encoded
            BAL["decay_one_night_mult"],    # 1 night old
            BAL["decay_two_nights_mult"],   # 2 nights old
            BAL["decay_old_mult"],          # 3+ nights old
        ]

        for m in list(player.short_term):
            nights_since = max(0, player.current_night - m.last_reinforced)
            mult = _ebbinghaus[min(nights_since, 3)]
            m.decay(base_rate * mult, emot_resist)
            if m.memory_strength <= 0.05:
                m.status = MemoryStatus.FADING
                faded.append(m)

        return faded

    def purge_faded_stm(self, player: PlayerState) -> list[Memory]:
        """Remove all STM memories at or below strength 0.05. Returns removed list."""
        removed = [m for m in player.short_term if m.memory_strength <= 0.05]
        for m in removed:
            player.short_term.remove(m)
        return removed

    def consolidate(self, player: PlayerState, memory_id: str) -> tuple[Optional[Memory], bool]:
        """
        Probabilistically move a STM memory to LTM.
        Returns (Memory, True) on success, (None, False) on failure.
        Even on failure the memory is partially reinforced (it tried to consolidate).
        Danger-category and mnemonic memories have better odds.
        """
        m = player.find_memory(memory_id)
        if m is None or m.is_long_term:
            return (None, False)

        # --- Probabilistic consolidation ---
        # Based on memory strength and confidence; higher-quality traces succeed more.
        base_chance = BAL["ltm_base_chance"]
        chance = min(0.95, base_chance * (0.5 + m.memory_strength * 0.3 + m.confidence * 0.3))
        if m.category == MemoryCategory.DANGER:
            chance = min(0.95, chance + BAL["ltm_danger_bonus"])
        if m.has_mnemonic:
            chance = min(0.95, chance + BAL["ltm_mnemonic_bonus"])

        boost = BAL["consolidation_boost"]
        # Partial reinforce even on a failure (the attempt still exercises the trace)
        m.reinforce(boost * 0.4, night=player.current_night)

        if random.random() > chance:
            # Consolidation failed — memory remains in STM but slightly stronger
            return (None, False)

        # Full reinforce on success
        m.reinforce(boost * 0.6, night=player.current_night)

        # Check if an existing LTM memory has the same title → merge/reinforce
        existing = self._find_ltm_by_title(player, m.title)
        if existing:
            existing.reinforce(boost * 0.6, night=player.current_night)
            existing.exposure_count += 1
            for trait in m.traits:
                existing.add_trait(trait)
            for cue in m.cue_tags:
                existing.add_cue(cue)
            for rule in m.context_rules:
                existing.add_context_rule(rule)
            player.remove_stm(memory_id)
            return (existing, True)

        player.promote_to_ltm(memory_id)
        return (m, True)

    def dream_replay(self, player: PlayerState) -> Optional[Memory]:
        """
        Select one STM memory to dream-reinforce (random, weighted by emotional_weight).
        Returns the memory that was replayed.
        """
        candidates = [m for m in player.short_term
                      if m.status not in (MemoryStatus.FADING, MemoryStatus.MERGED)]
        if not candidates:
            return None

        weights = [0.3 + abs(m.emotional_weight) + m.memory_strength for m in candidates]
        total = sum(weights)
        r = random.uniform(0, total)
        cumulative = 0.0
        chosen = candidates[-1]
        for m, w in zip(candidates, weights):
            cumulative += w
            if r <= cumulative:
                chosen = m
                break

        chosen.reinforce(0.12, night=player.current_night)
        chosen.status = MemoryStatus.DREAM
        return chosen

    def clear_dream_status(self, player: PlayerState) -> None:
        """Remove the DREAM status after animation completes."""
        for m in player.short_term:
            if m.status == MemoryStatus.DREAM:
                m.status = MemoryStatus.ACTIVE

    def reveal_hidden_trait_on_encounter(self, player: PlayerState, memory_id: str) -> Optional[str]:
        """
        When a player encounters something related to a memory,
        reveal one hidden trait if confidence is high enough.
        """
        m = player.find_memory(memory_id)
        if m and m.confidence >= 0.6 and m.hidden_traits:
            return m.reveal_hidden_trait()
        return None

    # -----------------------------------------------------------------------
    # Interference, Reconsolidation, and Cortisol  (new mechanics)
    # -----------------------------------------------------------------------

    def apply_interference(self, player: PlayerState, new_memory: Memory) -> list[Memory]:
        """
        Proactive/retroactive interference: similar memories compete for storage.
        Memories that share 2+ traits with new_memory lose confidence, and so
        does new_memory itself. Returns the list of interfered memories.
        """
        penalty    = BAL["interference_penalty"]
        interfered = []
        for m in player.all_memories():
            if m.id == new_memory.id:
                continue
            overlap = sum(1 for t in new_memory.traits if t in m.traits)
            if overlap >= 2:
                m.confidence       = max(0.0, m.confidence - penalty)
                new_memory.confidence = max(0.0, new_memory.confidence - penalty)
                interfered.append(m)
        return interfered

    def apply_reconsolidation(
        self, memory: Memory, current_night: int
    ) -> bool:
        """
        Each time a memory is retrieved and used it re-enters an unstable
        (labile) state — reconsolidation.  This slightly lowers confidence
        and occasionally distorts a trait (the memory updates with new context
        but may drift from the original).
        Returns True if a trait was mutated.
        """
        memory.confidence = max(
            0.0, memory.confidence - BAL["reconsolidation_conf_drop"])
        if (memory.traits
                and random.random() < BAL["reconsolidation_mutate_chance"]):
            # Drop one random known trait (the trace was subtly altered)
            memory.traits.pop(random.randrange(len(memory.traits)))
            return True
        return False

    # -----------------------------------------------------------------------
    # Utility
    # -----------------------------------------------------------------------

    def get_stm_memories(self, player: PlayerState) -> list[Memory]:
        return list(player.short_term)

    def get_ltm_memories(self, player: PlayerState) -> list[Memory]:
        return list(player.long_term)

    def get_all_memories(self, player: PlayerState) -> list[Memory]:
        return player.all_memories()

    def _find_ltm_by_title(self, player: PlayerState, title: str) -> Optional[Memory]:
        title_l = title.lower()
        for m in player.long_term:
            if m.title.lower() == title_l:
                return m
        return None

    def get_relevant_memories_for_encounter(self, player: PlayerState, tags: list[str]) -> list[Memory]:
        """
        Return all memories (STM + LTM) that are relevant to an encounter
        defined by the given tags, sorted by relevance score.
        """
        scored: list[tuple[float, Memory]] = []
        for m in player.all_memories():
            if m.status == MemoryStatus.FADING:
                continue
            score = self._relevance_score(m, tags)
            if score > 0:
                scored.append((score, m))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored]

    def _relevance_score(self, memory: Memory, tags: list[str]) -> float:
        score = 0.0
        for tag in tags:
            tag_l = tag.lower()
            if tag_l in memory.title.lower():
                score += 2.0
            if any(tag_l in t.lower() for t in memory.traits):
                score += 1.5
            if any(tag_l in ct.description.lower() for ct in memory.cue_tags):
                score += 1.0
        # Weight by memory quality
        score *= memory.memory_strength * memory.confidence
        # Penalise false memories (they look relevant but lead to wrong action)
        if memory.is_false:
            score *= 0.5
        return score
