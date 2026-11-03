"""
CULTURA Acceptance Test Suite: Milestone 5 Final Verification & E2E Hardening.

Authoritative Acceptance Tests asserting on all 5 deliverables & criteria:
- R1: Qloo API Client & Offline Mock Data
  * 8 Cultural Hubs (BLR, BOM, NYC, LDN, TYO, PAR, BER, SFO) and aliases
  * 7 Cultural Domains (dining, music, arts, cinema, nightlife, literary, fashion)
  * 82 Authentic venues with full metadata integrity
  * Offline mode deterministic affinities and health checks
- R2: Pydantic Schemas & Autonomous ReAct Planner
  * Pydantic V2 model validations & boundary enforcement
  * 48-Hour 8-slot schedule invariant & zero-duplicate rule
  * 5-State ReAct transitions (Thought -> Action -> Observation -> Reflection -> Synthesis)
  * Spatio-temporal transit constraints (<= 45 min transit legs)
  * Shannon domain diversity (>= 4 unique cultural domains, anti-clumping)
- R3: Dual Interface (Terminal CLI & Streamlit Web App)
  * Typer CLI `cultura doctor` with strict <100ms wall-clock SLA benchmark
  * Typer CLI `cultura hubs`, `cultura search`, and `cultura plan` (ASCII timeline & tables)
  * Streamlit web app headless import guard & PyDeck 3D map generation
- R4: Multi-Format Exporters & Submission Packaging Kit
  * .ics RFC 5545 CRLF line endings & calendar event structure
  * .md GitHub Flavored Markdown travel guide formatting
  * .geojson RFC 7946 FeatureCollection (Point & LineString geometries)
  * .json schema roundtrip fidelity
  * Packaging files: LICENSE (Copyright 2026 R Jan Steve Daniel), pyproject.toml, requirements.txt, .env.example, README.md
- R5: Comprehensive End-to-End Suite Verification
  * Autonomous itinerary generation across all 8 cultural hubs
  * 100% automated test suite pass rate

Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import asyncio
import io
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import pytest
from rich.console import Console
from typer.testing import CliRunner

import cultura.cli.main
from cultura import __version__
from cultura.agent.planner import ReActPlanner, ReActState
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
from cultura.cli.main import app, doctor
from cultura.client.mock_data import (
    CULTURAL_DOMAINS,
    CULTURAL_HUBS,
    ENTITIES_BY_HUB,
    ENTITIES_BY_ID,
    HUB_ALIASES,
    HUB_METADATA,
    MOCK_ENTITIES,
    SUPPORTED_HUBS,
    calculate_affinity,
    normalize_domain,
    normalize_hub,
)
from cultura.client.qloo import QlooClient, QlooEntityNotFoundError, QlooInvalidDomainError
from cultura.export.exporters import (
    export_geojson,
    export_ics,
    export_itinerary,
    export_json,
    export_markdown,
)

REPO_ROOT = Path(__file__).resolve().parent.parent

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore


# ============================================================================
# R1: Qloo Client & Offline Mock Data Acceptance Suite
# ============================================================================

class TestAcceptanceR1QlooClientAndMockData:
    """Acceptance tests for Deliverable R1: Qloo Client & Offline Mock Catalog."""

    def test_r1_eight_cultural_hubs_and_aliases(self) -> None:
        """Asserts all 8 cultural hubs and their airport/standard aliases are supported."""
        canonical_hubs = {
            "Bangalore",
            "Mumbai",
            "New York",
            "London",
            "Tokyo",
            "Paris",
            "Berlin",
            "San Francisco",
        }
        assert set(SUPPORTED_HUBS) == canonical_hubs
        assert set(CULTURAL_HUBS) == canonical_hubs
        assert set(HUB_METADATA.keys()) == canonical_hubs

        # Verify hub metadata contains valid coordinates, timezone, country, and description
        for hub_name in canonical_hubs:
            meta = HUB_METADATA[hub_name]
            assert "latitude" in meta and -90.0 <= meta["latitude"] <= 90.0
            assert "longitude" in meta and -180.0 <= meta["longitude"] <= 180.0
            assert "timezone" in meta and len(meta["timezone"]) > 0
            assert "country" in meta and len(meta["country"]) > 0
            assert "description" in meta and len(meta["description"]) > 20

        # Verify standard short airport codes & aliases
        expected_aliases = {
            "blr": "Bangalore",
            "bom": "Mumbai",
            "nyc": "New York",
            "ldn": "London",
            "tyo": "Tokyo",
            "par": "Paris",
            "ber": "Berlin",
            "sfo": "San Francisco",
        }
        for code, expected_name in expected_aliases.items():
            resolved = normalize_hub(code)
            assert resolved == expected_name, f"Alias '{code}' resolved to '{resolved}', expected '{expected_name}'"
            assert normalize_hub(code.upper()) == expected_name

    def test_r1_seven_cultural_domains(self) -> None:
        """Asserts all 7 cultural domains are recognized and represented."""
        expected_domains = {
            "dining",
            "music",
            "arts",
            "cinema",
            "nightlife",
            "literary",
            "fashion",
        }
        domain_values = {d.value for d in CulturalDomain}
        assert domain_values == expected_domains
        assert set(CULTURAL_DOMAINS) == expected_domains

        # Verify domain normalization and aliases
        assert normalize_domain("food") == CulturalDomain.DINING
        assert normalize_domain("concert") == CulturalDomain.MUSIC
        assert normalize_domain("gallery") == CulturalDomain.ARTS
        assert normalize_domain("film") == CulturalDomain.CINEMA
        assert normalize_domain("club") == CulturalDomain.NIGHTLIFE
        assert normalize_domain("books") == CulturalDomain.LITERARY
        assert normalize_domain("apparel") == CulturalDomain.FASHION

    def test_r1_eighty_two_authentic_venues_integrity(self) -> None:
        """Asserts mock catalog contains exactly 82 authentic venues with valid metadata."""
        assert len(MOCK_ENTITIES) == 82
        assert len(ENTITIES_BY_ID) == 82

        entity_ids = set()
        hubs_represented = set()
        domains_represented = set()

        for entity in MOCK_ENTITIES:
            # ID uniqueness
            assert entity.id not in entity_ids, f"Duplicate entity ID detected: {entity.id}"
            entity_ids.add(entity.id)

            # Name and address (if present)
            assert len(entity.name.strip()) > 0, f"Entity {entity.id} has empty name"
            if entity.address:
                assert len(entity.address.strip()) > 0

            # Domain & hub coverage
            assert isinstance(entity.domain, CulturalDomain)
            domains_represented.add(entity.domain.value)
            assert entity.hub in SUPPORTED_HUBS
            hubs_represented.add(entity.hub)

            # Coordinates
            assert -90.0 <= entity.latitude <= 90.0
            assert -180.0 <= entity.longitude <= 180.0
            assert -90.0 <= entity.coordinates.latitude <= 90.0
            assert -180.0 <= entity.coordinates.longitude <= 180.0

            # Price tier and tags
            assert 1 <= entity.price_tier <= 4
            assert len(entity.tags) >= 1

        assert len(hubs_represented) == 8
        assert len(domains_represented) == 7

        # Verify each hub has sufficient entities across domains (at least 10 per hub)
        for hub_name in SUPPORTED_HUBS:
            hub_entities = ENTITIES_BY_HUB.get(hub_name, [])
            assert len(hub_entities) >= 10, f"Hub '{hub_name}' has insufficient entities: {len(hub_entities)}"

    def test_r1_offline_mode_deterministic_affinities(self) -> None:
        """Asserts offline mock client calculates deterministic affinities with zero API dependency."""
        async def _test() -> None:
            client = QlooClient(api_key=None, use_mock_fallback=True)
            assert client.is_offline is True

            # Diagnostic health check
            health = await client.health_check()
            assert health["status"] == "healthy"
            assert health["mode"] == "offline_mock"
            assert health["entities_count"] == 82
            assert health["hubs_count"] == 8
            assert health["latency_ms"] < 20.0

            # Entity search determinism
            results1 = await client.search_entities(query="Jazz", hub="Tokyo")
            results2 = await client.search_entities(query="Jazz", hub="Tokyo")
            assert len(results1) > 0
            assert [e.id for e in results1] == [e.id for e in results2]

            # Cross-domain affinities determinism
            source_id = "ent_tyo_din_001"  # Sukiyabashi Jiro
            affinities1 = await client.get_cross_domain_affinities(
                entity_id=source_id,
                target_domain=CulturalDomain.MUSIC,
                hub="Tokyo",
                limit=3,
            )
            affinities2 = await client.get_cross_domain_affinities(
                entity_id=source_id,
                target_domain=CulturalDomain.MUSIC,
                hub="Tokyo",
                limit=3,
            )
            assert len(affinities1) > 0
            assert len(affinities1) == len(affinities2)
            for a1, a2 in zip(affinities1, affinities2):
                assert a1.target_entity.id == a2.target_entity.id
                assert a1.score == a2.score
                assert a1.confidence == a2.confidence
                assert a1.rationale == a2.rationale

            await client.close()

        asyncio.run(_test())


# ============================================================================
# R2: Pydantic Schemas & ReAct Planner Acceptance Suite
# ============================================================================

class TestAcceptanceR2SchemasAndReActPlanner:
    """Acceptance tests for Deliverable R2: Schemas & Autonomous ReAct Planner."""

    def test_r2_pydantic_schema_validation(self) -> None:
        """Validates all 5 Pydantic models with valid inputs and boundary rejections."""
        # TasteSeed
        seed = TasteSeed(name="Berghain", domain=CulturalDomain.NIGHTLIFE, weight=1.5)
        assert seed.name == "Berghain"
        assert seed.domain == CulturalDomain.NIGHTLIFE
        assert seed.weight == 1.5

        with pytest.raises(Exception):
            TasteSeed(name="", domain=CulturalDomain.DINING)  # blank name rejected
        with pytest.raises(Exception):
            TasteSeed(name="Test", domain="invalid_domain")  # invalid domain

        # CulturalEntity
        entity = CulturalEntity(
            id="ent_test_001",
            name="Test Venue",
            domain=CulturalDomain.ARTS,
            hub="Berlin",
            latitude=52.52,
            longitude=13.40,
            address="Berlin, Germany",
            tags=["modernist", "minimalist"],
            price_tier=2,
        )
        assert entity.coordinates.latitude == 52.52
        assert entity.coordinates.longitude == 13.40

        # AffinityScore
        aff = AffinityScore(
            entity_id="ent_test_001",
            target_entity=entity,
            score=0.92,
            confidence=0.88,
            rationale="Shared brutalist aesthetic.",
        )
        assert aff.score == 0.92
        assert aff.target_domain == CulturalDomain.ARTS

        with pytest.raises(Exception):
            AffinityScore(
                entity_id="ent_test_001",
                target_entity=entity,
                score=1.5,  # out of [0, 1] bounds
                rationale="Invalid",
            )

    def test_r2_forty_eight_hour_eight_slot_schedule_invariant(self) -> None:
        """Enforces the 48-Hour 8-Slot Schedule Invariant (exactly 8 items, 0 duplicate venues)."""
        # Build 8 distinct items across 8 distinct mock venues
        distinct_entities = MOCK_ENTITIES[:8]
        assert len(distinct_entities) == 8

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

        valid_items = [
            ItineraryItem(
                day=day,
                slot=slot,
                entity=distinct_entities[idx],
                affinity_score=0.85,
                curator_notes=f"Scheduled slot {slot.value}",
                transit_from_previous_min=0 if idx == 0 else 15,
            )
            for idx, (day, slot) in enumerate(slots_sequence)
        ]

        # Valid plan passes
        valid_plan = ItineraryPlan(
            city_hub="London",
            taste_seeds=[TasteSeed(name="Tate Modern", domain=CulturalDomain.ARTS)],
            items=valid_items,
            cultural_coherence_score=0.91,
            domain_diversity_score=0.88,
            transit_efficiency_score=0.85,
        )
        assert len(valid_plan.items) == 8

        # Invariant rejection: exactly 8 items (reject 7 or 9)
        with pytest.raises(Exception):
            ItineraryPlan(
                city_hub="London",
                taste_seeds=[TasteSeed(name="Tate Modern", domain=CulturalDomain.ARTS)],
                items=valid_items[:7],  # only 7 items
            )

        with pytest.raises(Exception):
            ItineraryPlan(
                city_hub="London",
                taste_seeds=[TasteSeed(name="Tate Modern", domain=CulturalDomain.ARTS)],
                items=valid_items + [valid_items[0]],  # 9 items
            )

        # Invariant rejection: zero duplicate venues
        duplicate_items = list(valid_items)
        duplicate_items[7] = ItineraryItem(
            day=2,
            slot=TimeSlot.NIGHT,
            entity=distinct_entities[0],  # Duplicate of item 0
            affinity_score=0.80,
            curator_notes="Duplicate venue",
        )
        with pytest.raises(Exception):
            ItineraryPlan(
                city_hub="London",
                taste_seeds=[TasteSeed(name="Tate Modern", domain=CulturalDomain.ARTS)],
                items=duplicate_items,
            )

    def test_r2_react_five_state_transitions(self) -> None:
        """Asserts the ReAct planning loop executes complete 5-state transitions."""
        async def _test() -> None:
            client = QlooClient(use_mock_fallback=True)
            planner = ReActPlanner(client=client)

            plan = await planner.plan_48h(
                city_hub="Tokyo",
                taste_seeds=[
                    TasteSeed(name="Sukiyabashi Jiro", domain=CulturalDomain.DINING),
                    TasteSeed(name="Blue Note Tokyo", domain=CulturalDomain.MUSIC),
                ],
            )

            assert plan.react_steps_count >= 8
            assert "react_trace" in plan.metadata
            trace = plan.metadata["react_trace"]
            assert isinstance(trace, list)
            assert len(trace) >= 8

            # Extract states observed in execution trace
            observed_states = {step.get("state") for step in trace if "state" in step}
            expected_5_states = {
                ReActState.THOUGHT.value,
                ReActState.ACTION.value,
                ReActState.OBSERVATION.value,
                ReActState.REFLECTION.value,
                ReActState.SYNTHESIS.value,
            }
            assert expected_5_states.issubset(observed_states), (
                f"Missing ReAct state transitions: {expected_5_states - observed_states}"
            )

            await client.close()

        asyncio.run(_test())

    def test_r2_spatio_temporal_transit_invariant(self) -> None:
        """Asserts inter-venue transit times are <= 45 minutes and spatial efficiency is maintained."""
        async def _test() -> None:
            client = QlooClient(use_mock_fallback=True)
            planner = ReActPlanner(client=client)

            plan = await planner.plan_48h(
                city_hub="Paris",
                taste_seeds=[
                    TasteSeed(name="Le Gabriel", domain=CulturalDomain.DINING),
                    TasteSeed(name="Centre Pompidou", domain=CulturalDomain.ARTS),
                ],
            )

            for idx, item in enumerate(plan.items):
                if idx == 0:
                    assert item.transit_from_previous_min == 0, "Initial slot should have 0 transit"
                else:
                    assert item.transit_from_previous_min <= 45, (
                        f"Slot {item.day}-{item.slot.value} transit ({item.transit_from_previous_min}m) > 45m"
                    )
                    assert item.transit_from_previous_min >= 0

            assert plan.transit_efficiency_score >= 0.70
            await client.close()

        asyncio.run(_test())

    def test_r2_shannon_domain_diversity_invariant(self) -> None:
        """Asserts plan spans at least 4 distinct cultural domains with anti-clumping."""
        async def _test() -> None:
            client = QlooClient(use_mock_fallback=True)
            planner = ReActPlanner(client=client)

            plan = await planner.plan_48h(
                city_hub="Berlin",
                taste_seeds=[
                    TasteSeed(name="Berghain", domain=CulturalDomain.NIGHTLIFE),
                    TasteSeed(name="Boros Collection", domain=CulturalDomain.ARTS),
                ],
            )

            unique_domains = {item.entity.domain for item in plan.items}
            assert len(unique_domains) >= 4, (
                f"Expected at least 4 domains in 48-hour plan, got {len(unique_domains)}: {unique_domains}"
            )

            # Anti-clumping: no two adjacent slots have identical domain
            for i in range(len(plan.items) - 1):
                assert plan.items[i].entity.domain != plan.items[i + 1].entity.domain, (
                    f"Adjacent slots {i} and {i+1} have identical domain '{plan.items[i].entity.domain.value}'"
                )

            assert plan.domain_diversity_score >= 0.70
            await client.close()

        asyncio.run(_test())


# ============================================================================
# R3: Dual Interface Acceptance Suite (CLI & Web Dashboard)
# ============================================================================

class TestAcceptanceR3DualInterface:
    """Acceptance tests for Deliverable R3: Terminal CLI & Streamlit Dashboard."""

    @pytest.fixture
    def runner(self) -> CliRunner:
        return CliRunner()

    def test_r3_typer_cli_doctor_sla_under_100ms(self, runner: CliRunner) -> None:
        """Asserts `cultura doctor` executes under 100ms wall-clock SLA benchmark."""
        # Functional check
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "System & Taste Graph Diagnostics" in result.output
        assert "Compatible" in result.output
        assert "Verified" in result.output
        assert "ALL 4 CHECKS OPERATIONAL" in result.output

        # Benchmark 10 direct doctor() calls with muted console to eliminate terminal I/O skew
        saved_console = cultura.cli.main.console
        cultura.cli.main.console = Console(file=io.StringIO(), force_terminal=False)
        latencies: List[float] = []
        try:
            for _ in range(10):
                t0 = time.perf_counter()
                doctor()
                dt_ms = (time.perf_counter() - t0) * 1000.0
                latencies.append(dt_ms)
        finally:
            cultura.cli.main.console = saved_console

        max_lat = max(latencies)
        mean_lat = sum(latencies) / len(latencies)
        assert max_lat < 100.0, f"Doctor SLA exceeded: max latency was {max_lat:.2f}ms (threshold 100ms)"
        assert mean_lat < 30.0, f"Doctor mean latency too high: {mean_lat:.2f}ms"

    def test_r3_typer_cli_hubs_command(self, runner: CliRunner) -> None:
        """Asserts `cultura hubs` lists all 8 cultural hubs with venue counts."""
        result = runner.invoke(app, ["hubs"])
        assert result.exit_code == 0
        for hub in ["Bangalore", "Mumbai", "New York", "London", "Tokyo", "Paris", "Berlin", "San Francisco"]:
            assert hub in result.output

    def test_r3_typer_cli_search_command(self, runner: CliRunner) -> None:
        """Asserts `cultura search` queries mock entities accurately."""
        result = runner.invoke(app, ["search", "Jazz", "--domain", "music"])
        assert result.exit_code == 0
        assert "Jazz" in result.output or "Blue Note" in result.output or "MUSIC" in result.output

    def test_r3_typer_cli_plan_command_ascii_timeline_and_table(self, runner: CliRunner) -> None:
        """Asserts `cultura plan` outputs ASCII timeline tree and affinity score table."""
        result = runner.invoke(
            app,
            ["plan", "--hub", "Bangalore", "-s", "Coffee:dining"],
        )
        assert result.exit_code == 0
        # Timeline tree checks
        assert "Day 1" in result.output
        assert "Day 2" in result.output
        assert "Morning" in result.output
        assert "Afternoon" in result.output
        assert "Evening" in result.output
        assert "Night" in result.output
        # Score table checks
        assert "Cultural Coherence" in result.output
        assert "Domain Diversity" in result.output
        assert "Transit Efficiency" in result.output

    def test_r3_streamlit_app_headless_import_guard(self) -> None:
        """Asserts Streamlit web app can be imported headlessly without runtime errors."""
        import cultura.web.app as web_app
        assert hasattr(web_app, "main")
        assert hasattr(web_app, "build_pydeck_map")
        assert hasattr(web_app, "generate_plan")

        # Test map builder with an actual plan and hub metadata dictionary
        planner = ReActPlanner()
        plan = asyncio.run(
            planner.plan_48h(
                city_hub="New York",
                taste_seeds=[TasteSeed(name="Blue Note", domain=CulturalDomain.MUSIC)],
            )
        )
        deck = web_app.build_pydeck_map(plan, HUB_METADATA["New York"])
        assert deck is not None
        assert hasattr(deck, "layers")
        assert len(deck.layers) >= 2  # ScatterplotLayer + PathLayer


# ============================================================================
# R4: Multi-Format Exporters & Packaging Acceptance Suite
# ============================================================================

class TestAcceptanceR4ExportersAndPackaging:
    """Acceptance tests for Deliverable R4: Exporters & Packaging Kit."""

    @pytest.fixture
    def sample_plan(self) -> ItineraryPlan:
        planner = ReActPlanner()
        return asyncio.run(
            planner.plan_48h(
                city_hub="San Francisco",
                taste_seeds=[
                    TasteSeed(name="City Lights Books", domain=CulturalDomain.LITERARY),
                    TasteSeed(name="Tartine Bakery", domain=CulturalDomain.DINING),
                ],
            )
        )

    def test_r4_ics_exporter_rfc5545_crlf_conformance(self, sample_plan: ItineraryPlan) -> None:
        """Asserts .ics export strictly adheres to RFC 5545 with CRLF line endings."""
        ics_text = export_ics(sample_plan)
        assert "\r\n" in ics_text, "RFC 5545 strictly mandates CRLF (\\r\\n) line separators"
        assert "BEGIN:VCALENDAR\r\n" in ics_text
        assert "VERSION:2.0\r\n" in ics_text
        assert "PRODID:-//CULTURA//" in ics_text
        assert "END:VCALENDAR" in ics_text

        # Verify exactly 8 VEVENT blocks
        vevent_count = ics_text.count("BEGIN:VEVENT\r\n")
        assert vevent_count == 8, f"Expected 8 VEVENT blocks, found {vevent_count}"
        assert ics_text.count("END:VEVENT\r\n") == 8

        # Verify essential VEVENT fields
        for field in ["UID:", "DTSTART:", "DTEND:", "SUMMARY:", "DESCRIPTION:", "LOCATION:"]:
            assert field in ics_text, f"Missing standard iCalendar field '{field}'"

    def test_r4_markdown_exporter_gfm_conformance(self, sample_plan: ItineraryPlan) -> None:
        """Asserts .md export produces GitHub Flavored Markdown travel guide."""
        md_text = export_markdown(sample_plan)
        assert "# 📍 CULTURA 48-Hour Cultural Blueprint: San Francisco" in md_text
        assert "Day 1" in md_text
        assert "Day 2" in md_text
        assert "Morning" in md_text
        assert "Afternoon" in md_text
        assert "Evening" in md_text
        assert "Night" in md_text
        assert "Transit" in md_text
        assert "Affinity" in md_text

    def test_r4_geojson_exporter_rfc7946_conformance(self, sample_plan: ItineraryPlan) -> None:
        """Asserts .geojson export conforms to RFC 7946 FeatureCollection schema."""
        geojson_str = export_geojson(sample_plan)
        data = json.loads(geojson_str)
        assert data.get("type") == "FeatureCollection"
        features = data.get("features", [])
        assert len(features) >= 8

        # Check Point features
        point_features = [f for f in features if f["geometry"]["type"] == "Point"]
        assert len(point_features) == 8
        for pf in point_features:
            coords = pf["geometry"]["coordinates"]
            assert len(coords) == 2
            assert -180.0 <= coords[0] <= 180.0  # lon
            assert -90.0 <= coords[1] <= 90.0   # lat
            props = pf["properties"]
            assert "venue_name" in props or "name" in props
            assert "domain" in props
            assert "time_window" in props
            assert "affinity_score" in props

        # Check LineString route features
        route_features = [f for f in features if f["geometry"]["type"] == "LineString"]
        assert len(route_features) >= 1

    def test_r4_json_exporter_roundtrip(self, sample_plan: ItineraryPlan) -> None:
        """Asserts .json export preserves exact schema roundtrip fidelity."""
        json_str = export_json(sample_plan)
        data = json.loads(json_str)
        assert data["city_hub"] == "San Francisco"
        assert len(data["items"]) == 8

        # Model validation roundtrip
        reconstructed = ItineraryPlan.model_validate_json(json_str)
        assert reconstructed.city_hub == sample_plan.city_hub
        assert len(reconstructed.items) == 8
        assert [i.entity.id for i in reconstructed.items] == [i.entity.id for i in sample_plan.items]

    def test_r4_packaging_license_and_attribution(self) -> None:
        """Asserts Apache 2.0 LICENSE file exists with exact copyright attribution."""
        license_path = REPO_ROOT / "LICENSE"
        assert license_path.is_file(), f"Missing LICENSE at {license_path}"
        content = license_path.read_text(encoding="utf-8")
        assert "Apache License" in content
        assert "Version 2.0, January 2004" in content
        assert "Copyright 2026 R Jan Steve Daniel" in content

    def test_r4_packaging_pyproject_toml(self) -> None:
        """Asserts pyproject.toml PEP 518/621 packaging metadata and CLI entrypoint."""
        pyproj_path = REPO_ROOT / "pyproject.toml"
        assert pyproj_path.is_file(), f"Missing pyproject.toml at {pyproj_path}"
        content = pyproj_path.read_text(encoding="utf-8")
        assert 'name = "cultura"' in content
        assert 'version = "0.1.0"' in content
        assert "R Jan Steve Daniel" in content
        assert "cultura = \"cultura.cli.main:app\"" in content

    def test_r4_packaging_requirements_txt(self) -> None:
        """Asserts requirements.txt contains all core operational dependencies."""
        req_path = REPO_ROOT / "requirements.txt"
        assert req_path.is_file(), f"Missing requirements.txt at {req_path}"
        content = req_path.read_text(encoding="utf-8").lower()
        for pkg in ["pydantic", "typer", "rich", "httpx", "streamlit", "pydeck", "pytest"]:
            assert pkg in content, f"Dependency '{pkg}' missing from requirements.txt"

    def test_r4_packaging_env_example(self) -> None:
        """Asserts .env.example contains QLOO_API_KEY template."""
        env_path = REPO_ROOT / ".env.example"
        assert env_path.is_file(), f"Missing .env.example at {env_path}"
        assert "QLOO_API_KEY" in env_path.read_text(encoding="utf-8")

    def test_r4_packaging_readme_markdown(self) -> None:
        """Asserts README.md comprehensive architecture, CLI guide, and submission metadata."""
        readme_path = REPO_ROOT / "README.md"
        assert readme_path.is_file(), f"Missing README.md at {readme_path}"
        text = readme_path.read_text(encoding="utf-8")
        assert "# CULTURA: Autonomous Cultural Intelligence & Taste Graph Agent" in text
        assert "Architecture" in text
        assert "ReAct" in text
        assert "Bangalore" in text and "Tokyo" in text
        assert "cultura doctor" in text
        assert "cultura plan" in text
        assert "Copyright 2026 R Jan Steve Daniel" in text


# ============================================================================
# R5: Comprehensive End-to-End Suite Verification
# ============================================================================

class TestAcceptanceR5FullSuiteVerification:
    """Acceptance tests for Deliverable R5: 100% End-to-End Test Suite Verification."""

    @pytest.mark.parametrize(
        "hub_code,seed_name,seed_domain",
        [
            ("BLR", "Vidyarthi Bhavan", CulturalDomain.DINING),
            ("BOM", "Prithvi Theatre", CulturalDomain.ARTS),
            ("NYC", "Village Vanguard", CulturalDomain.MUSIC),
            ("LDN", "Tate Modern", CulturalDomain.ARTS),
            ("TYO", "Daikanyama T-Site", CulturalDomain.LITERARY),
            ("PAR", "Le Marais Boutiques", CulturalDomain.FASHION),
            ("BER", "Berghain", CulturalDomain.NIGHTLIFE),
            ("SFO", "Castro Theatre", CulturalDomain.CINEMA),
        ],
    )
    def test_r5_e2e_all_eight_hubs_generation(
        self,
        hub_code: str,
        seed_name: str,
        seed_domain: CulturalDomain,
    ) -> None:
        """Asserts genuine 48-hour itinerary synthesis succeeds across all 8 cultural hubs."""
        async def _test() -> None:
            client = QlooClient(use_mock_fallback=True)
            planner = ReActPlanner(client=client)

            canonical_hub = normalize_hub(hub_code)
            assert canonical_hub is not None

            plan = await planner.plan_48h(
                city_hub=canonical_hub,
                taste_seeds=[TasteSeed(name=seed_name, domain=seed_domain)],
            )

            # Invariant checks
            assert plan.city_hub == canonical_hub
            assert len(plan.items) == 8
            assert len(set(i.entity.id for i in plan.items)) == 8
            assert len({i.entity.domain for i in plan.items}) >= 4
            assert plan.cultural_coherence_score >= 0.70
            assert plan.domain_diversity_score >= 0.70
            assert plan.transit_efficiency_score >= 0.70

            # Exporter checks on generated plan
            ics = export_ics(plan)
            assert "BEGIN:VCALENDAR" in ics
            md = export_markdown(plan)
            assert f"Blueprint: {canonical_hub}" in md
            geo = json.loads(export_geojson(plan))
            assert geo["type"] == "FeatureCollection"
            js = json.loads(export_json(plan))
            assert js["city_hub"] == canonical_hub

            await client.close()

        asyncio.run(_test())

    def test_r5_automated_test_modules_present(self) -> None:
        """Asserts all required automated test suite modules exist and are discoverable."""
        test_dir = REPO_ROOT / "tests"
        required_modules = [
            "test_qloo_client.py",
            "test_agent_planner.py",
            "test_cli.py",
            "test_exporters.py",
            "test_packaging.py",
            "test_acceptance.py",
        ]
        for mod in required_modules:
            mod_path = test_dir / mod
            assert mod_path.is_file(), f"Required test suite module '{mod}' missing from {test_dir}"
