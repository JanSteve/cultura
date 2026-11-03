"""
CULTURA Empirical Adversarial Test Suite: Multi-Format Exporters & Streamlit UI Components.
Adversarially verifies:
1. RFC 5545 iCalendar (.ics) exporter: standard fields, UTC timestamps, chronological invariants, UID uniqueness, edge case sanitization.
2. RFC 7946 GeoJSON (.geojson) exporter: FeatureCollection conformance, 8 Point features in [lon, lat] order, 1 sequential LineString transit route.
3. Validated JSON (.json) exporter: round-trip Pydantic V2 deserialization and exact field-by-field equality across all 8 cultural hubs.
4. GitHub-flavored Markdown (.md) exporter: table syntax, 3-column delimiters, 8 slot cards, maps URLs, transit sums.
5. Export dispatcher: alias handling, multi-format batch generation, invalid format rejection.
6. Streamlit UI components: headless safety, PyDeck 3D map construction, AppTest lifecycle verification across all 8 hubs.

Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest

import pytest
from streamlit.testing.v1 import AppTest

from cultura.agent.planner import ReActPlanner
from cultura.agent.tools import (
    CulturalDomain,
    CulturalEntity,
    ItineraryItem,
    ItineraryPlan,
    TasteSeed,
    TimeSlot,
)
from cultura.client.mock_data import CULTURAL_HUBS, HUB_METADATA
from cultura.export.exporters import (
    export_geojson,
    export_ics,
    export_itinerary,
    export_json,
    export_markdown,
)
from cultura.web.app import build_pydeck_map, generate_plan


# ============================================================================
# Helpers & Custom Test Fixtures
# ============================================================================

def make_adversarial_plan(hub: str = "Tokyo") -> ItineraryPlan:
    """Creates a deterministic ItineraryPlan populated with hostile edge-case metadata."""
    slots = [
        (1, TimeSlot.MORNING),
        (1, TimeSlot.AFTERNOON),
        (1, TimeSlot.EVENING),
        (1, TimeSlot.NIGHT),
        (2, TimeSlot.MORNING),
        (2, TimeSlot.AFTERNOON),
        (2, TimeSlot.EVENING),
        (2, TimeSlot.NIGHT),
    ]

    domains = [
        CulturalDomain.DINING,
        CulturalDomain.ARTS,
        CulturalDomain.MUSIC,
        CulturalDomain.NIGHTLIFE,
        CulturalDomain.LITERARY,
        CulturalDomain.CINEMA,
        CulturalDomain.DINING,
        CulturalDomain.MUSIC,
    ]

    items = []
    for i, (day, slot) in enumerate(slots):
        ent = CulturalEntity(
            id=f"ent_adv_test_{i}",
            name=f"Venue \"Adversarial\" & Semicolon; {i} 🎨 東京 Café",
            domain=domains[i],
            hub=hub,
            latitude=35.6762 + i * 0.005,
            longitude=139.6503 + i * 0.005,
            vibe_tags=["tag|pipe", "tag*star", "tag[bracket]", "tag;semi", "vibes:chill"],
            price_tier=2,
            description="Desc with \n newlines and ; semicolons and \"quotes\"",
            address="123 Main St, Shibuya-ku, Tokyo, 150-0002; Japan",
            curator_note="Special tip; with \n multiple \n lines & | pipes",
        )
        items.append(
            ItineraryItem(
                day=day,
                slot=slot,
                time_window=slot.default_time_window,
                entity=ent,
                affinity_score=0.95 if i % 2 == 0 else 0.70,
                curator_notes="Notes with \n newline; semicolon, and \"quotes\" | pipe",
                transit_from_previous_min=20 if i > 0 else 0,
            )
        )

    seeds = [
        TasteSeed(name="Taste with | pipes, *stars*, and [brackets]", domain=CulturalDomain.MUSIC, weight=1.5),
        TasteSeed(name="Another; seed with \"quotes\"", domain=CulturalDomain.DINING, weight=0.5),
    ]

    return ItineraryPlan(
        city_hub=hub,
        taste_seeds=seeds,
        items=items,
        cultural_coherence_score=0.88,
        domain_diversity_score=0.92,
        transit_efficiency_score=0.85,
        summary="Summary with *markdown* and | pipes and \n newlines",
        metadata={"test_key": "adversarial_val", "react_trace": []},
    )


# ============================================================================
# Suite 1: RFC 5545 iCalendar Exporter Adversarial Verification
# ============================================================================

class TestIcsExporterAdversarial(unittest.IsolatedAsyncioTestCase):
    """Stress tests the RFC 5545 iCalendar exporter (.ics)."""

    async def asyncSetUp(self):
        self.planner = ReActPlanner()

    async def test_ics_standard_rfc5545_fields_all_eight_hubs(self):
        """Asserts RFC 5545 standard fields and parseable timestamps across all 8 hubs."""
        for hub in CULTURAL_HUBS:
            with self.subTest(hub=hub):
                plan = await self.planner.plan_48h(
                    city_hub=hub,
                    taste_seeds=[TasteSeed(name=f"{hub} Anchor", domain=CulturalDomain.ARTS)],
                )
                ics_text = export_ics(plan)

                # 1. Standard envelope
                self.assertIn("BEGIN:VCALENDAR", ics_text)
                self.assertIn("VERSION:2.0", ics_text)
                self.assertIn("PRODID:-//CULTURA//Cultural Intelligence Itinerary Agent//EN", ics_text)
                self.assertIn("CALSCALE:GREGORIAN", ics_text)
                self.assertIn("METHOD:PUBLISH", ics_text)
                self.assertIn("END:VCALENDAR", ics_text)

                # 2. Exactly 8 VEVENT items
                events = re.findall(r"BEGIN:VEVENT(.*?)END:VEVENT", ics_text, re.DOTALL)
                self.assertEqual(len(events), 8, f"Expected 8 VEVENT blocks in {hub}, found {len(events)}")

                uids = []
                for idx, ev in enumerate(events):
                    # Required fields check
                    required_fields = [
                        "UID:",
                        "DTSTAMP:",
                        "DTSTART:",
                        "DTEND:",
                        "SUMMARY:",
                        "DESCRIPTION:",
                        "LOCATION:",
                        "GEO:",
                        "CATEGORIES:",
                        "STATUS:CONFIRMED",
                    ]
                    for req in required_fields:
                        self.assertIn(req, ev, f"Missing {req} in event {idx} for hub {hub}")

                    # UID uniqueness
                    uid_match = re.search(r"UID:([^\r\n]+)", ev)
                    self.assertIsNotNone(uid_match)
                    uids.append(uid_match.group(1))

                    # Parseable ISO/UTC timestamps
                    dtstart_str = re.search(r"DTSTART:([^\r\n]+)", ev).group(1)
                    dtend_str = re.search(r"DTEND:([^\r\n]+)", ev).group(1)
                    dtstamp_str = re.search(r"DTSTAMP:([^\r\n]+)", ev).group(1)

                    t_start = datetime.strptime(dtstart_str, "%Y%m%dT%H%M%SZ")
                    t_end = datetime.strptime(dtend_str, "%Y%m%dT%H%M%SZ")
                    t_stamp = datetime.strptime(dtstamp_str, "%Y%m%dT%H%M%SZ")

                    self.assertIsNotNone(t_stamp)
                    # Chronological invariant: DTSTART strictly before DTEND (including night midnight crossing)
                    self.assertLess(
                        t_start,
                        t_end,
                        f"DTSTART {t_start} is not before DTEND {t_end} at slot {idx} in {hub}",
                    )

                    # GEO coordinates: RFC 5545 float;float format
                    geo_match = re.search(r"GEO:([-+]?\d*\.?\d+);([-+]?\d*\.?\d+)", ev)
                    self.assertIsNotNone(geo_match, f"Malformed GEO property in event {idx} for {hub}")
                    lat = float(geo_match.group(1))
                    lon = float(geo_match.group(2))
                    self.assertGreaterEqual(lat, -90.0)
                    self.assertLessEqual(lat, 90.0)
                    self.assertGreaterEqual(lon, -180.0)
                    self.assertLessEqual(lon, 180.0)

                # Ensure all 8 UIDs are unique
                self.assertEqual(len(set(uids)), 8, f"Duplicate event UIDs detected in {hub}")

    def test_ics_adversarial_sanitization(self):
        """Verifies ICS generator survives hostile characters, semicolons, and newlines."""
        plan = make_adversarial_plan()
        ics_text = export_ics(plan)

        self.assertIn("BEGIN:VCALENDAR", ics_text)
        self.assertIn("END:VCALENDAR", ics_text)
        self.assertEqual(ics_text.count("BEGIN:VEVENT"), 8)
        self.assertEqual(ics_text.count("END:VEVENT"), 8)

        # Ensure no raw unescaped semicolons inside DESCRIPTION
        for line in ics_text.splitlines():
            if line.startswith("DESCRIPTION:"):
                # Description should escape raw semicolons as \;
                self.assertNotIn(";", line.replace(r"\;", ""))

    def test_ics_file_writing(self):
        """Verifies export_ics properly writes to disk, creating nested directories."""
        plan = make_adversarial_plan()
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "nested" / "dir" / "itinerary.ics"
            ret_str = export_ics(plan, output_path=target)
            self.assertTrue(target.exists())
            self.assertIn("\r\n", ret_str)
            self.assertEqual(target.read_bytes().decode("utf-8"), ret_str)


# ============================================================================
# Suite 2: RFC 7946 GeoJSON Exporter Adversarial Verification
# ============================================================================

class TestGeoJsonExporterAdversarial(unittest.IsolatedAsyncioTestCase):
    """Stress tests the RFC 7946 GeoJSON FeatureCollection exporter (.geojson)."""

    async def asyncSetUp(self):
        self.planner = ReActPlanner()

    async def test_geojson_conformance_and_invariants_all_eight_hubs(self):
        """
        Asserts RFC 7946 FeatureCollection, 8 Point features in [lon, lat] order,
        and 1 LineString transit feature matching Point sequence.
        """
        for hub in CULTURAL_HUBS:
            with self.subTest(hub=hub):
                plan = await self.planner.plan_48h(
                    city_hub=hub,
                    taste_seeds=[TasteSeed(name=f"{hub} Culture", domain=CulturalDomain.MUSIC)],
                )
                geo_str = export_geojson(plan)
                data = json.loads(geo_str)

                # 1. FeatureCollection envelope
                self.assertEqual(data.get("type"), "FeatureCollection")
                self.assertIn("properties", data)
                self.assertIn("features", data)

                root_props = data["properties"]
                self.assertEqual(root_props["city_hub"], hub)
                self.assertEqual(root_props["total_venues"], 8)
                self.assertEqual(root_props["total_items"], 8)
                self.assertGreaterEqual(root_props["cultural_coherence_score"], 0.0)
                self.assertLessEqual(root_props["cultural_coherence_score"], 1.0)

                features = data["features"]
                point_features = [f for f in features if f["geometry"]["type"] == "Point"]
                line_features = [f for f in features if f["geometry"]["type"] == "LineString"]

                # 2. Exactly 8 Point features and 1 LineString feature
                self.assertEqual(len(point_features), 8, f"Expected 8 Point features in {hub}, got {len(point_features)}")
                self.assertEqual(len(line_features), 1, f"Expected 1 LineString feature in {hub}, got {len(line_features)}")

                # 3. Coordinate validation: [longitude, latitude] order
                point_coords = []
                for idx, pt in enumerate(point_features):
                    coords = pt["geometry"]["coordinates"]
                    self.assertEqual(len(coords), 2, f"Point {idx} in {hub} does not have 2 coordinates")
                    lon, lat = coords
                    self.assertIsInstance(lon, (int, float))
                    self.assertIsInstance(lat, (int, float))
                    self.assertGreaterEqual(lon, -180.0)
                    self.assertLessEqual(lon, 180.0)
                    self.assertGreaterEqual(lat, -90.0)
                    self.assertLessEqual(lat, 90.0)

                    # Invariant: coordinates match entity [longitude, latitude]
                    item = plan.items[idx]
                    self.assertAlmostEqual(lon, item.entity.coordinates.longitude, places=5)
                    self.assertAlmostEqual(lat, item.entity.coordinates.latitude, places=5)
                    point_coords.append(coords)

                    # Properties validation
                    props = pt["properties"]
                    self.assertEqual(props["id"], item.entity.id)
                    self.assertEqual(props["venue_name"], item.entity.name)
                    self.assertEqual(props["domain"], item.entity.domain.value)
                    self.assertEqual(props["slot"], item.slot.value)
                    self.assertEqual(props["day"], item.day)
                    self.assertEqual(props["time_window"], item.time_window)
                    self.assertEqual(props["affinity_score"], round(item.affinity_score, 4))
                    self.assertEqual(props["transit_from_previous_min"], item.transit_from_previous_min)

                # 4. LineString transit route matches point coordinates in sequence
                route = line_features[0]
                route_coords = route["geometry"]["coordinates"]
                self.assertEqual(route_coords, point_coords, f"Transit route does not match point coordinates in {hub}")
                self.assertEqual(route["properties"]["feature_type"], "itinerary_route")
                self.assertEqual(route["properties"]["total_stops"], 8)
                self.assertEqual(
                    route["properties"]["total_transit_minutes"],
                    sum(it.transit_from_previous_min for it in plan.items),
                )

    def test_geojson_adversarial_metadata(self):
        """Verifies GeoJSON serialization survives adversarial metadata."""
        plan = make_adversarial_plan()
        geo_str = export_geojson(plan)
        data = json.loads(geo_str)

        self.assertEqual(data["type"], "FeatureCollection")
        self.assertEqual(len(data["features"]), 9)
        self.assertEqual(len(data["features"][8]["geometry"]["coordinates"]), 8)


# ============================================================================
# Suite 3: Validated JSON Exporter Round-Trip Adversarial Verification
# ============================================================================

class TestJsonExporterAdversarial(unittest.IsolatedAsyncioTestCase):
    """Stress tests the JSON exporter and asserts exact round-trip deserialization."""

    async def asyncSetUp(self):
        self.planner = ReActPlanner()

    async def test_json_roundtrip_exact_equality_all_eight_hubs(self):
        """
        Exports to JSON, deserializes back into ItineraryPlan via Pydantic V2,
        and asserts exact equality of all fields across all 8 hubs.
        """
        for hub in CULTURAL_HUBS:
            with self.subTest(hub=hub):
                plan = await self.planner.plan_48h(
                    city_hub=hub,
                    taste_seeds=[
                        TasteSeed(name=f"{hub} Art", domain=CulturalDomain.ARTS, weight=1.2),
                        TasteSeed(name=f"{hub} Dining", domain=CulturalDomain.DINING, weight=0.8),
                    ],
                )
                json_str = export_json(plan)
                deserialized = ItineraryPlan.model_validate_json(json_str)

                # 1. Direct equality
                self.assertEqual(deserialized, plan, f"Round-trip equality failed for {hub}")

                # 2. Strict field-by-field verification
                self.assertEqual(deserialized.city_hub, plan.city_hub)
                self.assertEqual(deserialized.cultural_coherence_score, plan.cultural_coherence_score)
                self.assertEqual(deserialized.domain_diversity_score, plan.domain_diversity_score)
                self.assertEqual(deserialized.transit_efficiency_score, plan.transit_efficiency_score)
                self.assertEqual(deserialized.generated_at, plan.generated_at)
                self.assertEqual(deserialized.react_steps_count, plan.react_steps_count)
                self.assertEqual(deserialized.summary, plan.summary)
                self.assertEqual(deserialized.metadata, plan.metadata)

                # Taste seeds equality
                self.assertEqual(len(deserialized.taste_seeds), len(plan.taste_seeds))
                for s_orig, s_deser in zip(plan.taste_seeds, deserialized.taste_seeds):
                    self.assertEqual(s_deser.name, s_orig.name)
                    self.assertEqual(s_deser.domain, s_orig.domain)
                    self.assertEqual(s_deser.weight, s_orig.weight)

                # Schedule items equality
                self.assertEqual(len(deserialized.items), 8)
                for i_orig, i_deser in zip(plan.items, deserialized.items):
                    self.assertEqual(i_deser.day, i_orig.day)
                    self.assertEqual(i_deser.slot, i_orig.slot)
                    self.assertEqual(i_deser.time_window, i_orig.time_window)
                    self.assertEqual(i_deser.affinity_score, i_orig.affinity_score)
                    self.assertEqual(i_deser.curator_notes, i_orig.curator_notes)
                    self.assertEqual(i_deser.transit_from_previous_min, i_orig.transit_from_previous_min)
                    # Entity equality
                    self.assertEqual(i_deser.entity.id, i_orig.entity.id)
                    self.assertEqual(i_deser.entity.name, i_orig.entity.name)
                    self.assertEqual(i_deser.entity.domain, i_orig.entity.domain)
                    self.assertEqual(i_deser.entity.latitude, i_orig.entity.latitude)
                    self.assertEqual(i_deser.entity.longitude, i_orig.entity.longitude)
                    self.assertEqual(i_deser.entity.vibe_tags, i_orig.entity.vibe_tags)

    def test_json_roundtrip_adversarial_plan(self):
        """Verifies JSON roundtrip exact equality with adversarial characters."""
        plan = make_adversarial_plan()
        json_str = export_json(plan)
        deserialized = ItineraryPlan.model_validate_json(json_str)
        self.assertEqual(deserialized, plan)


# ============================================================================
# Suite 4: Markdown Exporter Syntax & Formatting Invariant Verification
# ============================================================================

class TestMarkdownExporterAdversarial(unittest.IsolatedAsyncioTestCase):
    """Stress tests the Markdown travel guide exporter (.md)."""

    async def asyncSetUp(self):
        self.planner = ReActPlanner()

    async def test_markdown_syntax_invariants_all_eight_hubs(self):
        """Verifies GFM table syntax, 3-column alignment, 8 slot cards, and maps links."""
        for hub in CULTURAL_HUBS:
            with self.subTest(hub=hub):
                plan = await self.planner.plan_48h(
                    city_hub=hub,
                    taste_seeds=[TasteSeed(name=f"{hub} Culture", domain=CulturalDomain.DINING)],
                )
                md = export_markdown(plan)

                # 1. Heading hierarchy
                self.assertTrue(md.startswith(f"# 📍 CULTURA 48-Hour Cultural Blueprint: {hub}"))
                self.assertIn("## 📊 Diurnal Harmony & Quality Metrics", md)
                self.assertIn("## 🎯 Grounded Taste Seeds", md)
                self.assertIn("## 🗓️ 48-Hour Curated Diurnal Itinerary", md)
                self.assertIn("## 🧭 Transit & Spatio-Temporal Topology", md)

                # 2. Table structure (GFM table with 3 columns)
                self.assertIn("| Metric | Score | Assessment |", md)
                self.assertIn("| :--- | :---: | :--- |", md)

                table_lines = [l for l in md.splitlines() if l.startswith("|") and l.endswith("|")]
                self.assertEqual(len(table_lines), 6, f"Expected 6 table lines in {hub}, got {len(table_lines)}")
                for line in table_lines:
                    self.assertEqual(line.count("|"), 4, f"Malformed table row in {hub}: {line}")

                # 3. Day 1 & Day 2 sections
                self.assertIn("### ☀️ Day 1", md)
                self.assertIn("### ☀️ Day 2", md)

                # 4. Exactly 8 slot headers
                slot_headers = re.findall(r"#### 🏷️ (.*?)\n", md)
                self.assertEqual(len(slot_headers), 8, f"Expected 8 slot headers in {hub}, got {len(slot_headers)}")

                # 5. Exactly 8 Google Maps search links
                maps_links = re.findall(r"\[([^\]]+)\]\((https://www.google.com/maps/search/\?api=1&query=[^\)]+)\)", md)
                self.assertEqual(len(maps_links), 8, f"Expected 8 maps links in {hub}, got {len(maps_links)}")

                # 6. Spatio-temporal summary
                self.assertIn("- **Total Cultural Stops:** 8 stops across 2 days", md)
                self.assertIn(f"- **Total Transit Duration:** {sum(it.transit_from_previous_min for it in plan.items)} minutes total travel time", md)
                self.assertIn(f"- **Generated At:** `{plan.generated_at}` UTC", md)
                self.assertIn("Copyright 2026 R Jan Steve Daniel", md)

    def test_markdown_adversarial_plan(self):
        """Verifies Markdown generation does not break with adversarial inputs."""
        plan = make_adversarial_plan()
        md = export_markdown(plan)

        self.assertIn("# 📍 CULTURA 48-Hour Cultural Blueprint: Tokyo", md)
        self.assertIn("| Metric | Score | Assessment |", md)
        self.assertEqual(len(re.findall(r"#### 🏷️ (.*?)\n", md)), 8)


# ============================================================================
# Suite 5: Batch Exporter Dispatcher Invariants
# ============================================================================

class TestExportItineraryDispatcher(unittest.TestCase):
    """Stress tests the export_itinerary dispatcher wrapper."""

    def test_export_itinerary_format_aliases_and_batching(self):
        """Tests format normalization (.ics, ics, markdown, .md, .geojson, json)."""
        plan = make_adversarial_plan()
        with tempfile.TemporaryDirectory() as td:
            formats = [".ics", "markdown", ".geojson", "json"]
            result = export_itinerary(plan, export_formats=formats, output_dir=td)

            self.assertEqual(set(result.keys()), {"ics", "md", "geojson", "json"})
            for ext, fpath in result.items():
                p = Path(fpath)
                self.assertTrue(p.exists(), f"File {fpath} was not created")
                self.assertGreater(p.stat().st_size, 0)

    def test_export_itinerary_unsupported_format_raises(self):
        """Asserts ValueError on unsupported formats."""
        plan = make_adversarial_plan()
        with tempfile.TemporaryDirectory() as td:
            for bad_fmt in ["pdf", "xml", "docx", ""]:
                with self.assertRaises(ValueError):
                    export_itinerary(plan, export_formats=[bad_fmt], output_dir=td)


# ============================================================================
# Suite 6: Streamlit UI Components Adversarial Verification
# ============================================================================

class TestStreamlitComponentsAdversarial(unittest.TestCase):
    """Stress tests Streamlit UI components and headless app lifecycle."""

    def test_build_pydeck_map_all_eight_hubs(self):
        """Verifies build_pydeck_map across all 8 cultural hubs."""
        for hub in CULTURAL_HUBS:
            plan = make_adversarial_plan(hub=hub)
            hub_meta = HUB_METADATA.get(hub, HUB_METADATA["Bangalore"])

            deck = build_pydeck_map(plan, hub_meta)
            self.assertIsNotNone(deck)
            self.assertEqual(len(deck.layers), 2)

            path_layer, scatter_layer = deck.layers
            # PathLayer checks
            self.assertEqual(path_layer.type, "PathLayer")
            self.assertEqual(len(path_layer.data[0]["path"]), 8)

            # ScatterplotLayer checks
            self.assertEqual(scatter_layer.type, "ScatterplotLayer")
            self.assertEqual(len(scatter_layer.data), 8)

    def test_generate_plan_tempos_and_budgets(self):
        """Verifies generate_plan executes across various tempo and budget combinations."""
        seeds = [TasteSeed(name="Coffee", domain=CulturalDomain.DINING)]
        for tempo in ["relaxed", "moderate", "intensive"]:
            for budget in ["low", "medium", "high"]:
                plan = generate_plan("Bangalore", seeds, budget=budget, tempo=tempo)
                self.assertEqual(len(plan.items), 8)

    def test_streamlit_apptest_lifecycle_all_eight_hubs(self):
        """
        Executes Streamlit app headlessly via AppTest across all 8 hubs,
        asserting 0 runtime exceptions, 8 slot expanders, and 4 download buttons.
        """
        for hub in CULTURAL_HUBS:
            at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "src/cultura/web/app.py"), default_timeout=30).run()
            self.assertEqual(len(at.exception), 0, f"AppTest initial exception in {hub}")

            # Select hub
            at.selectbox[0].select(hub).run()
            self.assertEqual(len(at.exception), 0, f"AppTest exception after selecting {hub}")

            # Click generate
            at.button[0].click().run()
            self.assertEqual(len(at.exception), 0, f"AppTest exception after generate in {hub}")

            # Verify UI components
            self.assertEqual(len(at.tabs), 2, f"Expected 2 tabs (Day 1 & Day 2) in {hub}")
            self.assertEqual(len(at.expander), 8, f"Expected 8 expanders in {hub}")
            self.assertEqual(len(at.download_button), 4, f"Expected 4 download buttons in {hub}")

    def test_streamlit_apptest_empty_seeds_graceful_fallback(self):
        """Tests that deselecting all presets and leaving custom seed blank falls back cleanly."""
        at = AppTest.from_file(str(Path(__file__).resolve().parent.parent / "src/cultura/web/app.py"), default_timeout=30).run()
        # Unselect presets
        while len(at.multiselect[0].value) > 0:
            at.multiselect[0].unselect(at.multiselect[0].value[0]).run()
        at.text_input[0].input("").run()
        at.button[0].click().run()

        self.assertEqual(len(at.exception), 0, "Failed graceful fallback on empty seeds")
        self.assertEqual(len(at.expander), 8)
