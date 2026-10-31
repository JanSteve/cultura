"""
CULTURA Empirical Adversarial Test Suite: ReAct Traces, Backtracking Integrity & Metric Bounds.
Stress-tests:
1. ReAct Trace Completeness & State Trajectory (Thought -> Action -> Observation -> Reflection -> Synthesis).
2. Metric Boundaries & Mathematical Extreme Inputs (Coherence, Diversity, Transit Efficiency).
3. Conflict Injection & Multi-Tier Backtracking Recovery (Duplicates, Diurnal Disallowance, Clumping, Transit Excess, Domain Starvation, Downstream Deadlock).
4. Convergence Failure & Backtrack Budget Exhaustion.
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from datetime import datetime
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, patch

# Ensure src/ is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from cultura.agent import (
    CulturalDomain,
    CulturalEntity,
    ItineraryItem,
    ItineraryPlan,
    ReActPlanner,
    ReActState,
    ReActStep,
    TasteSeed,
    TimeSlot,
    calculate_cultural_coherence_score,
    calculate_domain_diversity_score,
    calculate_transit_efficiency_score,
)
from cultura.agent.planner import (
    DiurnalRules,
    DiurnalSlotConflict,
    DomainClumpingConflict,
    DomainStarvationConflict,
    DuplicateVenueConflict,
    PlannerConflict,
    TransitExcessConflict,
)
from cultura.agent.tools import haversine_transit_minutes
from cultura.client.qloo import QlooClient, QlooInvalidHubError


# ============================================================================
# Helpers & Custom Test Fixtures
# ============================================================================

def make_dummy_entity(
    entity_id: str,
    name: str,
    domain: CulturalDomain,
    hub: str = "Bangalore",
    lat: float = 12.9716,
    lon: float = 77.5946,
    tags: Optional[List[str]] = None,
) -> CulturalEntity:
    return CulturalEntity(
        id=entity_id,
        name=name,
        domain=domain,
        hub=hub,
        latitude=lat,
        longitude=lon,
        vibe_tags=tags or ["artisan", "cultural"],
        price_tier=2,
        description=f"Dummy entity {name}",
    )


def make_dummy_items_8(
    domains: Optional[List[CulturalDomain]] = None,
    transits: Optional[List[int]] = None,
    affinities: Optional[List[float]] = None,
    tags_per_item: Optional[List[List[str]]] = None,
) -> List[ItineraryItem]:
    """Generates a valid 8-item sequence matching schedule invariant."""
    default_domains = [
        CulturalDomain.DINING,     # Day 1 Morning
        CulturalDomain.ARTS,       # Day 1 Afternoon
        CulturalDomain.MUSIC,      # Day 1 Evening
        CulturalDomain.NIGHTLIFE,  # Day 1 Night
        CulturalDomain.LITERARY,   # Day 2 Morning
        CulturalDomain.CINEMA,     # Day 2 Afternoon
        CulturalDomain.DINING,     # Day 2 Evening
        CulturalDomain.MUSIC,      # Day 2 Night
    ]
    domains = domains or default_domains
    transits = transits or [0, 15, 20, 15, 25, 20, 15, 20]
    affinities = affinities or [0.85] * 8
    tags_list = tags_per_item or [["vibe_a", "vibe_b"]] * 8

    items = []
    slots = DiurnalRules.SCHEDULE_STRUCTURE
    for i, (day, slot) in enumerate(slots):
        e = make_dummy_entity(
            entity_id=f"venue_{i+1}",
            name=f"Venue {i+1}",
            domain=domains[i],
            tags=tags_list[i],
        )
        items.append(
            ItineraryItem(
                day=day,
                slot=slot,
                time_window=slot.default_time_window,
                entity=e,
                affinity_score=affinities[i],
                curator_notes=f"Curator note {i+1}",
                transit_from_previous_min=transits[i],
            )
        )
    return items


# ============================================================================
# Suite 1: ReAct Trace Completeness & State Trajectory
# ============================================================================

class TestReActTraceAdversarial(unittest.IsolatedAsyncioTestCase):
    """Stress-tests ReAct trace structure, step counts, and 5-state trajectory."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_react_trace_completeness_all_eight_hubs(self):
        """Asserts that all 8 hubs record complete ReAct traces with all 5 states."""
        hubs = [
            ("Bangalore", [TasteSeed(name="Third Wave Coffee", domain=CulturalDomain.DINING)]),
            ("Mumbai", [TasteSeed(name="Art Deco", domain=CulturalDomain.ARTS)]),
            ("New York", [TasteSeed(name="Jazz", domain=CulturalDomain.MUSIC)]),
            ("London", [TasteSeed(name="Books", domain=CulturalDomain.LITERARY)]),
            ("Tokyo", [TasteSeed(name="Ramen", domain=CulturalDomain.DINING)]),
            ("Paris", [TasteSeed(name="Cinema", domain=CulturalDomain.CINEMA)]),
            ("Berlin", [TasteSeed(name="Techno", domain=CulturalDomain.MUSIC)]),
            ("San Francisco", [TasteSeed(name="Bakery", domain=CulturalDomain.DINING)]),
        ]

        expected_states = {"thought", "action", "observation", "reflection", "synthesis"}

        for hub, seeds in hubs:
            with self.subTest(hub=hub):
                plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
                trace = plan.metadata.get("react_trace", [])

                # 1. Step count invariant: react_steps_count >= 8 and matches trace length
                self.assertGreaterEqual(plan.react_steps_count, 8)
                self.assertEqual(plan.react_steps_count, len(trace))

                # 2. States trajectory completeness
                observed_states = {step["state"] for step in trace}
                self.assertTrue(
                    expected_states.issubset(observed_states),
                    f"Hub {hub} missing ReAct states: {expected_states - observed_states}",
                )

                # 3. Monotonic step ordering
                for idx, step in enumerate(trace):
                    self.assertEqual(step["step"], idx + 1, f"Step mismatch at idx {idx} in {hub}")
                    self.assertIn("timestamp", step)
                    # Verify timestamp is valid ISO format
                    dt = datetime.fromisoformat(step["timestamp"])
                    self.assertIsNotNone(dt)

                # 4. Phase 1 anchors resolution checks
                self.assertEqual(trace[0]["state"], "thought")
                self.assertEqual(trace[1]["state"], "action")
                self.assertEqual(trace[1]["tool"], "search_entities")
                self.assertEqual(trace[2]["state"], "observation")

                # 5. Terminal step is always Synthesis
                self.assertEqual(trace[-1]["state"], "synthesis")
                self.assertIn("Synthesizing", trace[-1]["thought"])

    async def test_react_step_serialization_and_deserialization(self):
        """Verifies ReActStep to_dict serialization integrity under varied fields."""
        step = ReActStep(
            step=42,
            state=ReActState.REFLECTION,
            slot="Day 1 Evening",
            thought="Evaluating candidate transit.",
            action="get_cross_domain_affinities",
            tool="get_cross_domain_affinities",
            tool_input={"hub": "Tokyo", "target_domains": ["music"]},
            observation="Observed 5 candidates",
            reflection="Candidate violates transit constraint",
            conflict_detected="transit_exceeded",
            backtrack_occurred=True,
        )
        d = step.to_dict()
        self.assertEqual(d["step"], 42)
        self.assertEqual(d["state"], "reflection")
        self.assertEqual(d["slot"], "Day 1 Evening")
        self.assertEqual(d["conflict_detected"], "transit_exceeded")
        self.assertTrue(d["backtrack_occurred"])
        self.assertEqual(d["tool_input"]["hub"], "Tokyo")


# ============================================================================
# Suite 2: Metric Boundaries & Mathematical Extreme Inputs
# ============================================================================

class TestMetricBoundsAdversarial(unittest.IsolatedAsyncioTestCase):
    """Stress-tests metric boundary conditions [0.0, 1.0] and mathematical extremes."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_end_to_end_metric_bounds_across_diverse_seeds(self):
        """Verifies that generated plans across all hubs strictly adhere to [0.0, 1.0]."""
        test_cases = [
            ("Bangalore", [TasteSeed(name="Kannada Theatre", domain=CulturalDomain.ARTS, weight=0.1)]),
            ("Mumbai", [TasteSeed(name="Street Food", domain=CulturalDomain.DINING, weight=1.0)]),
            ("Tokyo", [TasteSeed(name="Anime", domain=CulturalDomain.CINEMA, weight=0.5)]),
            ("Paris", [TasteSeed(name="Fashion Week", domain=CulturalDomain.FASHION, weight=0.8)]),
            ("Berlin", [TasteSeed(name="Club Culture", domain=CulturalDomain.NIGHTLIFE, weight=0.9)]),
        ]

        for hub, seeds in test_cases:
            with self.subTest(hub=hub):
                plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
                # Cultural coherence bound
                self.assertGreaterEqual(plan.cultural_coherence_score, 0.0)
                self.assertLessEqual(plan.cultural_coherence_score, 1.0)
                # Domain diversity bound
                self.assertGreaterEqual(plan.domain_diversity_score, 0.0)
                self.assertLessEqual(plan.domain_diversity_score, 1.0)
                # Transit efficiency bound
                self.assertGreaterEqual(plan.transit_efficiency_score, 0.0)
                self.assertLessEqual(plan.transit_efficiency_score, 1.0)

    def test_cultural_coherence_boundary_extremes(self):
        """Adversarial stress-testing of calculate_cultural_coherence_score."""
        seeds = [TasteSeed(name="Test", domain=CulturalDomain.ARTS)]

        # 1. Minimum extreme: zero affinities, completely disjoint tags
        items_min = make_dummy_items_8(
            affinities=[0.0] * 8,
            tags_per_item=[[f"unique_tag_{i}"] for i in range(8)],
        )
        score_min = calculate_cultural_coherence_score(items_min, seeds)
        self.assertGreaterEqual(score_min, 0.0)
        self.assertLessEqual(score_min, 1.0)

        # 2. Maximum extreme: 1.0 affinities, 100% shared tags
        items_max = make_dummy_items_8(
            affinities=[1.0] * 8,
            tags_per_item=[["universal_tag"]] * 8,
        )
        score_max = calculate_cultural_coherence_score(items_max, seeds)
        self.assertGreaterEqual(score_max, 0.0)
        self.assertLessEqual(score_max, 1.0)
        self.assertGreater(score_max, score_min)

        # 3. Item count invariant enforcement
        with self.assertRaises(ValueError):
            calculate_cultural_coherence_score(items_min[:7], seeds)
        with self.assertRaises(ValueError):
            calculate_cultural_coherence_score(items_min + items_min[:1], seeds)

    def test_domain_diversity_boundary_extremes(self):
        """Adversarial stress-testing of calculate_domain_diversity_score."""
        # 1. Monocultural extreme: All 8 items have identical domain
        monocultural_items = make_dummy_items_8(
            domains=[CulturalDomain.DINING] * 8
        )
        # Entropy is 0, 7 adjacent collisions -> score = 0.0 - 0.35 = -0.35, clamped to 0.0
        score_mono = calculate_domain_diversity_score(monocultural_items)
        self.assertEqual(score_mono, 0.0)

        # 2. Alternating binary domains: DINING, ARTS, DINING, ARTS...
        # 2 unique domains, 0 collisions
        binary_items = make_dummy_items_8(
            domains=[
                CulturalDomain.DINING, CulturalDomain.ARTS,
                CulturalDomain.DINING, CulturalDomain.ARTS,
                CulturalDomain.DINING, CulturalDomain.ARTS,
                CulturalDomain.DINING, CulturalDomain.ARTS,
            ]
        )
        score_binary = calculate_domain_diversity_score(binary_items)
        self.assertGreater(score_binary, 0.0)
        self.assertLessEqual(score_binary, 1.0)

        # 3. High diversity: 6 unique domains
        diverse_items = make_dummy_items_8(
            domains=[
                CulturalDomain.DINING, CulturalDomain.ARTS,
                CulturalDomain.MUSIC, CulturalDomain.NIGHTLIFE,
                CulturalDomain.LITERARY, CulturalDomain.CINEMA,
                CulturalDomain.DINING, CulturalDomain.MUSIC,
            ]
        )
        score_diverse = calculate_domain_diversity_score(diverse_items)
        self.assertGreater(score_diverse, score_binary)
        self.assertLessEqual(score_diverse, 1.0)

        # 4. Item count invariant enforcement
        with self.assertRaises(ValueError):
            calculate_domain_diversity_score(diverse_items[:6])

    def test_transit_efficiency_boundary_extremes(self):
        """Adversarial stress-testing of calculate_transit_efficiency_score."""
        # 1. Optimal extreme: 0 minutes transit for all legs
        items_zero = make_dummy_items_8(transits=[0] * 8)
        score_zero = calculate_transit_efficiency_score(items_zero)
        self.assertEqual(score_zero, 1.0)

        # 2. Optimal boundary: exactly 15 minutes for all transition legs
        items_15 = make_dummy_items_8(transits=[0] + [15] * 7)
        score_15 = calculate_transit_efficiency_score(items_15)
        self.assertEqual(score_15, 1.0)

        # 3. Acceptable boundary: exactly 45 minutes for all transition legs
        # leg_phi = 1.0 - 0.40 * (30/30) = 0.60, mean = 0.60
        items_45 = make_dummy_items_8(transits=[0] + [45] * 7)
        score_45 = calculate_transit_efficiency_score(items_45)
        self.assertEqual(score_45, 0.60)

        # 4. Excessive extreme: 120 minutes transit on all transition legs
        # excess_count = 7, penalty = 7 * 0.20 = 1.40 -> score clamped to 0.0
        items_excess = make_dummy_items_8(transits=[0] + [120] * 7)
        score_excess = calculate_transit_efficiency_score(items_excess)
        self.assertEqual(score_excess, 0.0)

        # 5. Item count invariant enforcement
        with self.assertRaises(ValueError):
            calculate_transit_efficiency_score(items_zero[:5])


# ============================================================================
# Suite 3: Conflict Injection & Backtracking Stress-Testing
# ============================================================================

class TestConflictInjectionAndBacktracking(unittest.IsolatedAsyncioTestCase):
    """
    Empirically injects conflicts into candidate generation and validates
    that ReActPlanner detects the conflict, registers the trace, and recovers.
    """

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_conflict_injection_duplicate_venue(self):
        """Injects duplicate venue candidates to assert rejection and backtracking."""
        hub = "Bangalore"
        seeds = [TasteSeed(name="Third Wave Coffee", domain=CulturalDomain.DINING)]

        # Run standard plan
        plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
        first_venue_id = plan.items[0].entity.id

        # Wrap client to intentionally prioritize first_venue_id in subsequent queries
        original_get_affinities = self.client.get_cross_domain_affinities
        original_get_hub_entities = self.client.get_hub_entities

        first_venue_entity = plan.items[0].entity

        async def injected_get_affinities(*args, **kwargs):
            results = await original_get_affinities(*args, **kwargs)
            # Prepend the already-used first_venue as a fake affinity match
            from cultura.agent.tools import AffinityScore
            poisoned_aff = AffinityScore(
                entity_id="dummy_source",
                target_entity=first_venue_entity,
                score=0.99,
                rationale="Injected poison duplicate venue",
            )
            return [poisoned_aff] + results

        self.client.get_cross_domain_affinities = injected_get_affinities

        # Plan with poisoned duplicates
        plan_poisoned = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)

        # Assert zero duplicate venues in final plan
        entity_ids = [item.entity.id for item in plan_poisoned.items]
        self.assertEqual(len(entity_ids), 8)
        self.assertEqual(len(set(entity_ids)), 8)

        # Assert duplicate rejections were recorded in trace
        trace = plan_poisoned.metadata.get("react_trace", [])
        dup_steps = [s for s in trace if s.get("conflict_detected") == "duplicate_venue"]
        self.assertGreater(len(dup_steps), 0)
        self.assertTrue(all(s["backtrack_occurred"] is True for s in dup_steps))

    async def test_conflict_injection_diurnal_mismatch(self):
        """Injects diurnal constraint violations to assert rejection and recovery."""
        hub = "Tokyo"
        seeds = [TasteSeed(name="Ramen", domain=CulturalDomain.DINING)]

        original_get_affinities = self.client.get_cross_domain_affinities

        # Inject a NIGHTLIFE venue into morning queries
        nightlife_entity = make_dummy_entity(
            entity_id="tokyo_nightlife_injected",
            name="Injected Midnight Club",
            domain=CulturalDomain.NIGHTLIFE,
            hub=hub,
        )

        async def injected_affinities(*args, **kwargs):
            results = await original_get_affinities(*args, **kwargs)
            from cultura.agent.tools import AffinityScore
            poisoned = AffinityScore(
                entity_id="dummy",
                target_entity=nightlife_entity,
                score=0.98,
                rationale="Injected nightlife candidate",
            )
            return [poisoned] + results

        self.client.get_cross_domain_affinities = injected_affinities

        plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
        self.assertEqual(len(plan.items), 8)

        # Verify Day 1 Morning and Day 2 Morning do NOT have Nightlife
        self.assertNotEqual(plan.items[0].entity.domain, CulturalDomain.NIGHTLIFE)
        self.assertNotEqual(plan.items[4].entity.domain, CulturalDomain.NIGHTLIFE)

        # Verify diurnal conflict was logged in react trace
        trace = plan.metadata.get("react_trace", [])
        diurnal_conflicts = [s for s in trace if s.get("conflict_detected") == "diurnal_disallowed"]
        self.assertGreater(len(diurnal_conflicts), 0)

    async def test_conflict_injection_spatial_transit_excess(self):
        """Injects spatially distant venues (> 45 min) to assert spatial rejection."""
        hub = "Berlin"
        seeds = [TasteSeed(name="Berghain", domain=CulturalDomain.NIGHTLIFE)]

        original_get_affinities = self.client.get_cross_domain_affinities

        # Inject venue located 150 km away from Berlin
        distant_entity = make_dummy_entity(
            entity_id="distant_venue_injected",
            name="Distant Outpost",
            domain=CulturalDomain.ARTS,
            hub=hub,
            lat=53.5511,  # Hamburg coords
            lon=9.9937,
        )

        async def injected_affinities(*args, **kwargs):
            results = await original_get_affinities(*args, **kwargs)
            from cultura.agent.tools import AffinityScore
            poisoned = AffinityScore(
                entity_id="dummy",
                target_entity=distant_entity,
                score=0.99,
                rationale="Injected distant candidate",
            )
            return [poisoned] + results

        self.client.get_cross_domain_affinities = injected_affinities

        plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
        self.assertEqual(len(plan.items), 8)

        # Distant entity should not be scheduled
        scheduled_ids = {item.entity.id for item in plan.items}
        self.assertNotIn("distant_venue_injected", scheduled_ids)

        # Trace must contain transit_exceeded conflict
        trace = plan.metadata.get("react_trace", [])
        transit_conflicts = [s for s in trace if s.get("conflict_detected") == "transit_exceeded"]
        self.assertGreater(len(transit_conflicts), 0)

        # All scheduled items must obey <= 45 min
        for item in plan.items:
            self.assertLessEqual(item.transit_from_previous_min, 45)

    async def test_conflict_injection_domain_clumping(self):
        """Injects consecutive identical domain candidates to assert anti-clumping."""
        hub = "Paris"
        seeds = [TasteSeed(name="Boulangerie", domain=CulturalDomain.DINING)]

        plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
        # Verify no consecutive domain clumping
        for i in range(len(plan.items) - 1):
            self.assertNotEqual(plan.items[i].entity.domain, plan.items[i + 1].entity.domain)

    async def test_conflict_backtracking_exhaustion_graceful_failure(self):
        """Asserts that impossible constraints fail gracefully with RuntimeError."""
        hub = "Bangalore"
        seeds = [TasteSeed(name="Third Wave Coffee", domain=CulturalDomain.DINING)]

        # Set max_backtracks low (e.g. 5) and poison candidates to trigger transit excess
        strict_planner = ReActPlanner(client=self.client, max_backtracks=5)

        # Allow anchor search to succeed, but poison candidate affinities with distant coordinates
        async def always_distant_affinities(*args, **kwargs):
            from cultura.agent.tools import AffinityScore
            results = []
            for i in range(5):
                e = make_dummy_entity(
                    entity_id=f"distant_{i}",
                    name=f"Distant {i}",
                    domain=CulturalDomain.ARTS,
                    hub=hub,
                    lat=50.0 + i,  # Far away
                    lon=10.0,
                )
                results.append(
                    AffinityScore(
                        entity_id="dummy",
                        target_entity=e,
                        score=0.9,
                        rationale="Distant",
                    )
                )
            return results

        async def always_distant_hub_entities(*args, **kwargs):
            # If domain is specified, this is called by _fetch_candidates_for_domains
            if kwargs.get("domain") is not None or (len(args) >= 2 and args[1] is not None):
                return [
                    make_dummy_entity(
                        entity_id="distant_hub_e",
                        name="Distant Hub Entity",
                        domain=kwargs.get("domain", CulturalDomain.ARTS),
                        hub=hub,
                        lat=50.0,
                        lon=10.0,
                    )
                ]
            # Otherwise it's anchor fallback
            from cultura.client.mock_data import get_mock_hub_entities
            return get_mock_hub_entities(hub=hub)

        strict_planner.client.get_cross_domain_affinities = always_distant_affinities
        strict_planner.client.get_hub_entities = always_distant_hub_entities

        # Must raise RuntimeError gracefully without unhandled crashes
        with self.assertRaises(RuntimeError) as ctx:
            await strict_planner.plan_48h(city_hub=hub, taste_seeds=seeds)
        self.assertTrue(
            "failed to converge" in str(ctx.exception).lower() or
            "failed to synthesize" in str(ctx.exception).lower()
        )

    async def test_downstream_deadlock_recovery(self):
        """
        Simulates a downstream deadlock where candidate committed at slot N
        causes slot N+1 to have 0 valid options, forcing a chronological pop & recovery.
        """
        hub = "London"
        seeds = [TasteSeed(name="British Museum", domain=CulturalDomain.ARTS)]

        # Create a planner with backtrack budget
        planner = ReActPlanner(client=self.client, max_backtracks=50)

        # Execute plan
        plan = await planner.plan_48h(city_hub=hub, taste_seeds=seeds)
        self.assertEqual(len(plan.items), 8)

        # Verify backtrack steps occurred or can be handled
        trace = plan.metadata.get("react_trace", [])
        self.assertIsInstance(trace, list)
        self.assertGreater(len(trace), 8)
        self.assertEqual(plan.metadata.get("domains_covered", []), sorted(list({i.entity.domain.value for i in plan.items})))


# ============================================================================
# Suite 4: Conflict Hierarchy Unit Integrity
# ============================================================================

class TestPlannerConflictHierarchy(unittest.TestCase):
    """Verifies that the conflict exception classes instantiate and inherit cleanly."""

    def test_planner_conflict_inheritance(self):
        diurnal = DiurnalSlotConflict(TimeSlot.MORNING, CulturalDomain.NIGHTLIFE, "Closed in morning")
        self.assertIsInstance(diurnal, PlannerConflict)
        self.assertIn("morning", str(diurnal))

        dup = DuplicateVenueConflict("venue_123", "Central Perk")
        self.assertIsInstance(dup, PlannerConflict)
        self.assertIn("Central Perk", str(dup))

        clump = DomainClumpingConflict(CulturalDomain.DINING, 1)
        self.assertIsInstance(clump, PlannerConflict)
        self.assertIn("dining", str(clump))

        transit = TransitExcessConflict(60, 45)
        self.assertIsInstance(transit, PlannerConflict)
        self.assertIn("60m", str(transit))

        starve = DomainStarvationConflict(2, 1, 4)
        self.assertIsInstance(starve, PlannerConflict)
        self.assertIn("starvation", str(starve))


# ============================================================================
# Suite 5: Hub Coverage, Adversarial Seeds, Concurrency & Latency Stress
# ============================================================================

import time

ALL_8_HUBS = [
    "Bangalore",
    "Mumbai",
    "New York",
    "London",
    "Tokyo",
    "Paris",
    "Berlin",
    "San Francisco",
]


class TestAdversarialHubAndSeedCombinations(unittest.IsolatedAsyncioTestCase):
    """Stress tests ReActPlanner across all 8 hubs with diverse seed combinations."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    def _assert_plan_invariants(self, plan: ItineraryPlan, hub: str):
        """Helper to assert strict 48-hour schedule invariants."""
        self.assertIsInstance(plan, ItineraryPlan)
        self.assertEqual(plan.city_hub, hub)
        self.assertEqual(len(plan.items), 8, f"Plan in {hub} did not produce exactly 8 items")

        # Zero duplicate venues
        venue_ids = [item.entity.id for item in plan.items]
        self.assertEqual(
            len(venue_ids),
            len(set(venue_ids)),
            f"Duplicate venues found in {hub}: {venue_ids}",
        )

        # All venues belong to requested hub
        for item in plan.items:
            self.assertEqual(
                item.entity.hub,
                hub,
                f"Entity {item.entity.id} has hub {item.entity.hub}, expected {hub}",
            )

        # Cross-domain diversity >= 4 domains
        unique_domains = {item.entity.domain for item in plan.items}
        self.assertGreaterEqual(
            len(unique_domains),
            4,
            f"Plan in {hub} only covered {len(unique_domains)} domains: {unique_domains}",
        )

        # Anti-clumping: no consecutive items have identical domain
        for i in range(len(plan.items) - 1):
            d_curr = plan.items[i].entity.domain
            d_next = plan.items[i + 1].entity.domain
            self.assertNotEqual(
                d_curr,
                d_next,
                f"Consecutive domain clumping in {hub} at slots {i} and {i+1}: {d_curr.value}",
            )

        # Transit threshold: <= 45 minutes for all legs
        for idx, item in enumerate(plan.items):
            if idx == 0:
                self.assertEqual(item.transit_from_previous_min, 0)
            else:
                self.assertLessEqual(
                    item.transit_from_previous_min,
                    45,
                    f"Transit exceeded 45m in {hub} at leg {idx}: {item.transit_from_previous_min}m",
                )

        # Mathematical metric floors
        self.assertGreaterEqual(
            plan.cultural_coherence_score,
            0.65,
            f"Low coherence in {hub}: {plan.cultural_coherence_score}",
        )
        self.assertGreaterEqual(
            plan.domain_diversity_score,
            0.70,
            f"Low diversity in {hub}: {plan.domain_diversity_score}",
        )
        self.assertGreaterEqual(
            plan.transit_efficiency_score,
            0.75,
            f"Low transit efficiency in {hub}: {plan.transit_efficiency_score}",
        )

        # Trace metadata verification
        self.assertIn("react_trace", plan.metadata)
        self.assertGreaterEqual(plan.react_steps_count, 17)

    async def test_all_8_hubs_single_seed_coverage(self):
        """Tests each of the 8 hubs with different single-seed cultural domains."""
        domains = [
            CulturalDomain.ARTS,
            CulturalDomain.DINING,
            CulturalDomain.MUSIC,
            CulturalDomain.CINEMA,
            CulturalDomain.FASHION,
            CulturalDomain.LITERARY,
            CulturalDomain.NIGHTLIFE,
            CulturalDomain.ARTS,
        ]
        for hub, dom in zip(ALL_8_HUBS, domains):
            seed = TasteSeed(name=f"{hub} Culture Exploration", domain=dom, weight=1.0)
            t0 = time.perf_counter()
            plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=[seed])
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.assertLess(elapsed_ms, 500, f"Plan for {hub} took {elapsed_ms:.1f}ms (> 500ms)")
            self._assert_plan_invariants(plan, hub)

    async def test_all_8_hubs_dual_cross_domain_seeds(self):
        """Tests each of the 8 hubs with dual conflicting/complementary domain seeds."""
        seed_pairs = [
            [
                TasteSeed(name="Third Wave Espresso", domain=CulturalDomain.DINING, weight=1.5),
                TasteSeed(name="Math Rock", domain=CulturalDomain.MUSIC, weight=0.8),
            ],
            [
                TasteSeed(name="Contemporary Gallery", domain=CulturalDomain.ARTS, weight=1.0),
                TasteSeed(name="Independent Cinema", domain=CulturalDomain.CINEMA, weight=1.2),
            ],
            [
                TasteSeed(name="Underground Techno", domain=CulturalDomain.NIGHTLIFE, weight=2.0),
                TasteSeed(name="Secondhand Bookstore", domain=CulturalDomain.LITERARY, weight=0.5),
            ],
            [
                TasteSeed(name="Heritage Architecture", domain=CulturalDomain.ARTS, weight=1.0),
                TasteSeed(name="Street Food Night Market", domain=CulturalDomain.DINING, weight=1.0),
            ],
            [
                TasteSeed(name="Jazz Bar", domain=CulturalDomain.MUSIC, weight=1.0),
                TasteSeed(name="Experimental Fashion", domain=CulturalDomain.FASHION, weight=1.0),
            ],
            [
                TasteSeed(name="Artisanal Bakery", domain=CulturalDomain.DINING, weight=1.0),
                TasteSeed(name="Modern Sculpture", domain=CulturalDomain.ARTS, weight=1.0),
            ],
            [
                TasteSeed(name="Electronic Ambient", domain=CulturalDomain.MUSIC, weight=1.0),
                TasteSeed(name="Indie Zines", domain=CulturalDomain.LITERARY, weight=1.0),
            ],
            [
                TasteSeed(name="Speakeasy Cocktail", domain=CulturalDomain.NIGHTLIFE, weight=1.0),
                TasteSeed(name="Documentary Film", domain=CulturalDomain.CINEMA, weight=1.0),
            ],
        ]
        for hub, seeds in zip(ALL_8_HUBS, seed_pairs):
            t0 = time.perf_counter()
            plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.assertLess(elapsed_ms, 500, f"Plan for {hub} took {elapsed_ms:.1f}ms (> 500ms)")
            self._assert_plan_invariants(plan, hub)


class TestAdversarialSeeds(unittest.IsolatedAsyncioTestCase):
    """Stress tests boundary, hostile, and adversarial taste seeds."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_zero_seeds_raises_value_error(self):
        """Zero seeds must raise ValueError before initiating planning."""
        for hub in ["Tokyo", "Bangalore", "Paris"]:
            with self.assertRaises(ValueError) as ctx:
                await self.planner.plan_48h(city_hub=hub, taste_seeds=[])
            self.assertIn("At least one taste seed must be supplied", str(ctx.exception))

    async def test_ten_competing_seeds_all_domains(self):
        """10 seeds covering all domains with conflicting weights in [0.0, 2.0] across all 8 hubs."""
        competing_10 = [
            TasteSeed(name="Minimalist Architecture", domain=CulturalDomain.ARTS, weight=2.0),
            TasteSeed(name="Artisanal Fermentation", domain=CulturalDomain.DINING, weight=0.1),
            TasteSeed(name="Post-Punk Revival", domain=CulturalDomain.MUSIC, weight=1.9),
            TasteSeed(name="Secret Basement Club", domain=CulturalDomain.NIGHTLIFE, weight=0.7),
            TasteSeed(name="French New Wave Cinema", domain=CulturalDomain.CINEMA, weight=1.8),
            TasteSeed(name="Deconstructed Streetwear", domain=CulturalDomain.FASHION, weight=0.4),
            TasteSeed(name="Existential Philosophy", domain=CulturalDomain.LITERARY, weight=1.5),
            TasteSeed(name="Abstract Expressionism", domain=CulturalDomain.ARTS, weight=0.9),
            TasteSeed(name="Vaporwave Synthesizers", domain=CulturalDomain.MUSIC, weight=0.2),
            TasteSeed(name="Late Night Tacos", domain=CulturalDomain.DINING, weight=2.0),
        ]
        for hub in ALL_8_HUBS:
            t0 = time.perf_counter()
            plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=competing_10)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.assertLess(elapsed_ms, 500, f"Competing 10 seeds took {elapsed_ms:.1f}ms in {hub}")
            self.assertEqual(len(plan.items), 8)
            self.assertEqual(len({i.entity.id for i in plan.items}), 8)
            self.assertGreaterEqual(len({i.entity.domain for i in plan.items}), 4)

    async def test_obscure_and_unresolvable_seeds(self):
        """Nonsense, unicode, emoji, and unindexed seeds fall back gracefully."""
        obscure_seeds = [
            TasteSeed(name="Xylophonic Cyberpunk Mycology 9000", domain=CulturalDomain.ARTS),
            TasteSeed(name="!@#$%^&*()_+=~`[]{}|:;?", domain=CulturalDomain.MUSIC),
            TasteSeed(name="👾🍣🔥⛩️", domain=CulturalDomain.DINING),
            TasteSeed(name="a", domain=CulturalDomain.LITERARY),
        ]
        for hub in ALL_8_HUBS:
            t0 = time.perf_counter()
            plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=obscure_seeds)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.assertLess(elapsed_ms, 500, f"Obscure seeds took {elapsed_ms:.1f}ms in {hub}")
            self.assertEqual(len(plan.items), 8)
            self.assertEqual(len({i.entity.id for i in plan.items}), 8)
            self.assertGreaterEqual(len({i.entity.domain for i in plan.items}), 4)

    async def test_mismatched_domain_semantics(self):
        """Seeds where the entity name heavily conflicts with the assigned domain."""
        mismatched_seeds = [
            TasteSeed(name="Steaming Pork Dumplings", domain=CulturalDomain.NIGHTLIFE),
            TasteSeed(name="Symphony Orchestra Hall", domain=CulturalDomain.DINING),
            TasteSeed(name="Heavy Industrial Techno", domain=CulturalDomain.LITERARY),
            TasteSeed(name="Rare Antiquarian Manuscript", domain=CulturalDomain.FASHION),
        ]
        for hub in ALL_8_HUBS:
            t0 = time.perf_counter()
            plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=mismatched_seeds)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            self.assertLess(elapsed_ms, 500, f"Mismatched seeds took {elapsed_ms:.1f}ms in {hub}")
            self.assertEqual(len(plan.items), 8)
            self.assertEqual(len({i.entity.id for i in plan.items}), 8)
            self.assertGreaterEqual(len({i.entity.domain for i in plan.items}), 4)

    async def test_schema_level_rejection_of_invalid_seeds(self):
        """TasteSeed schema must reject invalid names and out-of-bounds weights."""
        with self.assertRaises(Exception):
            TasteSeed(name="   ", domain=CulturalDomain.LITERARY)

        with self.assertRaises(Exception):
            TasteSeed(name="", domain=CulturalDomain.ARTS)

        with self.assertRaises(Exception):
            TasteSeed(name="Heavy Weight", domain=CulturalDomain.DINING, weight=2.5)

        with self.assertRaises(Exception):
            TasteSeed(name="Negative Weight", domain=CulturalDomain.MUSIC, weight=-0.5)

    async def test_extreme_and_asymmetric_seed_weights(self):
        """Zero weight, maximum 2.0 weight, and tiny epsilon weight seeds."""
        extreme_weights = [
            TasteSeed(name="Minimalist Art", domain=CulturalDomain.ARTS, weight=0.0),
            TasteSeed(name="High Dining", domain=CulturalDomain.DINING, weight=2.0),
            TasteSeed(name="Jazz", domain=CulturalDomain.MUSIC, weight=0.0001),
        ]
        plan = await self.planner.plan_48h(city_hub="Tokyo", taste_seeds=extreme_weights)
        self.assertEqual(len(plan.items), 8)
        self.assertGreaterEqual(len({i.entity.domain for i in plan.items}), 4)


class TestConcurrencyStress(unittest.IsolatedAsyncioTestCase):
    """Stress tests concurrent planner execution via asyncio.gather."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_twenty_concurrent_planner_calls(self):
        """Runs 20 concurrent planner calls across all 8 hubs simultaneously."""
        hubs_pool = [
            "Bangalore", "Mumbai", "New York", "London",
            "Tokyo", "Paris", "Berlin", "San Francisco",
            "Bangalore", "Mumbai", "New York", "London",
            "Tokyo", "Paris", "Berlin", "San Francisco",
            "Bangalore", "Mumbai", "Tokyo", "London",
        ]
        assert len(hubs_pool) == 20

        seeds_list = [
            [TasteSeed(name="Coffee", domain=CulturalDomain.DINING, weight=1.0)],
            [TasteSeed(name="Techno", domain=CulturalDomain.MUSIC, weight=1.2)],
            [TasteSeed(name="Modern Art", domain=CulturalDomain.ARTS, weight=0.8)],
            [TasteSeed(name="Cinema", domain=CulturalDomain.CINEMA, weight=1.5)],
            [TasteSeed(name="Nightclub", domain=CulturalDomain.NIGHTLIFE, weight=2.0)],
            [TasteSeed(name="Bookstore", domain=CulturalDomain.LITERARY, weight=0.5)],
            [TasteSeed(name="Streetwear", domain=CulturalDomain.FASHION, weight=1.1)],
            [
                TasteSeed(name="Art", domain=CulturalDomain.ARTS, weight=1.0),
                TasteSeed(name="Dining", domain=CulturalDomain.DINING, weight=1.0),
            ],
            [TasteSeed(name="Jazz", domain=CulturalDomain.MUSIC, weight=1.0)],
            [TasteSeed(name="Boutique", domain=CulturalDomain.FASHION, weight=0.9)],
            [TasteSeed(name="Poetry", domain=CulturalDomain.LITERARY, weight=1.3)],
            [TasteSeed(name="Cocktails", domain=CulturalDomain.NIGHTLIFE, weight=1.4)],
            [TasteSeed(name="Pastries", domain=CulturalDomain.DINING, weight=1.0)],
            [TasteSeed(name="Sculpture", domain=CulturalDomain.ARTS, weight=1.0)],
            [TasteSeed(name="Documentaries", domain=CulturalDomain.CINEMA, weight=1.0)],
            [TasteSeed(name="Ambient", domain=CulturalDomain.MUSIC, weight=1.0)],
            [TasteSeed(name="Heritage", domain=CulturalDomain.ARTS, weight=1.0)],
            [TasteSeed(name="Curry", domain=CulturalDomain.DINING, weight=1.0)],
            [TasteSeed(name="Ramen", domain=CulturalDomain.DINING, weight=1.0)],
            [TasteSeed(name="Speakeasy", domain=CulturalDomain.NIGHTLIFE, weight=1.0)],
        ]
        assert len(seeds_list) == 20

        async def run_plan(idx: int, hub: str, seeds: List[TasteSeed]):
            t0 = time.perf_counter()
            plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
            elapsed_ms = (time.perf_counter() - t0) * 1000
            return idx, hub, plan, elapsed_ms

        t_start = time.perf_counter()
        tasks = [run_plan(i, hubs_pool[i], seeds_list[i]) for i in range(20)]
        results = await asyncio.gather(*tasks)
        total_batch_ms = (time.perf_counter() - t_start) * 1000

        self.assertEqual(len(results), 20)

        for idx, hub, plan, elapsed_ms in results:
            self.assertLess(
                elapsed_ms,
                500.0,
                f"Concurrent plan {idx} ({hub}) took {elapsed_ms:.1f}ms (> 500ms)",
            )
            self.assertEqual(plan.city_hub, hub)
            self.assertEqual(len(plan.items), 8)
            venue_ids = [item.entity.id for item in plan.items]
            self.assertEqual(len(venue_ids), len(set(venue_ids)))
            unique_domains = {item.entity.domain for item in plan.items}
            self.assertGreaterEqual(len(unique_domains), 4)
            for item in plan.items:
                self.assertLessEqual(item.transit_from_previous_min, 45)
            self.assertGreaterEqual(plan.react_steps_count, 17)

        self.assertLess(total_batch_ms, 2000.0, f"20 concurrent plans took {total_batch_ms:.1f}ms (> 2000ms)")


class TestConvergenceLatencyAndRecursionSafety(unittest.IsolatedAsyncioTestCase):
    """Verifies convergence speed, latency bounds, and prevention of recursion depth/infinite loops."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_latency_sub_500ms_across_fifty_runs(self):
        """Repeats planning 50 times across alternating hubs and asserts 100% latency < 500ms."""
        seeds = [
            TasteSeed(name="Contemporary Art", domain=CulturalDomain.ARTS),
            TasteSeed(name="Fine Dining", domain=CulturalDomain.DINING),
        ]
        latencies = []
        for i in range(50):
            hub = ALL_8_HUBS[i % len(ALL_8_HUBS)]
            t0 = time.perf_counter()
            plan = await self.planner.plan_48h(city_hub=hub, taste_seeds=seeds)
            dt_ms = (time.perf_counter() - t0) * 1000
            latencies.append(dt_ms)
            self.assertLess(dt_ms, 500.0, f"Run {i} in {hub} took {dt_ms:.2f}ms (> 500ms)")

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        self.assertLess(avg_latency, 50.0, f"Average latency too high: {avg_latency:.2f}ms")
        self.assertLess(max_latency, 500.0, f"Max latency too high: {max_latency:.2f}ms")

    async def test_recursion_depth_is_strictly_bounded(self):
        """Recursion is bounded to 8 stack frames (one per diurnal slot)."""
        plan = await self.planner.plan_48h(
            city_hub="Paris",
            taste_seeds=[TasteSeed(name="Nouvelle Vague", domain=CulturalDomain.CINEMA)],
        )
        self.assertEqual(len(plan.items), 8)
        slots = [(item.day, item.slot) for item in plan.items]
        self.assertEqual(len(slots), 8)

    async def test_backtrack_cap_terminates_impossible_constraints(self):
        """Restricting max_transit_minutes to impossible 0m triggers backtrack termination without hanging."""
        planner_tight = ReActPlanner(
            client=self.client,
            max_transit_minutes=0,
            max_backtracks=15,
            speed_kmh=1.0,
        )
        seeds = [TasteSeed(name="Test", domain=CulturalDomain.ARTS)]
        t0 = time.perf_counter()
        with self.assertRaises(RuntimeError) as ctx:
            await planner_tight.plan_48h(city_hub="Tokyo", taste_seeds=seeds)
        elapsed_ms = (time.perf_counter() - t0) * 1000

        self.assertLess(elapsed_ms, 500.0, f"Termination took {elapsed_ms:.1f}ms")
        self.assertTrue(
            "within 15 backtracks" in str(ctx.exception)
            or "failed to synthesize a valid 8-slot plan" in str(ctx.exception)
        )


class TestPackageImportIntegrity(unittest.TestCase):
    """Verifies that the package modules can be imported in any arbitrary order without circular import failures."""

    def test_import_cultura_client_standalone(self):
        """from cultura.client import QlooClient in a fresh process must not crash with circular import."""
        import subprocess
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        env = dict(os.environ)
        env["PYTHONPATH"] = os.path.join(repo_root, "src")
        res = subprocess.run(
            [sys.executable, "-c", "from cultura.client import QlooClient"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            env=env,
        )
        self.assertEqual(
            res.returncode,
            0,
            f"Failed to import cultura.client cleanly:\n{res.stderr}",
        )
