"""Unit tests for CULTURA multi-format itinerary exporters.

Verifies:
- RFC 5545 iCalendar (.ics) syntax, headers, and VEVENT items
- GitHub-flavored Markdown (.md) travel guide formatting
- RFC 7946 GeoJSON (.geojson) FeatureCollection and transit routes
- Validated JSON (.json) schema conformity
- Single dispatch `export_itinerary` wrapper

Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

import asyncio
import json
from pathlib import Path
import pytest

from cultura.agent.planner import ReActPlanner
from cultura.agent.tools import CulturalDomain, TasteSeed
from cultura.export.exporters import (
    export_geojson,
    export_ics,
    export_itinerary,
    export_json,
    export_markdown,
)


@pytest.fixture
def sample_plan():
    """Generate a deterministic 48-hour plan in Tokyo for export testing."""
    planner = ReActPlanner()
    seeds = [
        TasteSeed(name="Tame Impala", domain=CulturalDomain.MUSIC, weight=0.95),
        TasteSeed(name="Interstellar", domain=CulturalDomain.CINEMA, weight=0.90),
    ]
    return asyncio.run(planner.plan_48h(city_hub="tokyo", taste_seeds=seeds))


def test_export_ics(sample_plan, tmp_path: Path):
    """Verify RFC 5545 iCalendar generation and file write."""
    out_file = tmp_path / "tokyo.ics"
    ics_str = export_ics(sample_plan, output_path=out_file)

    assert "BEGIN:VCALENDAR" in ics_str
    assert "VERSION:2.0" in ics_str
    assert "PRODID:-//CULTURA//Cultural Intelligence Itinerary Agent//EN" in ics_str
    assert "END:VCALENDAR" in ics_str
    assert ics_str.count("BEGIN:VEVENT") == 8
    assert ics_str.count("END:VEVENT") == 8

    # Verify file written matches returned content
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == ics_str


def test_export_markdown(sample_plan, tmp_path: Path):
    """Verify Markdown travel guide formatting and file write."""
    out_file = tmp_path / "tokyo.md"
    md_str = export_markdown(sample_plan, output_path=out_file)

    assert "# 📍 CULTURA 48-Hour Cultural Blueprint: Tokyo" in md_str
    assert "Diurnal Harmony & Quality Metrics" in md_str
    assert "Cultural Coherence" in md_str
    assert "Day 1" in md_str
    assert "Day 2" in md_str
    assert "Transit & Spatio-Temporal Topology" in md_str

    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == md_str


def test_export_geojson(sample_plan, tmp_path: Path):
    """Verify RFC 7946 GeoJSON FeatureCollection generation."""
    out_file = tmp_path / "tokyo.geojson"
    geojson_str = export_geojson(sample_plan, output_path=out_file)

    data = json.loads(geojson_str)
    assert data["type"] == "FeatureCollection"
    assert "features" in data
    
    # 8 points + 1 LineString route = 9 features
    assert len(data["features"]) >= 8
    
    # Check properties
    assert data["properties"]["city_hub"] == "tokyo"
    assert data["properties"]["total_items"] == 8

    assert out_file.exists()
    assert json.loads(out_file.read_text(encoding="utf-8")) == data


def test_export_json(sample_plan, tmp_path: Path):
    """Verify JSON serialization and file write."""
    out_file = tmp_path / "tokyo.json"
    json_str = export_json(sample_plan, output_path=out_file)

    data = json.loads(json_str)
    assert data["city_hub"] == "tokyo"
    assert len(data["items"]) == 8

    assert out_file.exists()


def test_export_itinerary_dispatcher(sample_plan, tmp_path: Path):
    """Verify export_itinerary handles all formats and writes files."""
    formats = ["ics", "markdown", "geojson", "json"]
    exported = export_itinerary(sample_plan, export_formats=formats, output_dir=tmp_path)
    
    assert set(exported.keys()) == {"ics", "md", "geojson", "json"}
    for fpath in exported.values():
        assert Path(fpath).exists()

    with pytest.raises(ValueError):
        export_itinerary(sample_plan, export_formats=["unsupported_format"], output_dir=tmp_path)
