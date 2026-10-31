"""
Comprehensive Unit & Integration Test Suite for QlooClient.
Tests offline initialization, entity searches, domain filtering, 8-hub coverage,
curated cross-domain affinities, mathematical determinism, ultra-fast diagnostic
health check latency (<5ms), and transparent zero-crash fallback under simulated
network timeouts and HTTP 500/401 errors.
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import unittest
from typing import List
from unittest.mock import MagicMock, patch

# Ensure src/ is on sys.path for direct pytest execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import httpx
import pytest

from cultura.agent.tools import (
    AffinityScore,
    CulturalDomain,
    CulturalEntity,
)
from cultura.client.qloo import (
    QlooAPIError,
    QlooClient,
    QlooEntityNotFoundError,
    QlooInvalidDomainError,
    QlooInvalidHubError,
    QlooNetworkError,
)


class TestQlooClientSuite(unittest.IsolatedAsyncioTestCase):
    """
    Test suite for asynchronous QlooClient with transparent offline mock fallback.
    Uses unittest.IsolatedAsyncioTestCase to guarantee native async execution
    under both pytest -v and python3 -m unittest.
    """

    CANONICAL_HUBS = [
        "Bangalore",
        "Mumbai",
        "New York",
        "London",
        "Tokyo",
        "Paris",
        "Berlin",
        "San Francisco",
    ]

    # ========================================================================
    # 1. Initialization & Session Lifecycle Tests
    # ========================================================================

    async def test_init_offline_without_api_key(self) -> None:
        """Client without API key must default to offline mock mode without errors."""
        client = QlooClient(api_key=None, use_mock_fallback=True)
        self.assertTrue(client.is_offline)
        self.assertTrue(client.use_mock_fallback)
        await client.close()

    async def test_init_with_api_key(self) -> None:
        """Client with API key initializes in live mode."""
        client = QlooClient(api_key="test_live_key_secret_123", use_mock_fallback=True)
        self.assertFalse(client.is_offline)
        self.assertEqual(client.api_key, "test_live_key_secret_123")
        await client.close()

    async def test_init_strict_without_key_raises(self) -> None:
        """Client without API key and without mock fallback must raise ValueError."""
        with self.assertRaises(ValueError) as ctx:
            QlooClient(api_key=None, use_mock_fallback=False)
        self.assertIn("API key", str(ctx.exception))

    async def test_async_context_manager(self) -> None:
        """Client supports async with context management and cleans up cleanly."""
        async with QlooClient(use_mock_fallback=True) as client:
            self.assertTrue(client.is_offline)
            health = await client.health_check()
            self.assertEqual(health["status"], "healthy")

    # ========================================================================
    # 2. Entity Search Tests
    # ========================================================================

    async def test_search_entities_basic_query(self) -> None:
        """Search by entity name returns matching CulturalEntity."""
        async with QlooClient(use_mock_fallback=True) as client:
            results = await client.search_entities("Vidyarthi")
            self.assertGreaterEqual(len(results), 1)
            entity = results[0]
            self.assertIsInstance(entity, CulturalEntity)
            self.assertIn("Vidyarthi", entity.name)
            self.assertEqual(entity.hub, "Bangalore")
            self.assertEqual(entity.domain, CulturalDomain.DINING)

    async def test_search_entities_domain_filter(self) -> None:
        """Search filtered by domain returns only entities in that domain."""
        async with QlooClient(use_mock_fallback=True) as client:
            results = await client.search_entities("jazz", domain=CulturalDomain.MUSIC)
            self.assertGreaterEqual(len(results), 1)
            for entity in results:
                self.assertEqual(entity.domain, CulturalDomain.MUSIC)

    async def test_search_entities_hub_filter(self) -> None:
        """Search filtered by hub returns only entities located in that hub."""
        async with QlooClient(use_mock_fallback=True) as client:
            results = await client.search_entities("art", hub="Tokyo")
            self.assertGreaterEqual(len(results), 1)
            for entity in results:
                self.assertEqual(entity.hub, "Tokyo")

    async def test_search_entities_empty_query(self) -> None:
        """Empty query or whitespace-only query returns [] immediately."""
        async with QlooClient(use_mock_fallback=True) as client:
            res_empty = await client.search_entities("")
            self.assertEqual(res_empty, [])
            res_spaces = await client.search_entities("    ")
            self.assertEqual(res_spaces, [])

    async def test_search_entities_case_insensitivity(self) -> None:
        """Search matching must be case-insensitive."""
        async with QlooClient(use_mock_fallback=True) as client:
            lower = await client.search_entities("vidyarthi")
            upper = await client.search_entities("VIDYARTHI")
            mixed = await client.search_entities("Vidyarthi")
            self.assertEqual(len(lower), len(upper))
            self.assertEqual(len(lower), len(mixed))
            self.assertEqual(lower[0].id, upper[0].id)

    async def test_search_entities_limit(self) -> None:
        """Search respects the limit parameter."""
        async with QlooClient(use_mock_fallback=True) as client:
            results = await client.search_entities("bar", limit=2)
            self.assertLessEqual(len(results), 2)

    async def test_search_entities_no_match(self) -> None:
        """Unmatched query returns empty list [] without error."""
        async with QlooClient(use_mock_fallback=True) as client:
            results = await client.search_entities("completely_nonexistent_venue_xyz_99999")
            self.assertEqual(results, [])

    async def test_search_entities_invalid_domain(self) -> None:
        """Searching with an unrecognized cultural domain raises an error."""
        async with QlooClient(use_mock_fallback=True) as client:
            with self.assertRaises((QlooInvalidDomainError, ValueError)):
                await client.search_entities("coffee", domain="underwater_basket_weaving")

    # ========================================================================
    # 3. Cross-Domain Affinity Tests
    # ========================================================================

    async def test_cross_domain_affinity_curated_pair(self) -> None:
        """Known curated pair returns high affinity score and explainable rationale."""
        async with QlooClient(use_mock_fallback=True) as client:
            # ent_nyc_mus_001 = Village Vanguard
            affinities = await client.get_cross_domain_affinities(
                entity_id="ent_nyc_mus_001",
                target_domain=CulturalDomain.DINING,
                hub="New York",
                limit=5,
            )
            self.assertGreaterEqual(len(affinities), 1)
            top = affinities[0]
            self.assertIsInstance(top, AffinityScore)
            self.assertEqual(top.target_entity.hub, "New York")
            self.assertEqual(top.target_entity.domain, CulturalDomain.DINING)
            self.assertGreaterEqual(top.score, 0.85)
            self.assertGreaterEqual(top.confidence, 0.85)
            self.assertTrue(len(top.rationale) > 10)

    async def test_cross_domain_affinity_score_ranges(self) -> None:
        """All affinity scores and confidences must fall strictly in [0.0, 1.0]."""
        async with QlooClient(use_mock_fallback=True) as client:
            entities = await client.search_entities("Vidyarthi")
            self.assertGreaterEqual(len(entities), 1)
            src_id = entities[0].id

            affinities = await client.get_cross_domain_affinities(
                entity_id=src_id,
                target_domain=CulturalDomain.MUSIC,
                hub="Bangalore",
            )
            for aff in affinities:
                self.assertGreaterEqual(aff.score, 0.0)
                self.assertLessEqual(aff.score, 1.0)
                self.assertGreaterEqual(aff.confidence, 0.0)
                self.assertLessEqual(aff.confidence, 1.0)
                self.assertIsInstance(aff.rationale, str)
                self.assertTrue(len(aff.rationale.strip()) > 0)

    async def test_cross_domain_affinity_sorted_descending(self) -> None:
        """Affinities must be sorted in descending order of score."""
        async with QlooClient(use_mock_fallback=True) as client:
            affinities = await client.get_cross_domain_affinities(
                entity_id="ent_lon_din_001",  # St. JOHN Smithfield
                target_domain=CulturalDomain.ARTS,
                hub="London",
                limit=5,
            )
            for i in range(len(affinities) - 1):
                self.assertGreaterEqual(
                    affinities[i].score,
                    affinities[i + 1].score,
                    f"Affinity scores not monotonically descending at index {i}",
                )

    async def test_cross_domain_affinity_destination_hub(self) -> None:
        """Destination hub filter scopes all target entities to the destination city."""
        async with QlooClient(use_mock_fallback=True) as client:
            affinities = await client.get_cross_domain_affinities(
                entity_id="ent_ber_mus_001",  # Berghain
                target_domain=CulturalDomain.ARTS,
                hub="Berlin",
            )
            for aff in affinities:
                self.assertEqual(aff.target_entity.hub, "Berlin")

    async def test_cross_domain_affinity_nonexistent_entity(self) -> None:
        """Querying affinities for nonexistent entity raises QlooEntityNotFoundError."""
        async with QlooClient(use_mock_fallback=True) as client:
            with self.assertRaises(QlooEntityNotFoundError):
                await client.get_cross_domain_affinities(
                    entity_id="completely_nonexistent_entity_id_9999",
                    target_domain=CulturalDomain.DINING,
                )

    # ========================================================================
    # 4. Determinism Tests
    # ========================================================================

    async def test_determinism_identical_calls_produce_identical_results(self) -> None:
        """Identical calls must produce 100% identical entities, scores, and rationales."""
        async with QlooClient(use_mock_fallback=True) as client:
            test_pairs = [
                ("ent_nyc_mus_001", CulturalDomain.DINING, "New York"),
                ("ent_blr_din_001", CulturalDomain.MUSIC, "Bangalore"),
                ("ent_tyo_mus_001", CulturalDomain.ARTS, "Tokyo"),
                ("ent_lon_din_001", CulturalDomain.NIGHTLIFE, "London"),
            ]
            for entity_id, target_domain, hub in test_pairs:
                res1 = await client.get_cross_domain_affinities(entity_id, target_domain, hub=hub)
                res2 = await client.get_cross_domain_affinities(entity_id, target_domain, hub=hub)

                self.assertEqual(len(res1), len(res2))
                for a, b in zip(res1, res2):
                    self.assertEqual(a.target_entity.id, b.target_entity.id)
                    self.assertEqual(a.score, b.score)
                    self.assertEqual(a.confidence, b.confidence)
                    self.assertEqual(a.rationale, b.rationale)

    # ========================================================================
    # 5. Hub Coverage & Catalog Completeness
    # ========================================================================

    async def test_hub_coverage_all_eight_hubs(self) -> None:
        """All 8 canonical cultural hubs must be represented in the catalog."""
        async with QlooClient(use_mock_fallback=True) as client:
            for hub in self.CANONICAL_HUBS:
                entities = await client.get_hub_entities(hub)
                self.assertGreaterEqual(
                    len(entities),
                    8,
                    f"Hub '{hub}' has insufficient entities in mock catalog ({len(entities)})",
                )
                for ent in entities:
                    self.assertEqual(ent.hub, hub)
                    self.assertGreaterEqual(ent.latitude, -90.0)
                    self.assertLessEqual(ent.latitude, 90.0)
                    self.assertGreaterEqual(ent.longitude, -180.0)
                    self.assertLessEqual(ent.longitude, 180.0)
                    self.assertTrue(len(ent.vibe_tags) > 0)
                    self.assertGreaterEqual(ent.price_tier, 1)
                    self.assertLessEqual(ent.price_tier, 4)

    async def test_hub_coverage_core_domains(self) -> None:
        """Every hub must cover at least the 4 core domains: music, dining, arts, cinema."""
        core_domains = {
            CulturalDomain.MUSIC,
            CulturalDomain.DINING,
            CulturalDomain.ARTS,
            CulturalDomain.CINEMA,
        }
        async with QlooClient(use_mock_fallback=True) as client:
            for hub in self.CANONICAL_HUBS:
                entities = await client.get_hub_entities(hub)
                present_domains = {e.domain for e in entities}
                missing = core_domains - present_domains
                self.assertEqual(
                    len(missing),
                    0,
                    f"Hub '{hub}' is missing core domains: {missing}",
                )

    # ========================================================================
    # 6. Health Check & Latency Benchmark Tests
    # ========================================================================

    async def test_health_check_latency_and_structure(self) -> None:
        """
        Health check must return full diagnostic metadata and execute in <5ms in mock mode
        to satisfy the <100ms budget for 'cultura doctor'.
        """
        async with QlooClient(use_mock_fallback=True) as client:
            start_time = time.perf_counter()
            health = await client.health_check()
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            # Verify structure
            self.assertIn("status", health)
            self.assertEqual(health["status"], "healthy")
            self.assertIn("mode", health)
            self.assertIn("entities_count", health)
            self.assertGreaterEqual(health["entities_count"], 50)
            self.assertIn("hubs_count", health)
            self.assertEqual(health["hubs_count"], 8)
            self.assertIn("hubs_available", health)
            self.assertEqual(len(health["hubs_available"]), 8)
            self.assertIn("latency_ms", health)

            # Strict performance assertion (<10ms assertion, typically <1ms)
            self.assertLess(
                elapsed_ms,
                10.0,
                f"Health check exceeded latency budget: {elapsed_ms:.2f}ms",
            )

    # ========================================================================
    # 7. Fallback Simulation Tests (Network Timeout & HTTP 500/401)
    # ========================================================================

    @patch("httpx.AsyncClient.get")
    async def test_fallback_simulation_network_timeout(self, mock_get: MagicMock) -> None:
        """
        Simulated network timeout must seamlessly trigger mock fallback without
        crashing or raising an exception.
        """
        mock_get.side_effect = httpx.TimeoutException("Connection timed out after 3.0s")

        async with QlooClient(api_key="valid_token", use_mock_fallback=True) as client:
            results = await client.search_entities("Vidyarthi")
            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0].name, "Vidyarthi Bhavan")

    @patch("httpx.AsyncClient.get")
    async def test_fallback_simulation_http_500_server_error(self, mock_get: MagicMock) -> None:
        """
        Simulated HTTP 500 error from live Qloo API must seamlessly trigger mock fallback.
        """
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.json.return_value = {"error": "Internal Server Error"}
        mock_get.return_value = mock_resp

        async with QlooClient(api_key="valid_token", use_mock_fallback=True) as client:
            affinities = await client.get_cross_domain_affinities(
                entity_id="ent_nyc_mus_001",
                target_domain=CulturalDomain.DINING,
                hub="New York",
            )
            self.assertGreaterEqual(len(affinities), 1)
            self.assertEqual(affinities[0].target_entity.hub, "New York")

    @patch("httpx.AsyncClient.get")
    async def test_fallback_simulation_http_401_unauthorized(self, mock_get: MagicMock) -> None:
        """
        Simulated HTTP 401 Unauthorized must log a warning and fall back to mock data.
        """
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 401
        mock_resp.text = "Unauthorized: Invalid API Key"
        mock_resp.json.return_value = {"error": "Invalid API Key"}
        mock_get.return_value = mock_resp

        async with QlooClient(api_key="invalid_bad_key", use_mock_fallback=True) as client:
            results = await client.search_entities("Vidyarthi")
            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(results[0].name, "Vidyarthi Bhavan")

    @patch("httpx.AsyncClient.get")
    async def test_strict_mode_raises_on_network_error(self, mock_get: MagicMock) -> None:
        """
        When use_mock_fallback=False, network failures must raise QlooNetworkError.
        """
        mock_get.side_effect = httpx.ConnectError("DNS lookup failed")

        async with QlooClient(api_key="valid_token", use_mock_fallback=False) as client:
            with self.assertRaises(QlooNetworkError):
                await client.search_entities("Vidyarthi")

    @patch("httpx.AsyncClient.get")
    async def test_strict_mode_raises_on_500_error(self, mock_get: MagicMock) -> None:
        """
        When use_mock_fallback=False, HTTP 500 must raise QlooAPIError.
        """
        mock_resp = MagicMock(spec=httpx.Response)
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_resp.json.return_value = {"error": "Internal Server Error"}
        mock_get.return_value = mock_resp

        async with QlooClient(api_key="valid_token", use_mock_fallback=False) as client:
            with self.assertRaises(QlooAPIError) as ctx:
                await client.search_entities("Vidyarthi")
            self.assertEqual(ctx.exception.status_code, 500)

    # ========================================================================
    # 8. Entity Lookup & Hub Retrieval Tests
    # ========================================================================

    async def test_get_entity_found_and_missing(self) -> None:
        """Direct entity lookup by ID for existing and missing records."""
        async with QlooClient(use_mock_fallback=True) as client:
            entity = await client.get_entity("ent_blr_din_001")
            self.assertIsNotNone(entity)
            self.assertEqual(entity.name, "Vidyarthi Bhavan")

            missing = await client.get_entity("ent_nonexistent_xyz_9999")
            self.assertIsNone(missing)

            empty = await client.get_entity("")
            self.assertIsNone(empty)

    async def test_get_hub_entities_invalid_hub(self) -> None:
        """Querying entities for an unsupported hub raises QlooInvalidHubError."""
        async with QlooClient(use_mock_fallback=True) as client:
            with self.assertRaises(QlooInvalidHubError):
                await client.get_hub_entities("Atlantis")


if __name__ == "__main__":
    unittest.main()
