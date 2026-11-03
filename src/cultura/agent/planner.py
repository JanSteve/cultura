"""
CULTURA Autonomous ReAct Agent Planner.
Synthesizes conflict-free 48-hour cultural itineraries across global cultural hubs
enforcing diurnal slot suitability, spatial transit limits (<=45 min),
anti-clumping domain diversity (>=4 domains), and automated conflict backtracking.
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, Tuple, Union

if TYPE_CHECKING:
    from cultura.client.qloo import QlooClient

from cultura.agent.tools import (
    AffinityScore,
    CulturalDomain,
    CulturalEntity,
    ItineraryItem,
    ItineraryPlan,
    TasteSeed,
    TimeSlot,
    haversine_transit_minutes,
)
from cultura.client.mock_data import calculate_affinity

logger = logging.getLogger("cultura.agent.planner")


# ============================================================================
# 1. Conflict Hierarchy
# ============================================================================

class PlannerConflict(Exception):
    """Base class for all itinerary planning conflicts."""
    pass


class DiurnalSlotConflict(PlannerConflict):
    """Raised when candidate domain violates operating diurnal hours."""

    def __init__(self, slot: TimeSlot, domain: CulturalDomain, reason: str = ""):
        msg = f"Diurnal conflict in {slot.value}: domain '{domain.value}' disallowed"
        if reason:
            msg += f" ({reason})"
        super().__init__(msg)
        self.slot = slot
        self.domain = domain
        self.reason = reason


class DuplicateVenueConflict(PlannerConflict):
    """Raised when candidate venue has already been assigned in itinerary."""

    def __init__(self, entity_id: str, name: str = ""):
        super().__init__(f"Duplicate venue conflict: '{name or entity_id}' already scheduled")
        self.entity_id = entity_id
        self.name = name


class DomainClumpingConflict(PlannerConflict):
    """Raised when candidate domain matches domain of adjacent slot."""

    def __init__(self, domain: CulturalDomain, prev_slot: int):
        super().__init__(f"Domain clumping conflict: domain '{domain.value}' repeats consecutive slot {prev_slot}")
        self.domain = domain
        self.prev_slot = prev_slot


class TransitExcessConflict(PlannerConflict):
    """Raised when travel time between venues exceeds maximum allowed minutes."""

    def __init__(self, transit_min: int, max_allowed: int = 45):
        super().__init__(f"Spatial transit conflict: transit time {transit_min}m exceeds maximum {max_allowed}m")
        self.transit_min = transit_min
        self.max_allowed = max_allowed


class DomainStarvationConflict(PlannerConflict):
    """Raised when remaining slots cannot satisfy minimum unique domain invariant."""

    def __init__(self, current_unique: int, remaining_slots: int, required: int = 4):
        super().__init__(
            f"Domain starvation: {current_unique} unique domains with {remaining_slots} slots left cannot reach {required}"
        )
        self.current_unique = current_unique
        self.remaining_slots = remaining_slots
        self.required = required


# ============================================================================
# 2. ReAct States & Trace Models
# ============================================================================

class ReActState(str, Enum):
    """5-State ReAct transitions for autonomous cultural curation."""
    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"
    REFLECTION = "reflection"
    SYNTHESIS = "synthesis"


class ReActStep:
    """An individual execution record in the ReAct planning trajectory."""

    def __init__(
        self,
        step: int,
        state: Union[ReActState, str],
        slot: Optional[str] = None,
        thought: Optional[str] = None,
        action: Optional[str] = None,
        tool: Optional[str] = None,
        tool_input: Optional[Dict[str, Any]] = None,
        observation: Optional[str] = None,
        reflection: Optional[str] = None,
        conflict_detected: Optional[str] = None,
        backtrack_occurred: bool = False,
        content: Optional[str] = None,
    ) -> None:
        self.step = step
        self.state = state.value if isinstance(state, ReActState) else str(state)
        self.slot = slot
        self.thought = thought
        self.action = action
        self.tool = tool or action
        self.tool_input = tool_input
        self.observation = observation
        self.reflection = reflection
        self.conflict_detected = conflict_detected
        self.backtrack_occurred = backtrack_occurred
        self.content = content or thought or reflection or observation or ""
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Converts step record to JSON-serializable dictionary."""
        d: Dict[str, Any] = {
            "step": self.step,
            "state": self.state,
            "slot": self.slot,
            "thought": self.thought,
            "action": self.action,
            "tool": self.tool,
            "tool_input": self.tool_input,
            "observation": self.observation,
            "reflection": self.reflection,
            "conflict_detected": self.conflict_detected,
            "backtrack_occurred": self.backtrack_occurred,
            "content": self.content,
            "timestamp": self.timestamp,
        }
        return {k: v for k, v in d.items() if v is not None}


# ============================================================================
# 3. Diurnal Rules & Mathematical Formulations
# ============================================================================

class DiurnalRules:
    """Diurnal slot permissions and suitability weights."""

    SCHEDULE_STRUCTURE: List[Tuple[int, TimeSlot]] = [
        (1, TimeSlot.MORNING),
        (1, TimeSlot.AFTERNOON),
        (1, TimeSlot.EVENING),
        (1, TimeSlot.NIGHT),
        (2, TimeSlot.MORNING),
        (2, TimeSlot.AFTERNOON),
        (2, TimeSlot.EVENING),
        (2, TimeSlot.NIGHT),
    ]

    ALLOWED_DOMAINS: Dict[TimeSlot, List[CulturalDomain]] = {
        TimeSlot.MORNING: [
            CulturalDomain.DINING,
            CulturalDomain.LITERARY,
            CulturalDomain.ARTS,
            CulturalDomain.FASHION,
        ],
        TimeSlot.AFTERNOON: [
            CulturalDomain.ARTS,
            CulturalDomain.DINING,
            CulturalDomain.LITERARY,
            CulturalDomain.CINEMA,
            CulturalDomain.FASHION,
        ],
        TimeSlot.EVENING: [
            CulturalDomain.DINING,
            CulturalDomain.CINEMA,
            CulturalDomain.MUSIC,
            CulturalDomain.ARTS,
            CulturalDomain.NIGHTLIFE,
        ],
        TimeSlot.NIGHT: [
            CulturalDomain.NIGHTLIFE,
            CulturalDomain.MUSIC,
            CulturalDomain.CINEMA,
            CulturalDomain.DINING,
        ],
    }

    SUITABILITY_WEIGHTS: Dict[TimeSlot, Dict[CulturalDomain, float]] = {
        TimeSlot.MORNING: {
            CulturalDomain.DINING: 1.0,
            CulturalDomain.LITERARY: 0.95,
            CulturalDomain.ARTS: 0.90,
            CulturalDomain.FASHION: 0.85,
        },
        TimeSlot.AFTERNOON: {
            CulturalDomain.ARTS: 1.0,
            CulturalDomain.DINING: 0.95,
            CulturalDomain.LITERARY: 0.90,
            CulturalDomain.FASHION: 0.90,
            CulturalDomain.CINEMA: 0.85,
        },
        TimeSlot.EVENING: {
            CulturalDomain.DINING: 1.0,
            CulturalDomain.CINEMA: 0.95,
            CulturalDomain.MUSIC: 0.95,
            CulturalDomain.ARTS: 0.85,
            CulturalDomain.NIGHTLIFE: 0.80,
        },
        TimeSlot.NIGHT: {
            CulturalDomain.NIGHTLIFE: 1.0,
            CulturalDomain.MUSIC: 1.0,
            CulturalDomain.CINEMA: 0.80,
            CulturalDomain.DINING: 0.75,
        },
    }

    @classmethod
    def is_allowed(cls, slot: TimeSlot, domain: CulturalDomain) -> bool:
        return domain in cls.ALLOWED_DOMAINS.get(slot, [])

    @classmethod
    def get_weight(cls, slot: TimeSlot, domain: CulturalDomain) -> float:
        return cls.SUITABILITY_WEIGHTS.get(slot, {}).get(domain, 0.5)


def calculate_cultural_coherence_score(
    items: List[ItineraryItem],
    taste_seeds: List[TasteSeed],
) -> float:
    """
    Computes cultural_coherence_score in [0.0, 1.0] synthesizing:
    - 50% Normalized seed resonance (average affinity_score across 8 items)
    - 30% Sequential transition harmony (adjacent pairwise affinity + Jaccard tag similarity)
    - 20% Global aesthetic motif density (proportion of tags appearing in >=2 venues)
    """
    if not items or len(items) != 8:
        raise ValueError(f"Expected exactly 8 items, got {len(items)}")

    # 1. Seed Resonance
    seed_resonance = sum(item.affinity_score for item in items) / 8.0

    # 2. Sequential Transition Harmony across the 7 adjacent pairs
    transition_scores: List[float] = []
    for i in range(len(items) - 1):
        e_curr = items[i].entity
        e_next = items[i + 1].entity
        aff = calculate_affinity(e_curr, e_next)["score"]

        tags_curr = set(t.strip().lower() for t in e_curr.vibe_tags)
        tags_next = set(t.strip().lower() for t in e_next.vibe_tags)
        union_tags = tags_curr.union(tags_next)
        jaccard = len(tags_curr.intersection(tags_next)) / max(1, len(union_tags))

        harmonic_pair = 0.85 * aff + 0.15 * max(aff, jaccard)
        transition_scores.append(harmonic_pair)

    seq_harmony = sum(transition_scores) / max(1, len(transition_scores))

    # 3. Global Aesthetic Motif Density
    tag_counts: Dict[str, int] = {}
    for item in items:
        for tag in item.entity.vibe_tags:
            clean_tag = tag.strip().lower()
            tag_counts[clean_tag] = tag_counts.get(clean_tag, 0) + 1

    total_tag_instances = sum(tag_counts.values())
    if total_tag_instances == 0:
        motif_density = 0.50
    else:
        recurring_instances = sum(count for count in tag_counts.values() if count >= 2)
        vibe_density = recurring_instances / total_tag_instances
        motif_density = 0.50 + 0.50 * vibe_density

    composite = (
        0.50 * seed_resonance +
        0.30 * seq_harmony +
        0.20 * motif_density
    )
    return round(min(1.0, max(0.0, composite)), 3)


def calculate_domain_diversity_score(
    items: List[ItineraryItem],
) -> float:
    """
    Computes domain_diversity_score in [0.0, 1.0] using:
    - Discrete normalized Shannon entropy: H(D) / 2.75 bits
    - Domain clumping penalty: -0.05 per adjacent identical domain collision
    """
    if not items or len(items) != 8:
        raise ValueError(f"Expected exactly 8 items, got {len(items)}")

    domain_counts: Dict[CulturalDomain, int] = {}
    for item in items:
        d = item.entity.domain
        domain_counts[d] = domain_counts.get(d, 0) + 1

    entropy = 0.0
    for count in domain_counts.values():
        p = count / 8.0
        entropy -= p * math.log2(p)

    h_max_discrete = 2.75  # Optimal integer partition (2, 1, 1, 1, 1, 1, 1)
    normalized_entropy = entropy / h_max_discrete

    clumps = 0
    for i in range(len(items) - 1):
        if items[i].entity.domain == items[i + 1].entity.domain:
            clumps += 1

    clump_penalty = 0.05 * clumps
    score = normalized_entropy - clump_penalty
    return round(min(1.0, max(0.0, score)), 3)


def calculate_transit_efficiency_score(
    items: List[ItineraryItem],
) -> float:
    """
    Computes transit_efficiency_score in [0.0, 1.0] using:
    - Tripartite piecewise efficiency per leg (15m optimal, 15-45m linear, >45m steep penalty)
    - Penalty cliff of -0.20 for each leg exceeding 45 minutes
    """
    if not items or len(items) != 8:
        raise ValueError(f"Expected exactly 8 items, got {len(items)}")

    leg_scores: List[float] = []
    excess_count = 0

    # Evaluate the 7 transition legs (indices 1 to 7)
    for i in range(1, len(items)):
        t = items[i].transit_from_previous_min
        if t <= 15:
            leg_phi = 1.00
        elif t <= 45:
            leg_phi = 1.00 - 0.40 * ((t - 15) / 30.0)
        else:
            excess_count += 1
            leg_phi = max(0.0, 0.60 - 1.20 * ((t - 45) / 45.0))
        leg_scores.append(leg_phi)

    mean_phi = sum(leg_scores) / 7.0
    excess_penalty = 0.20 * excess_count
    score = mean_phi - excess_penalty
    return round(min(1.0, max(0.0, score)), 3)


# ============================================================================
# 4. Autonomous ReAct Planner Implementation
# ============================================================================

class ReActPlanner:
    """
    Autonomous ReAct Agent Planner for CULTURA.
    Synthesizes conflict-free 48-hour itineraries across 8 cultural hubs using
    Qloo taste graph affinities, diurnal temporal constraints, Haversine spatial
    routing, anti-clumping diversity (>=4 domains), and automated backtracking.
    """

    def __init__(
        self,
        client: Optional[QlooClient] = None,
        max_transit_minutes: int = 45,
        max_backtracks: int = 50,
        speed_kmh: float = 25.0,
    ) -> None:
        if client is None:
            from cultura.client.qloo import QlooClient

            self.client = QlooClient()
        else:
            self.client = client
        self.max_transit_minutes = max_transit_minutes
        self.max_backtracks = max_backtracks
        self.speed_kmh = speed_kmh

    async def plan_48h(
        self,
        city_hub: str,
        taste_seeds: List[TasteSeed],
        **kwargs: Any,
    ) -> ItineraryPlan:
        """
        Executes the autonomous 5-state ReAct planning loop and returns a validated ItineraryPlan.
        """
        if not taste_seeds:
            raise ValueError("At least one taste seed must be supplied to plan_48h.")

        clean_hub = city_hub.strip()
        if not clean_hub:
            raise ValueError("Destination cultural hub cannot be blank.")

        react_trace: List[ReActStep] = []
        step_counter = 0

        # --------------------------------------------------------------------
        # Phase 1: Multi-Tier Taste Seed Resolution
        # --------------------------------------------------------------------
        step_counter += 1
        seed_names = ", ".join(f"{s.name} ({s.domain.value})" for s in taste_seeds)
        react_trace.append(
            ReActStep(
                step=step_counter,
                state=ReActState.THOUGHT,
                thought=f"Resolving {len(taste_seeds)} taste seed(s) [{seed_names}] against Qloo taste graph for {clean_hub}.",
            )
        )

        step_counter += 1
        react_trace.append(
            ReActStep(
                step=step_counter,
                state=ReActState.ACTION,
                action="resolve_taste_seed_anchors",
                tool="search_entities",
                tool_input={"city_hub": clean_hub, "seeds_count": len(taste_seeds)},
            )
        )

        anchors = await self._resolve_taste_seed_anchors(clean_hub, taste_seeds)
        if not anchors:
            raise ValueError(f"Unable to resolve taste seeds for cultural hub '{clean_hub}'.")

        step_counter += 1
        anchor_summary = ", ".join(f"{a.name} [{a.domain.value}]" for a in anchors)
        react_trace.append(
            ReActStep(
                step=step_counter,
                state=ReActState.OBSERVATION,
                observation=f"Successfully anchored {len(anchors)} entity/entities in {clean_hub}: {anchor_summary}.",
            )
        )

        # --------------------------------------------------------------------
        # Phase 2: 8-Slot Depth-First Search with Forward Checking & Backtracking
        # --------------------------------------------------------------------
        scheduled: List[ItineraryItem] = []
        backtrack_count = 0

        # Calculate seed domain influence weights
        seed_weight_map: Dict[CulturalDomain, float] = {}
        for s in taste_seeds:
            seed_weight_map[s.domain] = seed_weight_map.get(s.domain, 0.0) + s.weight

        async def solve_slot(slot_idx: int) -> bool:
            nonlocal step_counter, backtrack_count

            if slot_idx == 8:
                # Terminal condition: verify global diversity >= 4 domains
                unique_domains = {item.entity.domain for item in scheduled}
                return len(unique_domains) >= 4

            day, slot = DiurnalRules.SCHEDULE_STRUCTURE[slot_idx]
            slot_label = f"Day {day} {slot.value.capitalize()}"
            prev_item = scheduled[-1] if scheduled else None
            prev_domain = prev_item.entity.domain if prev_item else None
            prev_entity = prev_item.entity if prev_item else None
            used_ids: Set[str] = {item.entity.id for item in scheduled}
            visited_domains: Set[CulturalDomain] = {item.entity.domain for item in scheduled}

            # Select active seed anchor
            active_anchor = anchors[slot_idx % len(anchors)]

            # 2a. THOUGHT
            step_counter += 1
            react_trace.append(
                ReActStep(
                    step=step_counter,
                    state=ReActState.THOUGHT,
                    slot=slot_label,
                    thought=(
                        f"Curating {slot_label}. Diurnal slot {slot.value}. "
                        f"Previous domain: {prev_domain.value if prev_domain else 'None'}. "
                        f"Avoiding domain clumping while targeting >= 4 unique domains. "
                        f"Resonating from anchor {active_anchor.name}."
                    ),
                )
            )

            # Determine candidate domains for this slot
            allowed_domains = list(DiurnalRules.ALLOWED_DOMAINS[slot])

            # Anti-clumping pre-filter: exclude previous domain
            target_domains = [d for d in allowed_domains if d != prev_domain]

            # Domain diversity prioritization:
            # 1. Boost unvisited domains if diversity needs expansion
            # 2. Boost domains matching user taste seeds proportional to seed weight
            def domain_priority_key(d: CulturalDomain) -> float:
                suitability = DiurnalRules.get_weight(slot, d)
                unvisited_boost = 0.25 if d not in visited_domains else 0.0
                seed_boost = 0.20 * seed_weight_map.get(d, 0.0)
                return suitability + unvisited_boost + seed_boost

            target_domains.sort(key=domain_priority_key, reverse=True)

            # 2b. ACTION: Query affinities across target domains
            step_counter += 1
            react_trace.append(
                ReActStep(
                    step=step_counter,
                    state=ReActState.ACTION,
                    slot=slot_label,
                    action=f"get_cross_domain_affinities(source='{active_anchor.name}', target_domains={[d.value for d in target_domains]})",
                    tool="get_cross_domain_affinities",
                    tool_input={
                        "source_entity_id": active_anchor.id,
                        "target_domains": [d.value for d in target_domains],
                        "hub": clean_hub,
                    },
                )
            )

            candidate_pool = await self._fetch_candidates_for_domains(
                source_entity=active_anchor,
                target_domains=target_domains,
                hub=clean_hub,
                slot=slot,
                seed_weight_map=seed_weight_map,
            )

            # 2c. OBSERVATION
            step_counter += 1
            react_trace.append(
                ReActStep(
                    step=step_counter,
                    state=ReActState.OBSERVATION,
                    slot=slot_label,
                    observation=f"Retrieved {len(candidate_pool)} candidate venue(s) across {len(target_domains)} domains for {slot_label}.",
                )
            )

            # 2d. REFLECTION: Evaluate candidates sequentially
            for cand, composite_score, raw_score, rationale in candidate_pool:
                # Check 1: Duplicate venue conflict
                if cand.id in used_ids:
                    backtrack_count += 1
                    step_counter += 1
                    react_trace.append(
                        ReActStep(
                            step=step_counter,
                            state=ReActState.REFLECTION,
                            slot=slot_label,
                            reflection=f"DuplicateVenueConflict: Venue '{cand.name}' already visited in itinerary. Discarding.",
                            conflict_detected="duplicate_venue",
                            backtrack_occurred=True,
                        )
                    )
                    continue

                # Check 2: Diurnal hard constraint
                if not DiurnalRules.is_allowed(slot, cand.domain):
                    backtrack_count += 1
                    step_counter += 1
                    react_trace.append(
                        ReActStep(
                            step=step_counter,
                            state=ReActState.REFLECTION,
                            slot=slot_label,
                            reflection=f"DiurnalSlotConflict: '{cand.name}' ({cand.domain.value}) not suitable for {slot.value}. Discarding.",
                            conflict_detected="diurnal_disallowed",
                            backtrack_occurred=True,
                        )
                    )
                    continue

                # Check 3: Domain clumping conflict (adjacent identical domain)
                if prev_domain and cand.domain == prev_domain:
                    backtrack_count += 1
                    step_counter += 1
                    react_trace.append(
                        ReActStep(
                            step=step_counter,
                            state=ReActState.REFLECTION,
                            slot=slot_label,
                            reflection=f"DomainClumpingConflict: '{cand.name}' ({cand.domain.value}) repeats consecutive domain. Discarding.",
                            conflict_detected="domain_clumping",
                            backtrack_occurred=True,
                        )
                    )
                    continue

                # Check 4: Spatial transit constraint (<= 45 min)
                transit_min = 0
                if slot_idx == 0:
                    transit_min = 0  # Starting point
                else:
                    ref_entity = prev_entity or active_anchor
                    transit_min = haversine_transit_minutes(
                        ref_entity.latitude,
                        ref_entity.longitude,
                        cand.latitude,
                        cand.longitude,
                        speed_kmh=self.speed_kmh,
                    )
                    if transit_min > self.max_transit_minutes:
                        backtrack_count += 1
                        step_counter += 1
                        react_trace.append(
                            ReActStep(
                                step=step_counter,
                                state=ReActState.REFLECTION,
                                slot=slot_label,
                                reflection=f"TransitExcessConflict: Transit from {ref_entity.name} to {cand.name} is {transit_min}m (> 45m). Discarding.",
                                conflict_detected="transit_exceeded",
                                backtrack_occurred=True,
                            )
                        )
                        continue

                # Check 5: Domain distribution cap (no single domain > 3 slots)
                current_domain_count = sum(1 for item in scheduled if item.entity.domain == cand.domain)
                if current_domain_count >= 3:
                    continue

                # Check 6: Domain starvation lookahead
                future_unique = len(visited_domains | {cand.domain})
                remaining_slots = 7 - slot_idx
                if future_unique + remaining_slots < 4:
                    backtrack_count += 1
                    step_counter += 1
                    react_trace.append(
                        ReActStep(
                            step=step_counter,
                            state=ReActState.REFLECTION,
                            slot=slot_label,
                            reflection=f"DomainStarvationConflict: Selecting {cand.domain.value} would prevent reaching >= 4 unique domains. Discarding.",
                            conflict_detected="domain_starvation",
                            backtrack_occurred=True,
                        )
                    )
                    continue

                # All constraints satisfied: Commit candidate
                item = ItineraryItem(
                    day=day,
                    slot=slot,
                    time_window=slot.default_time_window,
                    entity=cand,
                    affinity_score=round(raw_score, 3),
                    curator_notes=rationale,
                    transit_from_previous_min=transit_min,
                )
                scheduled.append(item)

                step_counter += 1
                react_trace.append(
                    ReActStep(
                        step=step_counter,
                        state=ReActState.REFLECTION,
                        slot=slot_label,
                        reflection=f"Committed '{cand.name}' ({cand.domain.value}) for {slot_label}. Transit: {transit_min}m, Affinity: {raw_score:.2f}.",
                        backtrack_occurred=False,
                    )
                )

                # Recursively solve next diurnal slot
                if await solve_slot(slot_idx + 1):
                    return True

                # Chronological backtrack: Pop and explore alternative
                scheduled.pop()
                backtrack_count += 1
                step_counter += 1
                react_trace.append(
                    ReActStep(
                        step=step_counter,
                        state=ReActState.REFLECTION,
                        slot=slot_label,
                        reflection=f"Downstream deadlock from '{cand.name}'. Backtracking and exploring alternative candidate.",
                        conflict_detected="downstream_deadlock",
                        backtrack_occurred=True,
                    )
                )

                if backtrack_count > self.max_backtracks:
                    raise RuntimeError(
                        f"Planning failed to converge for hub '{clean_hub}' within {self.max_backtracks} backtracks."
                    )

            return False

        # Execute search
        success = await solve_slot(0)
        if not success or len(scheduled) != 8:
            raise RuntimeError(f"ReAct planner failed to synthesize a valid 8-slot plan for hub '{clean_hub}'.")

        # --------------------------------------------------------------------
        # Phase 3: Plan Synthesis & Exact Mathematical Scoring
        # --------------------------------------------------------------------
        step_counter += 1
        react_trace.append(
            ReActStep(
                step=step_counter,
                state=ReActState.SYNTHESIS,
                thought="Synthesizing final ItineraryPlan: computing cultural coherence, Shannon entropy diversity, and transit efficiency.",
            )
        )

        coherence = calculate_cultural_coherence_score(scheduled, taste_seeds)
        diversity = calculate_domain_diversity_score(scheduled)
        transit_eff = calculate_transit_efficiency_score(scheduled)
        summary = self._generate_executive_summary(clean_hub, scheduled, taste_seeds)

        plan = ItineraryPlan(
            city_hub=clean_hub,
            taste_seeds=taste_seeds,
            items=scheduled,
            cultural_coherence_score=coherence,
            domain_diversity_score=diversity,
            transit_efficiency_score=transit_eff,
            react_steps_count=len(react_trace),
            summary=summary,
            metadata={
                "react_trace": [s.to_dict() for s in react_trace],
                "backtrack_count": backtrack_count,
                "domains_covered": sorted(list({item.entity.domain.value for item in scheduled})),
                "resolved_anchors": [a.id for a in anchors],
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            },
        )
        return plan

    # ------------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------------

    async def _resolve_taste_seed_anchors(
        self,
        hub: str,
        taste_seeds: List[TasteSeed],
    ) -> List[CulturalEntity]:
        """Resolves user taste seeds against QlooClient catalog into anchor entities."""
        anchors: List[CulturalEntity] = []

        for seed in taste_seeds:
            # Tier 1: Local entity name and domain search in hub
            matches = await self.client.search_entities(query=seed.name, domain=seed.domain, hub=hub, limit=5)
            if matches:
                anchors.append(matches[0])
                continue

            # Tier 2: Vibe tag / keyword search in hub
            matches = await self.client.search_entities(query=seed.name, hub=hub, limit=5)
            if matches:
                anchors.append(matches[0])
                continue

            # Tier 3: Global entity match across any hub
            matches = await self.client.search_entities(query=seed.name, domain=seed.domain, hub=None, limit=5)
            if matches:
                anchors.append(matches[0])
                continue

            # Tier 4: Signature hub domain fallback
            hub_entities = await self.client.get_hub_entities(hub=hub, domain=seed.domain)
            if hub_entities:
                anchors.append(hub_entities[0])
                continue

            # Tier 5: Signature hub general fallback
            all_hub = await self.client.get_hub_entities(hub=hub)
            if all_hub:
                anchors.append(all_hub[0])

        if not anchors:
            all_hub = await self.client.get_hub_entities(hub=hub)
            if all_hub:
                anchors.append(all_hub[0])

        return anchors

    async def _fetch_candidates_for_domains(
        self,
        source_entity: CulturalEntity,
        target_domains: List[CulturalDomain],
        hub: str,
        slot: TimeSlot,
        seed_weight_map: Dict[CulturalDomain, float],
    ) -> List[Tuple[CulturalEntity, float, float, str]]:
        """
        Retrieves and ranks candidate entities across target domains using Qloo cross-domain affinities.
        Returns list of (entity, composite_score, raw_affinity_score, rationale).
        """
        candidates: List[Tuple[CulturalEntity, float, float, str]] = []
        seen_cand_ids: Set[str] = set()

        for domain in target_domains:
            affinities = await self.client.get_cross_domain_affinities(
                entity_id=source_entity.id,
                target_domain=domain,
                hub=hub,
                limit=5,
            )

            # If affinities return candidates
            for aff in affinities:
                if aff.target_entity.id not in seen_cand_ids:
                    seen_cand_ids.add(aff.target_entity.id)
                    weight = DiurnalRules.get_weight(slot, domain)
                    seed_boost = 0.15 * seed_weight_map.get(domain, 0.0)
                    composite_score = aff.score * weight + seed_boost
                    raw_score = min(1.0, max(0.0, aff.score))
                    candidates.append((aff.target_entity, composite_score, raw_score, aff.rationale))

            # Complement with direct hub entities in domain if needed
            hub_entities = await self.client.get_hub_entities(hub=hub, domain=domain)
            for he in hub_entities:
                if he.id not in seen_cand_ids:
                    seen_cand_ids.add(he.id)
                    aff_data = calculate_affinity(source_entity, he)
                    weight = DiurnalRules.get_weight(slot, domain)
                    seed_boost = 0.15 * seed_weight_map.get(domain, 0.0)
                    composite_score = aff_data["score"] * weight + seed_boost
                    raw_score = min(1.0, max(0.0, aff_data["score"]))
                    candidates.append((he, composite_score, raw_score, aff_data["rationale"]))

        # Sort descending by composite score, tie-breaking deterministically by entity id
        candidates.sort(key=lambda x: (-x[1], x[0].id))
        return candidates

    def _generate_executive_summary(
        self,
        hub: str,
        schedule: List[ItineraryItem],
        seeds: List[TasteSeed],
    ) -> str:
        """Synthesizes narrative editorial summary for the 48-hour plan."""
        seed_str = ", ".join(f"'{s.name}'" for s in seeds)
        domains = sorted(list({item.entity.domain.value for item in schedule}))
        return (
            f"Curated 48-hour cultural journey across {hub} inspired by {seed_str}. "
            f"Spanning {len(domains)} distinct cultural domains ({', '.join(domains)}) across 8 diurnal slots, "
            f"balancing atmospheric resonance with seamless spatial progression."
        )

    # Backward compatibility alias
    plan = plan_48h

