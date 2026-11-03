"""
CULTURA Multi-Format Itinerary Exporters.
Provides standard-compliant exporters for:
- RFC 5545 iCalendar (.ics)
- GitHub-flavored Markdown Travel Guide (.md)
- RFC 7946 GeoJSON FeatureCollection with Transit LineString (.geojson)
- Pydantic-validated JSON (.json)

Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from cultura.agent.tools import ItineraryPlan, TimeSlot


def export_ics(plan: ItineraryPlan, output_path: Optional[Union[str, Path]] = None) -> str:
    """
    Export an ItineraryPlan to RFC 5545 iCalendar standard format (.ics).

    Generates a VCALENDAR with VEVENT items for each scheduled itinerary slot,
    including exact start/end timestamps, summary, venue location, geo coordinates,
    curator notes, and domain categories.

    Args:
        plan: Validated 48-hour ItineraryPlan.
        output_path: Optional file path where .ics content will be written.

    Returns:
        The complete RFC 5545 formatted iCalendar string (CRLF line endings).
    """
    slot_hours = {
        TimeSlot.MORNING: ("090000", "123000"),
        TimeSlot.AFTERNOON: ("130000", "163000"),
        TimeSlot.EVENING: ("170000", "203000"),
        TimeSlot.NIGHT: ("210000", "003000"),
    }

    now_utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Project start date: next calendar day at midnight
    base_date = datetime.now(timezone.utc).date() + timedelta(days=1)

    lines: List[str] = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//CULTURA//Cultural Intelligence Itinerary Agent//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:CULTURA 48H - {plan.city_hub.title()}",
        f"X-WR-TIMEZONE:UTC",
    ]

    for idx, item in enumerate(plan.items):
        day_offset = item.day - 1
        event_date = base_date + timedelta(days=day_offset)
        date_str = event_date.strftime("%Y%m%d")

        st_hour, end_hour = slot_hours.get(item.slot, ("100000", "120000"))
        dtstart = f"{date_str}T{st_hour}Z"

        if item.slot == TimeSlot.NIGHT:
            next_date_str = (event_date + timedelta(days=1)).strftime("%Y%m%d")
            dtend = f"{next_date_str}T{end_hour}Z"
        else:
            dtend = f"{date_str}T{end_hour}Z"

        entity = item.entity
        domain_str = entity.domain.value if hasattr(entity.domain, "value") else str(entity.domain)
        slot_name = item.slot.value.title() if hasattr(item.slot, "value") else str(item.slot).title()
        uid = f"cultura-{plan.city_hub.lower().replace(' ', '_')}-d{item.day}-s{idx}-{entity.id}@cultura.ai"

        # Sanitize text for iCalendar RFC 5545
        desc_parts = [
            f"Curator Notes: {item.curator_notes or 'Curated cultural anchor'}",
            f"Why Qloo Matched: {item.why_recommended}",
            f"Domain: {domain_str.upper()}",
            f"Vibe Tags: {', '.join(entity.tags)}",
            f"Transit from prior: {item.transit_from_previous_min}m",
            f"Affinity Match: {int(item.affinity_score * 100)}%",
        ]
        description = "\\n".join(part.replace("\n", " ").replace(";", "\\;") for part in desc_parts)
        summary = f"{entity.name} [{slot_name}]"
        location = f"{entity.name}, {entity.address}"
        lat = entity.coordinates.latitude
        lon = entity.coordinates.longitude

        lines.extend([
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTAMP:{now_utc}",
            f"DTSTART:{dtstart}",
            f"DTEND:{dtend}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{location}",
            f"GEO:{lat:.6f};{lon:.6f}",
            f"CATEGORIES:{domain_str.upper()}",
            "STATUS:CONFIRMED",
            "END:VEVENT",
        ])

    lines.append("END:VCALENDAR")
    ics_content = "\r\n".join(lines) + "\r\n"

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8", newline="") as f:
            f.write(ics_content)

    return ics_content


def export_markdown(plan: ItineraryPlan, output_path: Optional[Union[str, Path]] = None) -> str:
    """
    Export an ItineraryPlan to a GitHub-flavored Markdown travel guide (.md).

    Produces a formatted guide containing:
    - Executive summary & taste grounding seeds
    - Diurnal metrics overview table
    - Day 1 and Day 2 diurnal itineraries with venue metadata, address links,
      curator notes, vibe badges, and transit calculations.

    Args:
        plan: Validated 48-hour ItineraryPlan.
        output_path: Optional file path where .md content will be written.

    Returns:
        The complete Markdown string.
    """
    composite_score = (
        plan.cultural_coherence_score * 0.4
        + plan.domain_diversity_score * 0.3
        + plan.transit_efficiency_score * 0.3
    )

    lines: List[str] = [
        f"# 📍 CULTURA 48-Hour Cultural Blueprint: {plan.city_hub.title()}",
        "",
        "> Autonomous Cultural Intelligence & Taste Graph Grounding powered by Qloo.",
        "",
        "## 📊 Diurnal Harmony & Quality Metrics",
        "",
        "| Metric | Score | Assessment |",
        "| :--- | :---: | :--- |",
        f"| **Cultural Coherence** | `{plan.cultural_coherence_score * 100:.1f}%` | High taste graph synergy across cultural anchors |",
        f"| **Shannon Domain Diversity** | `{plan.domain_diversity_score * 100:.1f}%` | Rich anti-clumping multi-domain coverage |",
        f"| **Transit Efficiency** | `{plan.transit_efficiency_score * 100:.1f}%` | Optimized spatio-temporal route topology |",
        f"| **Overall Quality Rating** | `{composite_score * 100:.1f}%` | CULTURA Certified Autonomous Curation |",
        "",
        "## 🎯 Grounded Taste Seeds",
        "",
    ]

    for seed in plan.taste_seeds:
        dom = seed.domain.value if hasattr(seed.domain, "value") else str(seed.domain)
        lines.append(f"- **{seed.name}** (`{dom.upper()}`) — Preference Weight: `{seed.weight:.2f}`")

    lines.extend([
        "",
        "---",
        "",
        "## 🗓️ 48-Hour Curated Diurnal Itinerary",
        "",
    ])

    cur_day = 0
    for item in plan.items:
        if item.day != cur_day:
            cur_day = item.day
            day_theme = "Diurnal Immersion & Cultural Anchors" if cur_day == 1 else "Subcultural Resonance & Explorations"
            lines.extend([
                f"### ☀️ Day {cur_day} — {day_theme}",
                "",
            ])

        slot_name = item.slot.value.title() if hasattr(item.slot, "value") else str(item.slot).title()
        entity = item.entity
        domain_name = entity.domain.value.upper() if hasattr(entity.domain, "value") else str(entity.domain).upper()
        coords = entity.coordinates
        maps_link = f"https://www.google.com/maps/search/?api=1&query={coords.latitude},{coords.longitude}"
        transit_str = f"**Transit:** `{item.transit_from_previous_min} min` from prior stop" if item.transit_from_previous_min > 0 else "**Transit:** Starting departure point"

        lines.extend([
            f"#### 🏷️ {slot_name} ({item.time_window}): {entity.name} [{domain_name}]",
            f"- **Match Affinity:** `{int(item.affinity_score * 100)}% match`",
            f"- **Address:** [{entity.address}]({maps_link})",
            f"- **Curator Insight:** *{item.curator_notes or item.why_recommended}*",
            f"- **Why Qloo Matched:** {item.why_recommended}",
            f"- **Vibe Tags:** `{'`, `'.join(entity.tags)}`",
            f"- {transit_str}",
            "",
        ])

    lines.extend([
        "---",
        "",
        "## 🧭 Transit & Spatio-Temporal Topology",
        f"- **Total Cultural Stops:** {len(plan.items)} stops across 2 days",
        f"- **Total Transit Duration:** {sum(it.transit_from_previous_min for it in plan.items)} minutes total travel time",
        f"- **Generated At:** `{plan.generated_at}` UTC",
        "",
        "_Curated autonomously by CULTURA: Taste Graph Agent. Copyright 2026 R Jan Steve Daniel._",
    ])

    md_content = "\n".join(lines) + "\n"

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(md_content)

    return md_content


def export_geojson(plan: ItineraryPlan, output_path: Optional[Union[str, Path]] = None) -> str:
    """
    Export an ItineraryPlan to RFC 7946 GeoJSON FeatureCollection (.geojson).

    Constructs:
    1. Point features for each venue stop with metadata properties (domain, vibe, slot, day, notes).
    2. A LineString feature representing the chronological transit route connecting all stops.

    Args:
        plan: Validated 48-hour ItineraryPlan.
        output_path: Optional file path where .geojson content will be written.

    Returns:
        Formatted JSON string of the GeoJSON FeatureCollection.
    """
    features: List[Dict[str, Any]] = []
    route_coords: List[List[float]] = []

    for item in plan.items:
        entity = item.entity
        lon = float(entity.coordinates.longitude)
        lat = float(entity.coordinates.latitude)
        route_coords.append([lon, lat])

        domain_val = entity.domain.value if hasattr(entity.domain, "value") else str(entity.domain)
        slot_val = item.slot.value if hasattr(item.slot, "value") else str(item.slot)

        point_feature: Dict[str, Any] = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "id": entity.id,
                "venue_name": entity.name,
                "domain": domain_val,
                "vibe": entity.tags,
                "slot": slot_val,
                "day": item.day,
                "time_window": item.time_window,
                "affinity_score": round(item.affinity_score, 4),
                "address": entity.address,
                "curator_notes": item.curator_notes,
                "why_recommended": item.why_recommended,
                "transit_from_previous_min": item.transit_from_previous_min,
            },
        }
        features.append(point_feature)

    # LineString route connecting sequential itinerary stops
    route_feature: Dict[str, Any] = {
        "type": "Feature",
        "geometry": {
            "type": "LineString",
            "coordinates": route_coords,
        },
        "properties": {
            "feature_type": "itinerary_route",
            "route_name": f"48-Hour Cultural Route - {plan.city_hub.title()}",
            "city_hub": plan.city_hub,
            "total_stops": len(plan.items),
            "total_transit_minutes": sum(it.transit_from_previous_min for it in plan.items),
        },
    }
    features.append(route_feature)

    geojson_dict: Dict[str, Any] = {
        "type": "FeatureCollection",
        "properties": {
            "city_hub": plan.city_hub,
            "cultural_coherence_score": plan.cultural_coherence_score,
            "domain_diversity_score": plan.domain_diversity_score,
            "transit_efficiency_score": plan.transit_efficiency_score,
            "total_venues": len(plan.items),
            "total_items": len(plan.items),
            "generated_at": plan.generated_at,
        },
        "features": features,
    }

    geojson_str = json.dumps(geojson_dict, indent=2, ensure_ascii=False)

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(geojson_str)

    return geojson_str


def export_json(plan: ItineraryPlan, output_path: Optional[Union[str, Path]] = None) -> str:
    """
    Export an ItineraryPlan to validated JSON (.json).

    Args:
        plan: Validated 48-hour ItineraryPlan.
        output_path: Optional file path where .json content will be written.

    Returns:
        Formatted JSON string.
    """
    json_str = plan.model_dump_json(indent=2)

    if output_path:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            f.write(json_str)

    return json_str


def export_itinerary(
    plan: ItineraryPlan,
    export_formats: List[str],
    output_dir: Union[str, Path],
) -> Dict[str, str]:
    """
    Export an itinerary into multiple formats and save files in output_dir.

    Supported format identifiers:
    - 'ics', '.ics' -> iCalendar RFC 5545
    - 'md', '.md', 'markdown' -> GitHub-flavored Markdown
    - 'geojson', '.geojson' -> GeoJSON RFC 7946
    - 'json', '.json' -> Validated JSON

    Args:
        plan: Validated 48-hour ItineraryPlan.
        export_formats: List of format names (e.g. ['json', 'md']).
        output_dir: Destination directory.

    Returns:
        Dictionary mapping normalized format name to absolute or relative file path.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    hub_slug = plan.city_hub.lower().replace(" ", "_")
    base_name = f"{hub_slug}_itinerary"
    exported_files: Dict[str, str] = {}

    for fmt in export_formats:
        norm = fmt.strip().lstrip(".").lower()
        if norm == "ics":
            target = out_dir / f"{base_name}.ics"
            export_ics(plan, target)
            exported_files["ics"] = str(target)
        elif norm in ("md", "markdown"):
            target = out_dir / f"{base_name}.md"
            export_markdown(plan, target)
            exported_files["md"] = str(target)
        elif norm == "geojson":
            target = out_dir / f"{base_name}.geojson"
            export_geojson(plan, target)
            exported_files["geojson"] = str(target)
        elif norm == "json":
            target = out_dir / f"{base_name}.json"
            export_json(plan, target)
            exported_files["json"] = str(target)
        else:
            raise ValueError(
                f"Unsupported export format '{fmt}'. Supported formats: ics, md, geojson, json"
            )

    return exported_files
