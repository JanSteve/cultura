"""
CULTURA Automated Test Suite: Autonomous ReAct Agent Planner.
Verifies:
- 48-Hour 8-slot schedule invariant across global and Indian hubs (BLR, BOM, TYO, PAR, BER, LON, NYC, SFO)
- Single vs. multiple seed resolution & weight sensitivity
- Zero duplicate venues across the entire 48-hour plan
- Cross-domain diversity (>=4 domains) and elimination of adjacent domain clumping
- Haversine transit efficiency (<45 min per leg)
- 5-state ReAct planning loop (Thought -> Action -> Observation -> Reflection -> Synthesis)
- Exact mathematical scoring of cultural coherence, domain entropy, and transit efficiency.
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import List

# Ensure src/ is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import pytest

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
from cultura.client.qloo import QlooClient, QlooInvalidHubError


# ============================================================================
# 1. Hub Execution Suite (Indian & Global Hubs)
# ============================================================================

class TestPlannerHubExecution(unittest.IsolatedAsyncioTestCase):
    """Verifies planning across Indian and global cultural hubs."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_plan_bangalore_indian_hub(self):
        seeds = [
            TasteSeed(name="Third Wave Coffee", domain=CulturalDomain.DINING),
            TasteSeed(name="Indie Rock", domain=CulturalDomain.MUSIC),
        ]
        plan = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        self.assertIsInstance(plan, ItineraryPlan)
        self.assertEqual(plan.city_hub, "Bangalore")
        self.assertEqual(len(plan.items), 8)
        self.assertTrue(all(item.entity.hub == "Bangalore" for item in plan.items))
        self.assertGreaterEqual(plan.cultural_coherence_score, 0.70)
        self.assertGreaterEqual(plan.transit_efficiency_score, 0.75)

    async def test_plan_mumbai_indian_hub(self):
        seeds = [
            TasteSeed(name="Art Deco Architecture", domain=CulturalDomain.ARTS),
            TasteSeed(name="Coastal Seafood", domain=CulturalDomain.DINING),
        ]
        plan = await self.planner.plan_48h(city_hub="Mumbai", taste_seeds=seeds)
        self.assertIsInstance(plan, ItineraryPlan)
        self.assertEqual(plan.city_hub, "Mumbai")
        self.assertEqual(len(plan.items), 8)
        self.assertTrue(all(item.entity.hub == "Mumbai" for item in plan.items))
        self.assertGreaterEqual(plan.domain_diversity_score, 0.70)
        self.assertGreaterEqual(plan.transit_efficiency_score, 0.75)

    async def test_plan_tokyo_global_hub(self):
        seeds = [
            TasteSeed(name="Jazz Kissa", domain=CulturalDomain.MUSIC),
            TasteSeed(name="Contemporary Architecture", domain=CulturalDomain.ARTS),
        ]
        plan = await self.planner.plan_48h(city_hub="Tokyo", taste_seeds=seeds)
        self.assertEqual(plan.city_hub, "Tokyo")
        self.assertEqual(len(plan.items), 8)
        self.assertTrue(all(item.transit_from_previous_min <= 45 for item in plan.items))

    async def test_plan_paris_global_hub(self):
        seeds = [
            TasteSeed(name="Nouvelle Vague", domain=CulturalDomain.CINEMA),
            TasteSeed(name="Natural Wine", domain=CulturalDomain.DINING),
        ]
        plan = await self.planner.plan_48h(city_hub="Paris", taste_seeds=seeds)
        self.assertEqual(plan.city_hub, "Paris")
        self.assertGreaterEqual(plan.domain_diversity_score, 0.70)

    async def test_plan_berlin_global_hub(self):
        seeds = [
            TasteSeed(name="Modular Techno", domain=CulturalDomain.MUSIC),
            TasteSeed(name="Brutalist Architecture", domain=CulturalDomain.ARTS),
        ]
        plan = await self.planner.plan_48h(city_hub="Berlin", taste_seeds=seeds)
        self.assertEqual(plan.city_hub, "Berlin")
        self.assertEqual(len(plan.items), 8)
        self.assertGreaterEqual(plan.cultural_coherence_score, 0.70)

    async def test_plan_london_global_hub(self):
        seeds = [
            TasteSeed(name="Post-Punk", domain=CulturalDomain.MUSIC),
            TasteSeed(name="Antiquarian Books", domain=CulturalDomain.LITERARY),
        ]
        plan = await self.planner.plan_48h(city_hub="London", taste_seeds=seeds)
        self.assertEqual(plan.city_hub, "London")
        self.assertGreaterEqual(plan.domain_diversity_score, 0.70)

    async def test_plan_new_york_global_hub(self):
        seeds = [
            TasteSeed(name="Post-Bop Jazz", domain=CulturalDomain.MUSIC),
            TasteSeed(name="Modernist Art", domain=CulturalDomain.ARTS),
        ]
        plan = await self.planner.plan_48h(city_hub="New York", taste_seeds=seeds)
        self.assertEqual(plan.city_hub, "New York")
        self.assertGreater(plan.react_steps_count, 0)

    async def test_plan_san_francisco_global_hub(self):
        seeds = [
            TasteSeed(name="Beat Generation", domain=CulturalDomain.LITERARY),
            TasteSeed(name="Sourdough Bakery", domain=CulturalDomain.DINING),
        ]
        plan = await self.planner.plan_48h(city_hub="San Francisco", taste_seeds=seeds)
        self.assertEqual(plan.city_hub, "San Francisco")
        self.assertEqual(len(plan.items), 8)
        self.assertGreaterEqual(plan.transit_efficiency_score, 0.75)


# ============================================================================
# 2. Taste Seed Resolution & Weighting Suite
# ============================================================================

class TestSeedResolution(unittest.IsolatedAsyncioTestCase):
    """Verifies single vs multiple seed handling and weight influence."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_single_seed_resolution(self):
        seeds = [TasteSeed(name="Third Wave Coffee", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        domains = {item.entity.domain for item in plan.items}
        self.assertIn(CulturalDomain.DINING, domains)
        self.assertGreaterEqual(len(domains), 4)

    async def test_multiple_seeds_resolution(self):
        seeds = [
            TasteSeed(name="Coltrane", domain=CulturalDomain.MUSIC),
            TasteSeed(name="Brutalism", domain=CulturalDomain.ARTS),
            TasteSeed(name="Izakaya", domain=CulturalDomain.DINING),
        ]
        plan = await self.planner.plan_48h(city_hub="Tokyo", taste_seeds=seeds)
        domains = {item.entity.domain for item in plan.items}
        self.assertTrue({CulturalDomain.MUSIC, CulturalDomain.ARTS, CulturalDomain.DINING}.issubset(domains))

    async def test_seed_weight_influence(self):
        seeds_a = [
            TasteSeed(name="Jazz", domain=CulturalDomain.MUSIC, weight=2.0),
            TasteSeed(name="Coffee", domain=CulturalDomain.DINING, weight=0.2),
        ]
        seeds_b = [
            TasteSeed(name="Jazz", domain=CulturalDomain.MUSIC, weight=0.2),
            TasteSeed(name="Coffee", domain=CulturalDomain.DINING, weight=2.0),
        ]
        plan_a = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds_a)
        plan_b = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds_b)

        # Plan A with high music weight schedules music in Day 1 Evening (slot 2)
        # Plan B with high dining weight schedules dining in Day 1 Evening (slot 2)
        domain_a_evening = plan_a.items[2].entity.domain
        domain_b_evening = plan_b.items[2].entity.domain
        self.assertEqual(domain_a_evening, CulturalDomain.MUSIC)
        self.assertEqual(domain_b_evening, CulturalDomain.DINING)

    async def test_unmatched_seed_fallback(self):
        seeds = [TasteSeed(name="Xylophonic Neo-Cyberpunk", domain=CulturalDomain.MUSIC)]
        plan = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        self.assertEqual(len(plan.items), 8)
        self.assertGreaterEqual(plan.cultural_coherence_score, 0.50)


# ============================================================================
# 3. Schedule Invariant 48-Hour Suite
# ============================================================================

class TestScheduleInvariant48Hours(unittest.IsolatedAsyncioTestCase):
    """Verifies exactly 8 slots, diurnal progression, and time windows."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_exact_8_slots_sequence(self):
        seeds = [TasteSeed(name="Artisan Bread", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="Paris", taste_seeds=seeds)
        expected = [
            (1, TimeSlot.MORNING), (1, TimeSlot.AFTERNOON), (1, TimeSlot.EVENING), (1, TimeSlot.NIGHT),
            (2, TimeSlot.MORNING), (2, TimeSlot.AFTERNOON), (2, TimeSlot.EVENING), (2, TimeSlot.NIGHT),
        ]
        actual = [(item.day, item.slot) for item in plan.items]
        self.assertEqual(actual, expected)

    async def test_chronological_slot_progression(self):
        seeds = [TasteSeed(name="Electronic", domain=CulturalDomain.MUSIC)]
        plan = await self.planner.plan_48h(city_hub="Berlin", taste_seeds=seeds)
        day1_items = [i for i in plan.items if i.day == 1]
        day2_items = [i for i in plan.items if i.day == 2]
        self.assertEqual(len(day1_items), 4)
        self.assertEqual(len(day2_items), 4)
        self.assertEqual([i.slot for i in day1_items], [TimeSlot.MORNING, TimeSlot.AFTERNOON, TimeSlot.EVENING, TimeSlot.NIGHT])
        self.assertEqual([i.slot for i in day2_items], [TimeSlot.MORNING, TimeSlot.AFTERNOON, TimeSlot.EVENING, TimeSlot.NIGHT])

    async def test_time_window_assignments(self):
        seeds = [TasteSeed(name="Bebop", domain=CulturalDomain.MUSIC)]
        plan = await self.planner.plan_48h(city_hub="New York", taste_seeds=seeds)
        for item in plan.items:
            self.assertEqual(item.time_window, item.slot.default_time_window)


# ============================================================================
# 4. Zero Duplicate Venues Suite
# ============================================================================

class TestZeroDuplicateVenues(unittest.IsolatedAsyncioTestCase):
    """Verifies that all 8 venues are strictly distinct across days and slots."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_all_8_venues_distinct(self):
        seeds = [TasteSeed(name="Craft Beer", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        entity_ids = [item.entity.id for item in plan.items]
        self.assertEqual(len(set(entity_ids)), 8)

    async def test_no_venue_repetition_across_days(self):
        seeds = [TasteSeed(name="Soba", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="Tokyo", taste_seeds=seeds)
        d1_ids = {item.entity.id for item in plan.items if item.day == 1}
        d2_ids = {item.entity.id for item in plan.items if item.day == 2}
        self.assertTrue(d1_ids.isdisjoint(d2_ids))

    async def test_repetition_backtracking_resolution(self):
        seeds = [TasteSeed(name="Third Wave Coffee", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        trace = plan.metadata.get("react_trace", [])
        dup_rejections = [s for s in trace if s.get("conflict_detected") == "duplicate_venue"]
        # The planner encounter and properly rejected duplicate venue candidates
        self.assertGreater(len(dup_rejections), 0)
        self.assertEqual(len(set(i.entity.id for i in plan.items)), 8)


# ============================================================================
# 5. Domain Diversity & Anti-Clumping Suite
# ============================================================================

class TestDomainDiversityAndClumping(unittest.IsolatedAsyncioTestCase):
    """Verifies >=4 domains, zero adjacent clumping, and Shannon entropy."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_at_least_four_domains(self):
        seeds = [TasteSeed(name="Indie Pop", domain=CulturalDomain.MUSIC)]
        plan = await self.planner.plan_48h(city_hub="London", taste_seeds=seeds)
        unique_domains = {item.entity.domain for item in plan.items}
        self.assertGreaterEqual(len(unique_domains), 4)

    async def test_no_consecutive_domain_clumping(self):
        seeds = [TasteSeed(name="Ramen", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="Tokyo", taste_seeds=seeds)
        for i in range(len(plan.items) - 1):
            self.assertNotEqual(
                plan.items[i].entity.domain,
                plan.items[i + 1].entity.domain,
                f"Domain clumping at slot {i}->{i+1}: both are {plan.items[i].entity.domain}",
            )

    async def test_domain_diversity_score_threshold(self):
        seeds = [TasteSeed(name="Contemporary Art", domain=CulturalDomain.ARTS)]
        plan = await self.planner.plan_48h(city_hub="Paris", taste_seeds=seeds)
        self.assertGreaterEqual(plan.domain_diversity_score, 0.70)

    async def test_domain_distribution_balance(self):
        seeds = [TasteSeed(name="Jazz", domain=CulturalDomain.MUSIC)]
        plan = await self.planner.plan_48h(city_hub="New York", taste_seeds=seeds)
        for d in CulturalDomain:
            count = sum(1 for item in plan.items if item.entity.domain == d)
            self.assertLessEqual(count, 3, f"Domain '{d.value}' appeared {count} times (> 3 max)")


# ============================================================================
# 6. Spatial Transit & Spatio-Temporal Constraints Suite
# ============================================================================

class TestTransitEfficiencyAndSpatioTemporalConstraints(unittest.IsolatedAsyncioTestCase):
    """Verifies legs under 45m and spatial efficiency."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_all_transit_legs_under_45_min(self):
        seeds = [TasteSeed(name="Sourdough", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="San Francisco", taste_seeds=seeds)
        for i, item in enumerate(plan.items):
            if i == 0:
                self.assertEqual(item.transit_from_previous_min, 0)
            else:
                self.assertLessEqual(item.transit_from_previous_min, 45)
                self.assertGreaterEqual(item.transit_from_previous_min, 5)

    async def test_day1_morning_transit_is_zero_and_dwell_times_valid(self):
        seeds = [TasteSeed(name="Dosa", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        self.assertEqual(plan.items[0].transit_from_previous_min, 0)
        for item in plan.items[1:]:
            self.assertGreaterEqual(item.transit_from_previous_min, 5)

    async def test_transit_efficiency_score_threshold(self):
        seeds = [TasteSeed(name="Avant-Garde", domain=CulturalDomain.ARTS)]
        plan = await self.planner.plan_48h(city_hub="Berlin", taste_seeds=seeds)
        self.assertGreaterEqual(plan.transit_efficiency_score, 0.75)


# ============================================================================
# 7. ReAct Planning Loop & 5-State Transitions Suite
# ============================================================================

class TestReActPlanningLoopAndStateTransitions(unittest.IsolatedAsyncioTestCase):
    """Verifies ReAct execution, 5-state transitions, and reproducibility."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_react_step_count_and_trace(self):
        seeds = [TasteSeed(name="Avant-Garde", domain=CulturalDomain.ARTS)]
        plan = await self.planner.plan_48h(city_hub="Berlin", taste_seeds=seeds)
        self.assertGreaterEqual(plan.react_steps_count, 8)
        self.assertIn("react_trace", plan.metadata)
        trace = plan.metadata["react_trace"]
        self.assertIsInstance(trace, list)
        self.assertGreater(len(trace), 0)

    async def test_five_state_transitions_logged(self):
        seeds = [TasteSeed(name="Jazz", domain=CulturalDomain.MUSIC)]
        plan = await self.planner.plan_48h(city_hub="Tokyo", taste_seeds=seeds)
        trace = plan.metadata["react_trace"]
        states = {s["state"] for s in trace}
        expected_states = {"thought", "action", "observation", "reflection", "synthesis"}
        self.assertTrue(expected_states.issubset(states), f"Missing states: {expected_states - states}")

    async def test_backtracking_trace_on_conflict(self):
        seeds = [TasteSeed(name="Filter Coffee", domain=CulturalDomain.DINING)]
        plan = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        trace = plan.metadata["react_trace"]
        backtrack_steps = [s for s in trace if s.get("backtrack_occurred")]
        self.assertGreater(len(backtrack_steps), 0)
        self.assertGreaterEqual(plan.metadata.get("backtrack_count", 0), 1)

    async def test_deterministic_reproducibility(self):
        seeds = [TasteSeed(name="Dosa", domain=CulturalDomain.DINING)]
        plan1 = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        plan2 = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        self.assertEqual([i.entity.id for i in plan1.items], [i.entity.id for i in plan2.items])
        self.assertEqual(plan1.cultural_coherence_score, plan2.cultural_coherence_score)
        self.assertEqual(plan1.domain_diversity_score, plan2.domain_diversity_score)
        self.assertEqual(plan1.transit_efficiency_score, plan2.transit_efficiency_score)


# ============================================================================
# 8. Mathematical Scoring & Formula Unit Properties Suite
# ============================================================================

class TestMetricFormulasUnitEmpirical(unittest.IsolatedAsyncioTestCase):
    """Verifies mathematical properties of scoring functions directly."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_mathematical_metric_bounds_and_properties(self):
        seeds = [TasteSeed(name="Cinema", domain=CulturalDomain.CINEMA)]
        plan = await self.planner.plan_48h(city_hub="Mumbai", taste_seeds=seeds)

        # 1. Bounds verification
        self.assertGreaterEqual(plan.cultural_coherence_score, 0.0)
        self.assertLessEqual(plan.cultural_coherence_score, 1.0)
        self.assertGreaterEqual(plan.domain_diversity_score, 0.0)
        self.assertLessEqual(plan.domain_diversity_score, 1.0)
        self.assertGreaterEqual(plan.transit_efficiency_score, 0.0)
        self.assertLessEqual(plan.transit_efficiency_score, 1.0)

        # 2. Diversity verification
        calc_div = calculate_domain_diversity_score(plan.items)
        self.assertEqual(plan.domain_diversity_score, calc_div)

        # 3. Transit efficiency verification
        calc_transit = calculate_transit_efficiency_score(plan.items)
        self.assertEqual(plan.transit_efficiency_score, calc_transit)

    async def test_transit_efficiency_penalty_on_excess_transit(self):
        seeds = [TasteSeed(name="Jazz", domain=CulturalDomain.MUSIC)]
        plan = await self.planner.plan_48h(city_hub="Tokyo", taste_seeds=seeds)
        normal_score = calculate_transit_efficiency_score(plan.items)

        # Create copy with an excessive leg of 50 minutes (>45 min spatial constraint)
        modified_items = [i.model_copy(deep=True) for i in plan.items]
        modified_items[3].transit_from_previous_min = 50
        penalized_score = calculate_transit_efficiency_score(modified_items)

        self.assertLess(penalized_score, normal_score)
        self.assertGreaterEqual(normal_score - penalized_score, 0.20)


# ============================================================================
# 9. Adversarial & Edge Cases Suite
# ============================================================================

class TestPlannerAdversarialAndEdgeCases(unittest.IsolatedAsyncioTestCase):
    """Verifies robustness against invalid inputs and boundary conditions."""

    async def asyncSetUp(self):
        self.client = QlooClient(use_mock_fallback=True)
        self.planner = ReActPlanner(client=self.client)

    async def asyncTearDown(self):
        await self.client.close()

    async def test_empty_seeds_raises_value_error(self):
        with self.assertRaises(ValueError):
            await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=[])

    async def test_blank_hub_raises_value_error(self):
        seeds = [TasteSeed(name="Music", domain=CulturalDomain.MUSIC)]
        with self.assertRaises(ValueError):
            await self.planner.plan_48h(city_hub="   ", taste_seeds=seeds)

    async def test_unsupported_hub_raises_qloo_error(self):
        seeds = [TasteSeed(name="Music", domain=CulturalDomain.MUSIC)]
        with self.assertRaises(QlooInvalidHubError):
            await self.planner.plan_48h(city_hub="Atlantis", taste_seeds=seeds)

    async def test_extreme_weights_do_not_crash(self):
        seeds = [
            TasteSeed(name="Extreme High", domain=CulturalDomain.MUSIC, weight=2.0),
            TasteSeed(name="Extreme Low", domain=CulturalDomain.DINING, weight=0.0),
        ]
        plan = await self.planner.plan_48h(city_hub="Bangalore", taste_seeds=seeds)
        self.assertEqual(len(plan.items), 8)
        self.assertGreaterEqual(plan.cultural_coherence_score, 0.50)
