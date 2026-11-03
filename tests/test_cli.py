"""
CULTURA Automated Test Suite: CLI, Exporters, & Web Dashboard.
Verifies:
- `cultura --help`: command routing, help text, and metadata
- `cultura doctor`: functional checks (Python >= 3.10, 8 hubs, 82 entities, mock mode, timezone)
- `cultura doctor`: strict <100ms wall-clock SLA benchmark
- `cultura plan`: default Bangalore hub, Tokyo custom hub, ASCII timeline tree, score table
- `cultura plan`: robust error handling on invalid hubs and missing seeds
- Multi-format itinerary exporters: RFC 5545 iCalendar, Markdown guide, RFC 7946 GeoJSON, JSON
- Clean import of Streamlit web application (`cultura.web.app`)

Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cultura.cli.main import app
from cultura.export.exporters import (
    export_geojson,
    export_ics,
    export_itinerary,
    export_json,
    export_markdown,
)


@pytest.fixture
def runner() -> CliRunner:
    """Provides an isolated Typer CliRunner."""
    return CliRunner()


# ============================================================================
# 1. CLI Help & Metadata Tests
# ============================================================================

def test_cli_help(runner: CliRunner) -> None:
    """Verifies `cultura --help` exits 0 and describes core CLI commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "CULTURA" in result.output
    assert "doctor" in result.output
    assert "plan" in result.output
    assert "hubs" in result.output
    assert "version" in result.output


def test_cli_version(runner: CliRunner) -> None:
    """Verifies `cultura version` displays author and version metadata."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "CULTURA" in result.output
    assert "R Jan Steve Daniel" in result.output


def test_cli_hubs(runner: CliRunner) -> None:
    """Verifies `cultura hubs` displays all 8 cultural hubs with coordinates."""
    result = runner.invoke(app, ["hubs"])
    assert result.exit_code == 0
    for hub in ["Bangalore", "Mumbai", "New York", "London", "Tokyo", "Paris", "Berlin", "San Francisco"]:
        assert hub in result.output


# ============================================================================
# 2. Doctor Diagnostics & SLA Benchmark Tests
# ============================================================================

def test_doctor_functional(runner: CliRunner) -> None:
    """
    Verifies `cultura doctor` runs all 4 core checks and returns exit code 0:
    1. Python runtime version (>=3.10)
    2. Mock catalog integrity (82 entities across 8 hubs & 7 domains)
    3. Client connectivity (Mock Mode Active)
    4. System time & timezone alignment
    """
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code == 0
    output = result.output

    # Check assertions matching technical specification
    assert "Python" in output
    assert "8 hubs" in output
    assert "82 entities" in output
    assert "Mock Mode Active" in output or "Offline Fallback" in output
    assert "System Time" in output or "Synchronized" in output
    assert "Diagnostics" in output or "Health Check Summary" in output


def test_doctor_sla_benchmark(runner: CliRunner) -> None:
    """
    Strict SLA Benchmark: Verifies `cultura doctor` wall-clock execution time
    is strictly under 100 milliseconds (< 0.100 seconds).
    """
    # Execute benchmark measurement
    t0 = time.perf_counter()
    result = runner.invoke(app, ["doctor"])
    elapsed = time.perf_counter() - t0

    assert result.exit_code == 0
    assert elapsed < 0.100, (
        f"SLA Violation: 'cultura doctor' took {elapsed * 1000.0:.2f}ms "
        f"(Strict SLA threshold is < 100.0ms)"
    )


# ============================================================================
# 3. Plan Command Execution & Error Handling Tests
# ============================================================================

def test_plan_default_bangalore(runner: CliRunner) -> None:
    """
    Runs `cultura plan --hub Bangalore -s "Coffee:dining"`.
    Asserts exit code 0, ASCII timeline tree, and score table.
    """
    result = runner.invoke(app, ["plan", "--hub", "Bangalore", "-s", "Coffee:dining"])
    assert result.exit_code == 0
    output = result.output

    # Verify Header panel
    assert "Bangalore" in output

    # Verify ASCII Timeline Tree elements
    assert "Day 1" in output
    assert "Day 2" in output
    assert "Morning" in output
    assert "Afternoon" in output
    assert "Evening" in output
    assert "Night" in output

    # Verify Rich Score Table metrics
    assert "Cultural Coherence" in output
    assert "Shannon Domain Diversity" in output
    assert "Transit Efficiency" in output
    assert "Overall Quality Score" in output


def test_plan_custom_hub_tokyo(runner: CliRunner) -> None:
    """
    Runs `cultura plan --hub Tokyo -s "Jazz:music"`.
    Asserts exit code 0 and Tokyo venues in timeline tree.
    """
    result = runner.invoke(app, ["plan", "--hub", "Tokyo", "-s", "Jazz:music"])
    assert result.exit_code == 0
    output = result.output

    assert "Tokyo" in output
    assert "Day 1" in output
    assert "Day 2" in output
    assert "Cultural Coherence" in output


def test_plan_invalid_hub_error(runner: CliRunner) -> None:
    """
    Runs `cultura plan --hub Atlantis`.
    Asserts non-zero exit code (1 or 2) and clear, friendly error message without traceback.
    """
    result = runner.invoke(app, ["plan", "--hub", "Atlantis"])
    assert result.exit_code in (1, 2)
    assert "Unsupported cultural hub" in result.output or "Atlantis" in result.output
    # Ensure no raw traceback
    assert "Traceback (most recent call last)" not in result.output


def test_plan_empty_seeds_error(runner: CliRunner) -> None:
    """
    Runs `cultura plan --hub Bangalore` with no seeds.
    Asserts non-zero exit code (1 or 2) and clear error message.
    """
    result = runner.invoke(app, ["plan", "--hub", "Bangalore"])
    assert result.exit_code in (1, 2)
    assert "seed" in result.output.lower() or "error" in result.output.lower()
    assert "Traceback (most recent call last)" not in result.output


def test_plan_exports(runner: CliRunner, tmp_path: Path) -> None:
    """
    Runs `cultura plan --hub Bangalore -s "Art:arts" --export json --export md --output-dir <tmp_path>`.
    Asserts files are generated and non-empty.
    """
    out_dir = str(tmp_path / "itinerary_exports")
    result = runner.invoke(
        app,
        [
            "plan",
            "--hub",
            "Bangalore",
            "-s",
            "Art:arts",
            "--export",
            "json",
            "--export",
            "md",
            "--output-dir",
            out_dir,
        ],
    )
    assert result.exit_code == 0
    output = result.output

    # Check export confirmation table rendered
    assert "Generated Itinerary Export Files" in output

    json_file = Path(out_dir) / "bangalore_itinerary.json"
    md_file = Path(out_dir) / "bangalore_itinerary.md"

    assert json_file.exists(), f"Expected {json_file} to exist"
    assert json_file.stat().st_size > 500, f"JSON file {json_file} is suspiciously small"

    assert md_file.exists(), f"Expected {md_file} to exist"
    assert md_file.stat().st_size > 500, f"Markdown file {md_file} is suspiciously small"

    # Verify JSON content structure
    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["city_hub"] == "Bangalore"
    assert len(data["items"]) == 8

    # Verify Markdown content structure
    with open(md_file, "r", encoding="utf-8") as f:
        md_text = f.read()
    assert "CULTURA" in md_text
    assert "Bangalore" in md_text
    assert "Day 1" in md_text
    assert "Day 2" in md_text


def test_plan_all_export_formats(runner: CliRunner, tmp_path: Path) -> None:
    """
    Tests all 4 export formats (ics, md, geojson, json) simultaneously.
    """
    out_dir = str(tmp_path / "all_exports")
    result = runner.invoke(
        app,
        [
            "plan",
            "--hub",
            "Paris",
            "-s",
            "Louvre:arts",
            "-s",
            "Bistro:dining",
            "--export",
            "ics",
            "--export",
            "md",
            "--export",
            "geojson",
            "--export",
            "json",
            "--output-dir",
            out_dir,
        ],
    )
    assert result.exit_code == 0

    ics_f = Path(out_dir) / "paris_itinerary.ics"
    md_f = Path(out_dir) / "paris_itinerary.md"
    geojson_f = Path(out_dir) / "paris_itinerary.geojson"
    json_f = Path(out_dir) / "paris_itinerary.json"

    for fpath in [ics_f, md_f, geojson_f, json_f]:
        assert fpath.exists(), f"Missing exported file: {fpath}"
        assert fpath.stat().st_size > 0, f"Empty file: {fpath}"

    # Verify RFC 5545 iCalendar compliance
    with open(ics_f, "r", encoding="utf-8") as f:
        ics_text = f.read()
    assert "BEGIN:VCALENDAR" in ics_text
    assert "VERSION:2.0" in ics_text
    assert "BEGIN:VEVENT" in ics_text
    assert "END:VCALENDAR" in ics_text
    assert ics_text.count("BEGIN:VEVENT") == 8

    # Verify RFC 7946 GeoJSON compliance
    with open(geojson_f, "r", encoding="utf-8") as f:
        geo_data = json.load(f)
    assert geo_data["type"] == "FeatureCollection"
    # 8 points + 1 route line = 9 features
    assert len(geo_data["features"]) == 9
    line_features = [f for f in geo_data["features"] if f["geometry"]["type"] == "LineString"]
    point_features = [f for f in geo_data["features"] if f["geometry"]["type"] == "Point"]
    assert len(point_features) == 8
    assert len(line_features) == 1


# ============================================================================
# 4. Streamlit App Import Integrity Test
# ============================================================================

def test_streamlit_app_import() -> None:
    """Verifies that `cultura.web.app` can be imported cleanly without errors."""
    import cultura.web.app as web_app
    assert hasattr(web_app, "main")
    assert hasattr(web_app, "build_pydeck_map")
    assert hasattr(web_app, "generate_plan")


# ============================================================================
# 5. Standalone Exporters Unit Tests
# ============================================================================

def test_standalone_exporters_unit(tmp_path: Path) -> None:
    """Directly verifies standalone exporter functions with a generated plan."""
    from cultura.agent.planner import ReActPlanner
    from cultura.agent.tools import CulturalDomain, TasteSeed
    import asyncio

    planner = ReActPlanner()
    plan = asyncio.run(
        planner.plan_48h(
            city_hub="Berlin",
            taste_seeds=[
                TasteSeed(name="Berghain", domain=CulturalDomain.NIGHTLIFE),
                TasteSeed(name="Boros Collection", domain=CulturalDomain.ARTS),
            ],
        )
    )

    # Test export_ics string & file
    ics_file = str(tmp_path / "berlin.ics")
    ics_str = export_ics(plan, ics_file)
    assert "BEGIN:VCALENDAR" in ics_str
    assert os.path.exists(ics_file)

    # Test export_markdown string & file
    md_file = str(tmp_path / "berlin.md")
    md_str = export_markdown(plan, md_file)
    assert "# 📍 CULTURA 48-Hour Cultural Blueprint: Berlin" in md_str
    assert os.path.exists(md_file)

    # Test export_geojson string & file
    geo_file = str(tmp_path / "berlin.geojson")
    geo_str = export_geojson(plan, geo_file)
    geo_json = json.loads(geo_str)
    assert geo_json["type"] == "FeatureCollection"
    assert os.path.exists(geo_file)

    # Test export_json string & file
    json_file = str(tmp_path / "berlin.json")
    json_str = export_json(plan, json_file)
    parsed = json.loads(json_str)
    assert parsed["city_hub"] == "Berlin"
    assert os.path.exists(json_file)

    # Test export_itinerary helper
    export_dict = export_itinerary(plan, ["ics", "md", "geojson", "json"], tmp_path / "batch")
    assert len(export_dict) == 4
    for ext, path in export_dict.items():
        assert os.path.exists(path)
