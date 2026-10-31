"""
Empirical Adversarial Test Suite for CULTURA Pydantic V2 Schemas & Schedule Invariants.
Tests edge cases, boundary values, invalid inputs, and adversarial schedule attacks
against src/cultura/agent/tools.py.
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import os
import sys
import unittest
import pytest
from pydantic import ValidationError

# Ensure src/ is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from cultura.agent.tools import (
    AffinityScore,
    CulturalDomain,
    CulturalEntity,
    GetCrossDomainAffinitiesInput,
    GetEntityInput,
    GetHubEntitiesInput,
    ItineraryItem,
    ItineraryPlan,
    SearchEntitiesInput,
    TasteSeed,
    TimeSlot,
    TransitEvaluationInput,
    haversine_transit_minutes,
)


def _make_dummy_entity(
    entity_id: str = "ent_test_001",
    name: str = "Test Venue",
    domain: CulturalDomain = CulturalDomain.DINING,
    hub: str = "Bangalore",
    lat: float = 12.9716,
    lon: float = 77.5946,
    price_tier: int = 2,
) -> CulturalEntity:
    """Helper to generate a valid CulturalEntity."""
    return CulturalEntity(
        id=entity_id,
        name=name,
        domain=domain,
        hub=hub,
        latitude=lat,
        longitude=lon,
        price_tier=price_tier,
        vibe_tags=["curated", "authentic"],
        description="A great test cultural spot.",
    )


def _make_dummy_item(
    day: int,
    slot: TimeSlot,
    entity: CulturalEntity,
    affinity_score: float = 0.9,
) -> ItineraryItem:
    """Helper to generate a valid ItineraryItem."""
    return ItineraryItem(
        day=day,
        slot=slot,
        entity=entity,
        affinity_score=affinity_score,
        curator_notes="Curator selection for testing.",
    )


def _make_8_distinct_entities(domains=None) -> list[CulturalEntity]:
    """Helper to create 8 unique CulturalEntity instances across specified domains."""
    if domains is None:
        domains = [
            CulturalDomain.DINING,
            CulturalDomain.MUSIC,
            CulturalDomain.ARTS,
            CulturalDomain.NIGHTLIFE,
            CulturalDomain.CINEMA,
            CulturalDomain.LITERARY,
            CulturalDomain.FASHION,
            CulturalDomain.DINING,
        ]
    return [
        _make_dummy_entity(
            entity_id=f"ent_unique_{i:03d}",
            name=f"Unique Venue {i}",
            domain=domains[i],
            lat=12.97 + (i * 0.01),
            lon=77.59 + (i * 0.01),
        )
        for i in range(8)
    ]


class TestTasteSeedFuzzing(unittest.TestCase):
    """Adversarial stress-testing of TasteSeed Pydantic model."""

    def test_invalid_domain_raises(self):
        """TasteSeed must reject unrecognized or nonsensical domains."""
        invalid_domains = ["quantum_physics", "sports", "crypto", "astronomy", "123", "", "   "]
        for bad_domain in invalid_domains:
            with self.subTest(domain=bad_domain):
                with self.assertRaises(ValidationError):
                    TasteSeed(name="John Coltrane", domain=bad_domain, weight=1.0)

    def test_domain_normalization_synonyms(self):
        """TasteSeed should normalize synonyms and colloquial domain strings."""
        mappings = {
            "food": CulturalDomain.DINING,
            "restaurant": CulturalDomain.DINING,
            "art": CulturalDomain.ARTS,
            "museum": CulturalDomain.ARTS,
            "gallery": CulturalDomain.ARTS,
            "concert": CulturalDomain.MUSIC,
            "audio": CulturalDomain.MUSIC,
            "film": CulturalDomain.CINEMA,
            "movies": CulturalDomain.CINEMA,
            "books": CulturalDomain.LITERARY,
            "reading": CulturalDomain.LITERARY,
            "bar": CulturalDomain.NIGHTLIFE,
            "cocktails": CulturalDomain.NIGHTLIFE,
            "clubs": CulturalDomain.NIGHTLIFE,
            "style": CulturalDomain.FASHION,
            "apparel": CulturalDomain.FASHION,
        }
        for alias, expected_enum in mappings.items():
            with self.subTest(alias=alias):
                seed = TasteSeed(name="Test Anchor", domain=alias, weight=1.0)
                self.assertEqual(seed.domain, expected_enum)

    def test_negative_weight_raises(self):
        """TasteSeed must reject negative weights (ge=0.0)."""
        negative_weights = [-0.001, -0.1, -1.0, -100.0]
        for w in negative_weights:
            with self.subTest(weight=w):
                with self.assertRaises(ValidationError):
                    TasteSeed(name="Aesthetic Anchor", domain=CulturalDomain.MUSIC, weight=w)

    def test_weight_greater_than_two_raises(self):
        """TasteSeed must reject weights exceeding 2.0 (le=2.0)."""
        excessive_weights = [2.001, 2.1, 3.0, 10.0, 999.0]
        for w in excessive_weights:
            with self.subTest(weight=w):
                with self.assertRaises(ValidationError):
                    TasteSeed(name="Aesthetic Anchor", domain=CulturalDomain.MUSIC, weight=w)

    def test_valid_boundary_weights_pass(self):
        """TasteSeed must accept valid boundary weights 0.0, 1.0, 2.0."""
        for w in [0.0, 0.001, 0.5, 1.0, 1.5, 1.999, 2.0]:
            with self.subTest(weight=w):
                seed = TasteSeed(name="Valid Seed", domain=CulturalDomain.ARTS, weight=w)
                self.assertAlmostEqual(seed.weight, w)

    def test_empty_or_whitespace_name_raises(self):
        """TasteSeed must reject empty or whitespace-only names."""
        for bad_name in ["", " ", "   ", "\t\n"]:
            with self.subTest(name=bad_name):
                with self.assertRaises(ValidationError):
                    TasteSeed(name=bad_name, domain=CulturalDomain.MUSIC)

    def test_excessive_name_length_raises(self):
        """TasteSeed must reject names longer than 100 characters."""
        long_name = "X" * 101
        with self.assertRaises(ValidationError):
            TasteSeed(name=long_name, domain=CulturalDomain.CINEMA)


class TestCulturalEntityFuzzing(unittest.TestCase):
    """Adversarial stress-testing of CulturalEntity Pydantic model."""

    def test_invalid_price_tiers_raise(self):
        """Price tier must be within 1..4 (reject 0, 5, -1, 99)."""
        invalid_tiers = [0, 5, -1, -5, 10, 100]
        for pt in invalid_tiers:
            with self.subTest(price_tier=pt):
                with self.assertRaises(ValidationError):
                    _make_dummy_entity(price_tier=pt)

    def test_valid_price_tiers_pass(self):
        """Price tiers 1, 2, 3, 4 must all validate successfully."""
        for pt in [1, 2, 3, 4]:
            with self.subTest(price_tier=pt):
                entity = _make_dummy_entity(price_tier=pt)
                self.assertEqual(entity.price_tier, pt)

    def test_invalid_latitude_raises(self):
        """Latitude must be within [-90.0, 90.0]."""
        invalid_lats = [90.0001, 91.0, 180.0, 360.0, -90.0001, -91.0, -500.0]
        for lat in invalid_lats:
            with self.subTest(latitude=lat):
                with self.assertRaises(ValidationError):
                    _make_dummy_entity(lat=lat)

    def test_invalid_longitude_raises(self):
        """Longitude must be within [-180.0, 180.0]."""
        invalid_lons = [180.0001, 181.0, 270.0, 360.0, -180.0001, -181.0, -999.0]
        for lon in invalid_lons:
            with self.subTest(longitude=lon):
                with self.assertRaises(ValidationError):
                    _make_dummy_entity(lon=lon)

    def test_valid_boundary_coordinates_pass(self):
        """Boundary coordinates (-90, +90, -180, +180) must be accepted."""
        cases = [
            (-90.0, -180.0),
            (90.0, 180.0),
            (0.0, 0.0),
            (-45.0, 90.0),
            (12.9716, 77.5946),
        ]
        for lat, lon in cases:
            with self.subTest(lat=lat, lon=lon):
                ent = _make_dummy_entity(lat=lat, lon=lon)
                self.assertAlmostEqual(ent.latitude, lat)
                self.assertAlmostEqual(ent.longitude, lon)

    def test_alias_reconciliation(self):
        """Entity must correctly parse aliases like lat, lon, lng, tags, city, vibe."""
        data = {
            "id": "ent_alias_test",
            "name": "Alias Lounge",
            "domain": "nightlife",
            "city": "Tokyo",
            "lat": 35.6762,
            "lng": 139.6503,
            "tags": ["ambient", "whisky"],
            "vibe": "Moody minimalist bar",
            "price_tier": 3,
        }
        ent = CulturalEntity.model_validate(data)
        self.assertEqual(ent.hub, "Tokyo")
        self.assertAlmostEqual(ent.latitude, 35.6762)
        self.assertAlmostEqual(ent.longitude, 139.6503)
        self.assertEqual(ent.vibe_tags, ["ambient", "whisky"])
        self.assertEqual(ent.description, "Moody minimalist bar")
        self.assertEqual(ent.domain, CulturalDomain.NIGHTLIFE)
        # Convenience properties
        self.assertEqual(ent.lat, 35.6762)
        self.assertEqual(ent.lon, 139.6503)
        self.assertEqual(ent.tags, ["ambient", "whisky"])


class TestAffinityScoreFuzzing(unittest.TestCase):
    """Adversarial stress-testing of AffinityScore Pydantic model."""

    def setUp(self):
        self.target = _make_dummy_entity()

    def test_score_below_zero_raises(self):
        """Score must reject values < 0.0."""
        for bad_score in [-0.0001, -0.1, -1.0, -50.0]:
            with self.subTest(score=bad_score):
                with self.assertRaises(ValidationError):
                    AffinityScore(
                        entity_id="seed_001",
                        target_entity=self.target,
                        score=bad_score,
                        confidence=0.85,
                        rationale="Test match.",
                    )

    def test_score_above_one_raises(self):
        """Score must reject values > 1.0."""
        for bad_score in [1.0001, 1.1, 2.0, 100.0]:
            with self.subTest(score=bad_score):
                with self.assertRaises(ValidationError):
                    AffinityScore(
                        entity_id="seed_001",
                        target_entity=self.target,
                        score=bad_score,
                        confidence=0.85,
                        rationale="Test match.",
                    )

    def test_confidence_below_zero_raises(self):
        """Confidence must reject values < 0.0."""
        for bad_conf in [-0.0001, -0.5, -1.0]:
            with self.subTest(confidence=bad_conf):
                with self.assertRaises(ValidationError):
                    AffinityScore(
                        entity_id="seed_001",
                        target_entity=self.target,
                        score=0.9,
                        confidence=bad_conf,
                        rationale="Test match.",
                    )

    def test_confidence_above_one_raises(self):
        """Confidence must reject values > 1.0."""
        for bad_conf in [1.0001, 1.5, 2.0, 10.0]:
            with self.subTest(confidence=bad_conf):
                with self.assertRaises(ValidationError):
                    AffinityScore(
                        entity_id="seed_001",
                        target_entity=self.target,
                        score=0.9,
                        confidence=bad_conf,
                        rationale="Test match.",
                    )

    def test_valid_boundary_scores_and_confidence_pass(self):
        """Boundary scores [0.0, 1.0] and confidences [0.0, 1.0] must pass."""
        for s in [0.0, 0.5, 1.0]:
            for c in [0.0, 0.5, 1.0]:
                aff = AffinityScore(
                    entity_id="seed_001",
                    target_entity=self.target,
                    score=s,
                    confidence=c,
                    rationale="Boundary test.",
                )
                self.assertAlmostEqual(aff.score, s)
                self.assertAlmostEqual(aff.confidence, c)
                self.assertEqual(aff.target_domain, self.target.domain)

    def test_affinity_aliases_and_properties(self):
        """AffinityScore should resolve source_entity_id, reasoning, and taste_overlap_tags."""
        data = {
            "source_entity_id": "seed_src_99",
            "target_entity": self.target.model_dump(),
            "score": 0.88,
            "reasoning": "Deep aesthetic overlap in brutalist acoustics.",
            "taste_overlap_tags": ["minimalist", "acoustics"],
        }
        aff = AffinityScore.model_validate(data)
        self.assertEqual(aff.entity_id, "seed_src_99")
        self.assertEqual(aff.source_entity_id, "seed_src_99")
        self.assertEqual(aff.rationale, "Deep aesthetic overlap in brutalist acoustics.")
        self.assertEqual(aff.reasoning, "Deep aesthetic overlap in brutalist acoustics.")
        self.assertEqual(aff.shared_tags, ["minimalist", "acoustics"])


class TestItineraryItemFuzzing(unittest.TestCase):
    """Adversarial stress-testing of ItineraryItem Pydantic model."""

    def setUp(self):
        self.entity = _make_dummy_entity()

    def test_invalid_day_raises(self):
        """Day must be 1 or 2 (reject 0, 3, -1, 5)."""
        for bad_day in [0, 3, -1, 5, 10]:
            with self.subTest(day=bad_day):
                with self.assertRaises(ValidationError):
                    ItineraryItem(day=bad_day, slot=TimeSlot.MORNING, entity=self.entity)

    def test_valid_days_pass(self):
        """Days 1 and 2 must validate successfully."""
        for valid_day in [1, 2]:
            item = ItineraryItem(day=valid_day, slot=TimeSlot.MORNING, entity=self.entity)
            self.assertEqual(item.day, valid_day)

    def test_invalid_slot_raises(self):
        """Invalid time slot must raise ValidationError."""
        for bad_slot in ["brunch", "midnight", "dusk", ""]:
            with self.subTest(slot=bad_slot):
                with self.assertRaises(ValidationError):
                    ItineraryItem(day=1, slot=bad_slot, entity=self.entity)

    def test_negative_transit_time_raises(self):
        """Transit time from previous venue cannot be negative."""
        for bad_transit in [-1, -15, -100]:
            with self.subTest(transit=bad_transit):
                with self.assertRaises(ValidationError):
                    ItineraryItem(
                        day=1,
                        slot=TimeSlot.AFTERNOON,
                        entity=self.entity,
                        transit_from_previous_min=bad_transit,
                    )

    def test_invalid_affinity_score_raises(self):
        """Affinity score must be bounded within [0.0, 1.0]."""
        for bad_score in [-0.01, 1.01, 2.0]:
            with self.subTest(score=bad_score):
                with self.assertRaises(ValidationError):
                    ItineraryItem(
                        day=1,
                        slot=TimeSlot.EVENING,
                        entity=self.entity,
                        affinity_score=bad_score,
                    )

    def test_time_window_auto_population(self):
        """When time_window is empty or omitted, defaults to slot.default_time_window."""
        item = ItineraryItem(day=1, slot=TimeSlot.MORNING, entity=self.entity)
        self.assertEqual(item.time_window, "09:00 - 12:30")
        self.assertEqual(item.start_time, "09:00")
        self.assertEqual(item.end_time, "12:30")

    def test_alias_reconciliation(self):
        """ItineraryItem must resolve day_number, time_slot, curator_tip, transit_notes aliases."""
        data = {
            "day_number": 2,
            "time_slot": "night",
            "entity": self.entity.model_dump(),
            "curator_tip": "Arrive early for late night jazz jam.",
            "transit_notes": "10 min cab from evening bistro.",
            "transit_from_previous_min": 10,
        }
        item = ItineraryItem.model_validate(data)
        self.assertEqual(item.day, 2)
        self.assertEqual(item.slot, TimeSlot.NIGHT)
        self.assertEqual(item.curator_notes, "Arrive early for late night jazz jam.")
        self.assertEqual(item.curator_tip, "Arrive early for late night jazz jam.")
        self.assertEqual(item.transit_note, "10 min cab from evening bistro.")



class TestItineraryPlanScheduleInvariantFuzzing(unittest.TestCase):
    """
    Empirical Invariant Testing on ItineraryPlan:
    - 7 items (must reject: too short)
    - 9 items (must reject: too long)
    - duplicated entity IDs (must reject: duplicate venues)
    - non-chronological slots (must reject: invalid progression)
    - <3 distinct domains (must reject: domain diversity failure)
    - valid plan with exactly 8 items (must pass)
    """

    def setUp(self):
        self.taste_seeds = [
            TasteSeed(name="Miles Davis", domain=CulturalDomain.MUSIC, weight=1.5),
            TasteSeed(name="Art Deco", domain=CulturalDomain.ARTS, weight=1.0),
        ]
        self.city_hub = "Bangalore"

    def _build_standard_8_items(self, entities=None) -> list[ItineraryItem]:
        """Constructs an exactly chronological sequence of 8 diurnal slots."""
        if entities is None:
            entities = _make_8_distinct_entities()
        slots_sequence = [
            (1, TimeSlot.MORNING),
            (1, TimeSlot.AFTERNOON),
            (1, TimeSlot.EVENING),
            (1, TimeSlot.NIGHT),
            (2, TimeSlot.MORNING),
            (2, TimeSlot.AFTERNOON),
            (2, TimeSlot.EVENING),
            (2, TimeSlot.NIGHT),
        ]
        items = []
        for i, (day, slot) in enumerate(slots_sequence):
            items.append(_make_dummy_item(day=day, slot=slot, entity=entities[i]))
        return items

    def test_valid_plan_with_exactly_8_items_passes(self):
        """A valid 8-item, chronological, diverse, duplicate-free plan must succeed."""
        items = self._build_standard_8_items()
        plan = ItineraryPlan(
            city_hub=self.city_hub,
            taste_seeds=self.taste_seeds,
            items=items,
            cultural_coherence_score=0.92,
            domain_diversity_score=0.88,
            transit_efficiency_score=0.85,
        )
        self.assertEqual(len(plan.items), 8)
        self.assertEqual(plan.city_hub, "Bangalore")
        self.assertEqual(plan.city, "Bangalore")
        self.assertAlmostEqual(plan.cultural_coherence_score, 0.92)

    def test_plan_with_7_items_must_reject_too_short(self):
        """Plan with 7 items must be rejected (too short)."""
        items = self._build_standard_8_items()[:7]  # Drop Day 2 Night
        self.assertEqual(len(items), 7)
        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=items,
            )
        err_msg = str(ctx.exception)
        # Verify rejection mentions item count or too_short
        self.assertTrue(
            "too_short" in err_msg or "at least 8" in err_msg or "exactly 8 items" in err_msg,
            f"Unexpected error message: {err_msg}",
        )

    def test_plan_with_9_items_must_reject_too_long(self):
        """Plan with 9 items must be rejected (too long)."""
        items = self._build_standard_8_items()
        extra_entity = _make_dummy_entity(entity_id="ent_extra_009", name="Extra Venue")
        items.append(_make_dummy_item(day=2, slot=TimeSlot.NIGHT, entity=extra_entity))
        self.assertEqual(len(items), 9)
        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=items,
            )
        err_msg = str(ctx.exception)
        self.assertTrue(
            "too_long" in err_msg or "at most 8" in err_msg or "exactly 8 items" in err_msg,
            f"Unexpected error message: {err_msg}",
        )

    def test_plan_with_duplicated_entity_ids_must_reject(self):
        """Plan with duplicated venue IDs across slots must be rejected."""
        entities = _make_8_distinct_entities()
        # Make venue 0 and venue 4 share the exact same ID
        entities[4] = entities[0]
        items = self._build_standard_8_items(entities=entities)

        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=items,
            )
        err_msg = str(ctx.exception)
        self.assertIn("Duplicate cultural entities detected in itinerary", err_msg)
        self.assertIn(entities[0].id, err_msg)

    def test_plan_with_multiple_duplicated_venues_must_reject(self):
        """Plan where 4 slots repeat the same 2 venues must be rejected."""
        entities = _make_8_distinct_entities()
        entities[1] = entities[0]
        entities[3] = entities[2]
        items = self._build_standard_8_items(entities=entities)

        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=items,
            )
        self.assertIn("Duplicate cultural entities detected in itinerary", str(ctx.exception))

    def test_plan_with_non_chronological_slots_within_same_day_must_reject(self):
        """Plan with swapped slots (e.g. Afternoon before Morning) must be rejected."""
        items = self._build_standard_8_items()
        # Swap Day 1 Morning and Day 1 Afternoon
        items[0], items[1] = items[1], items[0]

        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=items,
            )
        err_msg = str(ctx.exception)
        self.assertIn("Invalid itinerary schedule sequence", err_msg)

    def test_plan_with_non_chronological_days_must_reject(self):
        """Plan with Day 2 items placed before Day 1 items must be rejected."""
        items = self._build_standard_8_items()
        # Put Day 2 first, then Day 1
        inverted_items = items[4:] + items[:4]

        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=inverted_items,
            )
        err_msg = str(ctx.exception)
        self.assertIn("Invalid itinerary schedule sequence", err_msg)

    def test_plan_with_repeated_slot_instead_of_progression_must_reject(self):
        """Plan with repeated slot (e.g. morning, morning, evening, night) must be rejected."""
        items = self._build_standard_8_items()
        # Corrupt Day 1 slot 1 to MORNING as well
        corrupted_item = _make_dummy_item(
            day=1, slot=TimeSlot.MORNING, entity=_make_dummy_entity(entity_id="ent_rep_01")
        )
        items[1] = corrupted_item

        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=items,
            )
        self.assertIn("Invalid itinerary schedule sequence", str(ctx.exception))

    def test_plan_with_under_three_distinct_domains_monocultural_must_reject(self):
        """Plan with all 8 items in 1 domain (DINING only) must be rejected."""
        monocultural_domains = [CulturalDomain.DINING] * 8
        entities = _make_8_distinct_entities(domains=monocultural_domains)
        items = self._build_standard_8_items(entities=entities)

        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=items,
            )
        err_msg = str(ctx.exception)
        self.assertIn("Itinerary lacks cultural breadth: found only 1 unique domain", err_msg)

    def test_plan_with_under_three_distinct_domains_dual_domain_must_reject(self):
        """Plan with only 2 distinct domains (4 DINING, 4 MUSIC) must be rejected."""
        dual_domains = [CulturalDomain.DINING] * 4 + [CulturalDomain.MUSIC] * 4
        entities = _make_8_distinct_entities(domains=dual_domains)
        items = self._build_standard_8_items(entities=entities)

        with self.assertRaises(ValidationError) as ctx:
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=self.taste_seeds,
                items=items,
            )
        err_msg = str(ctx.exception)
        self.assertIn("Itinerary lacks cultural breadth: found only 2 unique domain", err_msg)

    def test_plan_with_exactly_three_distinct_domains_must_pass(self):
        """Boundary test: exactly 3 distinct domains (minimum allowed) must succeed."""
        tri_domains = (
            [CulturalDomain.DINING] * 3
            + [CulturalDomain.MUSIC] * 3
            + [CulturalDomain.ARTS] * 2
        )
        entities = _make_8_distinct_entities(domains=tri_domains)
        items = self._build_standard_8_items(entities=entities)

        plan = ItineraryPlan(
            city_hub=self.city_hub,
            taste_seeds=self.taste_seeds,
            items=items,
        )
        self.assertEqual(len(plan.items), 8)
        unique_domains = {item.entity.domain for item in plan.items}
        self.assertEqual(len(unique_domains), 3)

    def test_plan_with_empty_taste_seeds_must_reject(self):
        """Taste seeds list cannot be empty (min_length=1)."""
        items = self._build_standard_8_items()
        with self.assertRaises(ValidationError):
            ItineraryPlan(
                city_hub=self.city_hub,
                taste_seeds=[],
                items=items,
            )

    def test_plan_with_empty_city_hub_must_reject(self):
        """city_hub cannot be empty string (min_length=1)."""
        items = self._build_standard_8_items()
        with self.assertRaises(ValidationError):
            ItineraryPlan(
                city_hub="",
                taste_seeds=self.taste_seeds,
                items=items,
            )


class TestSpatialAndToolInputValidation(unittest.TestCase):
    """Adversarial stress-testing of ReAct tool inputs and spatial functions."""

    def test_haversine_same_point_minimum_dwell(self):
        """Same point (0 distance) must return the 5-minute minimum transit time."""
        transit_time = haversine_transit_minutes(12.9716, 77.5946, 12.9716, 77.5946)
        self.assertEqual(transit_time, 5)

    def test_haversine_realistic_urban_transit(self):
        """Transit between Bangalore center and Indiranagar (~6km) should take >5 and <45 min."""
        time_min = haversine_transit_minutes(12.9716, 77.5946, 12.9784, 77.6408, speed_kmh=25.0)
        self.assertGreater(time_min, 5)
        self.assertLess(time_min, 45)

    def test_search_entities_input_limit_bounds(self):
        """SearchEntitiesInput must constrain limit to [1, 50]."""
        with self.assertRaises(ValidationError):
            SearchEntitiesInput(query="jazz", limit=0)
        with self.assertRaises(ValidationError):
            SearchEntitiesInput(query="jazz", limit=51)
        valid = SearchEntitiesInput(query="jazz", limit=50)
        self.assertEqual(valid.limit, 50)

    def test_cross_domain_affinities_input_limit_bounds(self):
        """GetCrossDomainAffinitiesInput must constrain limit to [1, 20]."""
        with self.assertRaises(ValidationError):
            GetCrossDomainAffinitiesInput(entity_id="e1", target_domain=CulturalDomain.DINING, limit=0)
        with self.assertRaises(ValidationError):
            GetCrossDomainAffinitiesInput(entity_id="e1", target_domain=CulturalDomain.DINING, limit=21)
        valid = GetCrossDomainAffinitiesInput(entity_id="e1", target_domain=CulturalDomain.DINING, limit=20)
        self.assertEqual(valid.limit, 20)

    def test_transit_evaluation_coordinate_bounds(self):
        """TransitEvaluationInput must enforce valid lat/lon bounds."""
        with self.assertRaises(ValidationError):
            TransitEvaluationInput(
                from_latitude=95.0, from_longitude=0.0, to_latitude=0.0, to_longitude=0.0
            )
        with self.assertRaises(ValidationError):
            TransitEvaluationInput(
                from_latitude=0.0, from_longitude=190.0, to_latitude=0.0, to_longitude=0.0
            )


if __name__ == "__main__":
    unittest.main()
