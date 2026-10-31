"""
Empirical Adversarial Test Suite for QlooClient & Offline Mock Catalog.
Stress-tests concurrency (100 concurrent async calls), extreme inputs (unicode, emojis,
SQL injection, whitespace, boundary limits), invalid domains/hubs, and microsecond
latency benchmarks (<1.0ms mean SLA across 1000 runs).
Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import unittest
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

# Ensure src/ is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

import httpx
import pytest

from cultura.agent.tools import (
    AffinityScore,
    CulturalDomain,
    CulturalEntity,
)
from cultura.client.mock_data import (
    CURATED_AFFINITIES,
    ENTITIES_BY_DOMAIN,
    ENTITIES_BY_HUB,
    ENTITIES_BY_ID,
    MOCK_ENTITIES,
    SUPPORTED_HUBS,
)
from cultura.client.qloo import (
    QlooAPIError,
    QlooClient,
    QlooEntityNotFoundError,
    QlooInvalidDomainError,
    QlooInvalidHubError,
    QlooNetworkError,
)


class TestQlooConcurrencyAdversarial(unittest.IsolatedAsyncioTestCase):
    """
    Concurrency stress testing: Executes 100+ concurrent async calls across
    search_entities, get_cross_domain_affinities, and mixed client operations.
    """

    async def asyncSetUp(self) -> None:
        self.client = QlooClient(use_mock_fallback=True)

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_100_concurrent_searches_across_hubs_and_domains(self) -> None:
        """Execute 100 concurrent search_entities calls with varied parameters."""
        queries = [
            ("jazz", CulturalDomain.MUSIC, "New York"),
            ("dosa", CulturalDomain.DINING, "Bangalore"),
            ("art", CulturalDomain.ARTS, "Paris"),
            ("techno", CulturalDomain.NIGHTLIFE, "Berlin"),
            ("cinema", CulturalDomain.CINEMA, "Mumbai"),
            ("coffee", CulturalDomain.DINING, "Tokyo"),
            ("books", CulturalDomain.LITERARY, "London"),
            ("vintage", CulturalDomain.FASHION, "San Francisco"),
            ("heritage", None, "Bangalore"),
            ("cocktails", CulturalDomain.NIGHTLIFE, None),
        ]

        async def _single_search(idx: int) -> List[CulturalEntity]:
            q, dom, hub = queries[idx % len(queries)]
            return await self.client.search_entities(query=q, domain=dom, hub=hub, limit=5)

        # Launch 100 concurrent tasks
        tasks = [_single_search(i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        self.assertEqual(len(results), 100)
        for res in results:
            self.assertIsInstance(res, list)
            for item in res:
                self.assertIsInstance(item, CulturalEntity)

    async def test_100_concurrent_cross_domain_affinities(self) -> None:
        """Execute 100 concurrent get_cross_domain_affinities calls across diverse seeds."""
        source_entities = list(ENTITIES_BY_ID.keys())[:10]
        target_domains = list(CulturalDomain)

        async def _single_affinity(idx: int) -> List[AffinityScore]:
            source_id = source_entities[idx % len(source_entities)]
            target_domain = target_domains[idx % len(target_domains)]
            return await self.client.get_cross_domain_affinities(
                entity_id=source_id,
                target_domain=target_domain,
                limit=4,
            )

        # Launch 100 concurrent tasks
        tasks = [_single_affinity(i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        self.assertEqual(len(results), 100)
        for res in results:
            self.assertIsInstance(res, list)
            for aff in res:
                self.assertIsInstance(aff, AffinityScore)
                self.assertGreaterEqual(aff.score, 0.0)
                self.assertLessEqual(aff.score, 1.0)
                self.assertGreaterEqual(aff.confidence, 0.0)
                self.assertLessEqual(aff.confidence, 1.0)
                self.assertTrue(len(aff.rationale) > 0)

    async def test_100_concurrent_mixed_operations(self) -> None:
        """Execute 100 concurrent interleaved operations (search, affinity, get_entity, get_hub)."""
        all_ids = list(ENTITIES_BY_ID.keys())
        hubs = sorted(list(SUPPORTED_HUBS))

        async def _dispatch_op(idx: int) -> Any:
            op_type = idx % 4
            if op_type == 0:
                return await self.client.search_entities(query="art", limit=3)
            elif op_type == 1:
                return await self.client.get_cross_domain_affinities(
                    entity_id=all_ids[idx % len(all_ids)],
                    target_domain=CulturalDomain.DINING,
                    limit=3,
                )
            elif op_type == 2:
                return await self.client.get_entity(all_ids[idx % len(all_ids)])
            else:
                return await self.client.get_hub_entities(hub=hubs[idx % len(hubs)])

        tasks = [_dispatch_op(i) for i in range(100)]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        self.assertEqual(len(results), 100)
        for idx, res in enumerate(results):
            op_type = idx % 4
            if op_type == 2:
                self.assertIsInstance(res, CulturalEntity)
            else:
                self.assertIsInstance(res, list)

    async def test_50_concurrent_simulated_network_failures_fallback_safely(self) -> None:
        """Stress test 50 concurrent calls under live gateway network timeout simulation."""
        live_client = QlooClient(api_key="mock_test_key", use_mock_fallback=True)

        with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectTimeout("Network unreachable")):
            async def _failing_call(idx: int) -> List[CulturalEntity]:
                return await live_client.search_entities(query="coffee", limit=2)

            tasks = [_failing_call(i) for i in range(50)]
            results = await asyncio.gather(*tasks, return_exceptions=False)

            self.assertEqual(len(results), 50)
            for res in results:
                self.assertIsInstance(res, list)
                self.assertGreater(len(res), 0)

        await live_client.close()


class TestQlooExtremeInputs(unittest.IsolatedAsyncioTestCase):
    """
    Adversarial testing with extreme, pathological, and injection inputs:
    - Multi-lingual Unicode (Japanese, Devanagari, Umlauts, Accents)
    - Emojis, math symbols, null bytes
    - SQL injection strings
    - XSS / script payload strings
    - Empty, whitespace, newline queries
    - Massive query strings (10k, 50k chars)
    - Boundary limits (0, -1, 1, 1000, 100000)
    """

    async def asyncSetUp(self) -> None:
        self.client = QlooClient(use_mock_fallback=True)

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_unicode_and_multilingual_queries(self) -> None:
        """Client must handle non-Latin and accented queries safely without crashing."""
        unicode_queries = [
            "東京",               # Tokyo in Kanji
            "すし",               # Sushi in Hiragana
            "बेंगलुरु",           # Bengaluru in Devanagari
            "Bücher",             # German umlaut
            "café",               # French accent
            "haute couture",      # French fashion
            "Москва",             # Cyrillic
            "الموسيقى",           # Arabic
        ]
        for q in unicode_queries:
            with self.subTest(query=q):
                results = await self.client.search_entities(query=q, limit=5)
                self.assertIsInstance(results, list)
                # Results may be empty if no token matches, but must never raise an unhandled exception

    async def test_emojis_and_symbols(self) -> None:
        """Client must handle emojis, mathematical operators, and punctuation safely."""
        symbolic_queries = [
            "☕ 🎵 🎨 🍜",
            "🔥✨💯",
            "∑∏∆∇∂∫",
            "&& || == != <= >=",
            "!@#$%^&*()_+=-`~[]\\;',./{}|:\"<>?",
            "\x00\x01\x02",
        ]
        for q in symbolic_queries:
            with self.subTest(query=q):
                results = await self.client.search_entities(query=q, limit=5)
                self.assertIsInstance(results, list)

    async def test_sql_injection_payloads_do_not_crash(self) -> None:
        """Adversarial SQL injection strings must be treated as inert search text."""
        sqli_payloads = [
            "SELECT * FROM entities; --",
            "' OR '1'='1",
            "'; DROP TABLE entities; --",
            "UNION SELECT null, username, password FROM users --",
            "1; EXEC xp_cmdshell('dir')",
            "\" OR \"\"=\"",
            "admin' --",
        ]
        for payload in sqli_payloads:
            with self.subTest(payload=payload):
                results = await self.client.search_entities(query=payload, limit=5)
                self.assertIsInstance(results, list)

    async def test_xss_and_html_injection_payloads(self) -> None:
        """Adversarial XSS and HTML payloads must be handled without error."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror=alert(1)>",
            "<svg/onload=alert('pwn')>",
            "javascript:void(0)",
            "{{ 7 * 7 }}",
            "${7*7}",
        ]
        for payload in xss_payloads:
            with self.subTest(payload=payload):
                results = await self.client.search_entities(query=payload, limit=5)
                self.assertIsInstance(results, list)

    async def test_empty_and_whitespace_only_queries(self) -> None:
        """Empty, whitespace, and control character queries must immediately return []."""
        empty_queries = [
            "",
            " ",
            "   ",
            "\t",
            "\n",
            "\r\n",
            "\t  \r\n \n  \t",
        ]
        for bad_q in empty_queries:
            with self.subTest(query=bad_q):
                results = await self.client.search_entities(query=bad_q)
                self.assertEqual(results, [])

    async def test_massive_query_string(self) -> None:
        """Excessively long query strings (10k, 50k chars) must not trigger ReDoS or OOM."""
        huge_query = "jazz " + ("a" * 10_000)
        results = await self.client.search_entities(query=huge_query, limit=5)
        self.assertIsInstance(results, list)

        gigantic_query = "a " * 25_000
        results2 = await self.client.search_entities(query=gigantic_query, limit=5)
        self.assertIsInstance(results2, list)

    async def test_boundary_limit_zero_raises_value_error(self) -> None:
        """limit=0 must be rejected with ValueError across all API endpoints."""
        with self.assertRaises(ValueError):
            await self.client.search_entities(query="jazz", limit=0)

        with self.assertRaises(ValueError):
            await self.client.get_cross_domain_affinities(
                entity_id="ent_blr_mus_001",
                target_domain=CulturalDomain.DINING,
                limit=0,
            )

    async def test_negative_limits_raise_value_error(self) -> None:
        """Negative limits (-1, -100) must be rejected with ValueError."""
        for bad_limit in [-1, -5, -100]:
            with self.subTest(limit=bad_limit):
                with self.assertRaises(ValueError):
                    await self.client.search_entities(query="jazz", limit=bad_limit)
                with self.assertRaises(ValueError):
                    await self.client.get_cross_domain_affinities(
                        entity_id="ent_blr_mus_001",
                        target_domain=CulturalDomain.DINING,
                        limit=bad_limit,
                    )

    async def test_boundary_limit_one(self) -> None:
        """limit=1 must return at most 1 entity/affinity."""
        res_search = await self.client.search_entities(query="coffee", limit=1)
        self.assertLessEqual(len(res_search), 1)

        res_aff = await self.client.get_cross_domain_affinities(
            entity_id="ent_blr_mus_001",
            target_domain=CulturalDomain.DINING,
            limit=1,
        )
        self.assertLessEqual(len(res_aff), 1)

    async def test_extreme_high_limits_do_not_crash(self) -> None:
        """limit=1000 and limit=100_000 must safely return all available entities."""
        for high_limit in [1000, 100_000]:
            with self.subTest(limit=high_limit):
                res = await self.client.search_entities(query="heritage", limit=high_limit)
                self.assertIsInstance(res, list)
                self.assertGreater(len(res), 0)
                self.assertLessEqual(len(res), len(MOCK_ENTITIES))

                affs = await self.client.get_cross_domain_affinities(
                    entity_id="ent_blr_mus_001",
                    target_domain=CulturalDomain.DINING,
                    limit=high_limit,
                )
                self.assertIsInstance(affs, list)
                self.assertGreater(len(affs), 0)


class TestQlooInvalidDomainsAndHubs(unittest.IsolatedAsyncioTestCase):
    """
    Adversarial testing of invalid, nonsensical, and unmapped domain/hub parameters.
    Verifies graceful handling via specific domain exceptions, without unhandled crashes.
    """

    async def asyncSetUp(self) -> None:
        self.client = QlooClient(use_mock_fallback=True)

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_search_entities_with_invalid_domain_raises(self) -> None:
        """search_entities with invalid domain string must raise QlooInvalidDomainError."""
        bad_domains = [
            "quantum_physics",
            "sports",
            "cryptocurrency",
            "12345",
            "astronomy",
        ]
        for bd in bad_domains:
            with self.subTest(domain=bd):
                with self.assertRaises(QlooInvalidDomainError):
                    await self.client.search_entities(query="test", domain=bd)

    async def test_search_entities_with_invalid_hub_graceful(self) -> None:
        """search_entities with invalid hub string returns [] or filters gracefully without crash."""
        bad_hubs = [
            "Atlantis",
            "Gotham",
            "Mars_Colony",
            "NonExistentCity123",
            "   ",
        ]
        for bh in bad_hubs:
            with self.subTest(hub=bh):
                # Must not raise an unhandled exception
                results = await self.client.search_entities(query="coffee", hub=bh)
                self.assertIsInstance(results, list)

    async def test_get_cross_domain_affinities_with_invalid_target_domain(self) -> None:
        """get_cross_domain_affinities with unrecognized domain must raise QlooInvalidDomainError."""
        bad_domains = ["astrology", "automotive", "gaming", ""]
        for bd in bad_domains:
            with self.subTest(domain=bd):
                with self.assertRaises(QlooInvalidDomainError):
                    await self.client.get_cross_domain_affinities(
                        entity_id="ent_blr_mus_001",
                        target_domain=bd,
                    )

    async def test_get_cross_domain_affinities_with_nonexistent_entity(self) -> None:
        """get_cross_domain_affinities with missing entity ID must raise QlooEntityNotFoundError."""
        bad_ids = [
            "ent_nonexistent_99999",
            "xyz_123_invalid",
            "",
            "   ",
            "DROP TABLE",
        ]
        for bid in bad_ids:
            with self.subTest(entity_id=bid):
                with self.assertRaises(QlooEntityNotFoundError):
                    await self.client.get_cross_domain_affinities(
                        entity_id=bid,
                        target_domain=CulturalDomain.DINING,
                    )

    async def test_get_hub_entities_with_unsupported_hub_raises(self) -> None:
        """get_hub_entities with an unsupported hub must raise QlooInvalidHubError."""
        bad_hubs = [
            "Atlantis",
            "Chicago",
            "Delhi",
            "Kolkata",
            "Sydney",
            "",
            "   ",
        ]
        for bh in bad_hubs:
            with self.subTest(hub=bh):
                with self.assertRaises(QlooInvalidHubError):
                    await self.client.get_hub_entities(hub=bh)

    async def test_get_hub_entities_with_invalid_domain_raises(self) -> None:
        """get_hub_entities with an invalid domain must raise QlooInvalidDomainError."""
        with self.assertRaises(QlooInvalidDomainError):
            await self.client.get_hub_entities(hub="Bangalore", domain="invalid_domain_xyz")

    async def test_get_entity_with_missing_or_invalid_id_returns_none(self) -> None:
        """get_entity with non-existent or blank entity_id must return None cleanly."""
        missing_ids = [
            "ent_missing_123",
            "",
            "   ",
            "\n\t",
            "unknown_id",
        ]
        for mid in missing_ids:
            with self.subTest(entity_id=mid):
                res = await self.client.get_entity(mid)
                self.assertIsNone(res)


class TestQlooLatencyBenchmark(unittest.IsolatedAsyncioTestCase):
    """
    Latency benchmark: Evaluates health_check() across 1000 consecutive runs,
    measuring exact execution time and asserting mean latency < 1.0ms (<5ms SLA).
    """

    async def asyncSetUp(self) -> None:
        self.client = QlooClient(use_mock_fallback=True)

    async def asyncTearDown(self) -> None:
        await self.client.close()

    async def test_health_check_1000_runs_latency_sla(self) -> None:
        """Execute 1,000 health_check() runs and verify latency SLA < 1.0ms (<5.0ms hard SLA)."""
        num_runs = 1000
        latencies_ms: List[float] = []

        # Warm up (5 runs)
        for _ in range(5):
            await self.client.health_check()

        # Benchmark 1000 runs
        for _ in range(num_runs):
            t0 = time.perf_counter()
            res = await self.client.health_check()
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

            # Structure validation on each call
            self.assertEqual(res["status"], "healthy")
            self.assertEqual(res["mode"], "offline_mock")
            self.assertEqual(res["entities_count"], 82)
            self.assertEqual(res["hubs_count"], 8)
            self.assertEqual(len(res["hubs_available"]), 8)

        latencies_sorted = sorted(latencies_ms)
        mean_latency = sum(latencies_ms) / len(latencies_ms)
        median_latency = latencies_sorted[num_runs // 2]
        p95_latency = latencies_sorted[int(num_runs * 0.95)]
        p99_latency = latencies_sorted[int(num_runs * 0.99)]
        max_latency = max(latencies_ms)
        min_latency = min(latencies_ms)

        print(
            f"\n[LATENCY BENCHMARK — 1000 RUNS]\n"
            f"  Mean Latency:   {mean_latency:.4f} ms\n"
            f"  Median Latency: {median_latency:.4f} ms\n"
            f"  Min Latency:    {min_latency:.4f} ms\n"
            f"  P95 Latency:    {p95_latency:.4f} ms\n"
            f"  P99 Latency:    {p99_latency:.4f} ms\n"
            f"  Max Latency:    {max_latency:.4f} ms\n"
        )

        # Assertions
        self.assertLess(
            mean_latency,
            1.0,
            f"Health check mean latency ({mean_latency:.4f} ms) exceeded 1.0 ms requirement!",
        )
        self.assertLess(
            max_latency,
            5.0,
            f"Health check max latency ({max_latency:.4f} ms) exceeded 5.0 ms hard SLA!",
        )


class TestQlooCatalogIntegrityAndDeterminism(unittest.IsolatedAsyncioTestCase):
    """
    Evaluates catalog immutability, data validity, and affinity determinism.
    """

    async def asyncSetUp(self) -> None:
        self.client = QlooClient(use_mock_fallback=True)

    async def asyncTearDown(self) -> None:
        await self.client.close()

    def test_catalog_structure_and_entity_validity(self) -> None:
        """Verify all 82 catalog entities have valid, non-null properties."""
        self.assertEqual(len(MOCK_ENTITIES), 82)
        self.assertEqual(len(SUPPORTED_HUBS), 8)
        self.assertEqual(len(ENTITIES_BY_ID), 82)

        for ent in MOCK_ENTITIES:
            self.assertTrue(ent.id.startswith("ent_"))
            self.assertTrue(len(ent.name) > 0)
            self.assertIn(ent.domain, CulturalDomain)
            self.assertIn(ent.hub, SUPPORTED_HUBS)
            self.assertGreaterEqual(ent.latitude, -90.0)
            self.assertLessEqual(ent.latitude, 90.0)
            self.assertGreaterEqual(ent.longitude, -180.0)
            self.assertLessEqual(ent.longitude, 180.0)
            self.assertIn(ent.price_tier, [1, 2, 3, 4])
            self.assertGreater(len(ent.vibe_tags), 0)
            self.assertGreater(len(ent.description), 0)

    def test_curated_affinities_bounded_and_consistent(self) -> None:
        """Verify all 25 curated pairings have valid scores, confidences, and rationales."""
        self.assertEqual(len(CURATED_AFFINITIES), 25)
        for (src_id, tgt_id), data in CURATED_AFFINITIES.items():
            self.assertIn(src_id, ENTITIES_BY_ID, f"Curated source {src_id} missing from catalog")
            self.assertIn(tgt_id, ENTITIES_BY_ID, f"Curated target {tgt_id} missing from catalog")
            self.assertGreaterEqual(data["score"], 0.0)
            self.assertLessEqual(data["score"], 1.0)
            self.assertGreaterEqual(data["confidence"], 0.0)
            self.assertLessEqual(data["confidence"], 1.0)
            self.assertTrue(len(data["rationale"]) > 0)

    async def test_determinism_across_repeated_affinity_evaluations(self) -> None:
        """Calling get_cross_domain_affinities 5 times on the same pair yields identical output."""
        src_id = "ent_blr_mus_001"
        target_domain = CulturalDomain.DINING

        runs = [
            await self.client.get_cross_domain_affinities(
                entity_id=src_id,
                target_domain=target_domain,
                limit=5,
            )
            for _ in range(5)
        ]

        first_run = runs[0]
        for run_idx, run in enumerate(runs[1:], start=2):
            self.assertEqual(len(run), len(first_run))
            for i in range(len(first_run)):
                self.assertEqual(
                    run[i].target_entity.id,
                    first_run[i].target_entity.id,
                    f"Mismatch in target entity ID at run {run_idx}, index {i}",
                )
                self.assertEqual(
                    run[i].score,
                    first_run[i].score,
                    f"Mismatch in score at run {run_idx}, index {i}",
                )
                self.assertEqual(
                    run[i].confidence,
                    first_run[i].confidence,
                    f"Mismatch in confidence at run {run_idx}, index {i}",
                )
                self.assertEqual(
                    run[i].rationale,
                    first_run[i].rationale,
                    f"Mismatch in rationale at run {run_idx}, index {i}",
                )


if __name__ == "__main__":
    unittest.main()
