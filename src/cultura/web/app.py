"""
CULTURA Streamlit Web Dashboard: Autonomous Cultural Intelligence & Taste Graph Agent.
Interactive visual interface featuring:
- Dark mode theme (#0B0E14 background, #151A23 cards, cyan #00F0FF & violet #8A2BE2 accents)
- Sidebar preference controls (Hub, Curated Domain Seeds, Tempo, Budget)
- Diurnal metric cards (Coherence, Diversity, Transit Efficiency, Venues)
- Interactive PyDeck 3D map with ScatterplotLayer and PathLayer
- Diurnal 48-Hour timeline tabs with expandable slot cards
- Multi-format itinerary download buttons (.ics, .md, .geojson, .json)
- 100% offline deterministic operation via Qloo mock catalog

Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, List, Optional

import pydeck as pdk
import streamlit as st

from cultura import __version__
from cultura.agent.planner import ReActPlanner
from cultura.agent.tools import CulturalDomain, ItineraryPlan, TasteSeed, TimeSlot
from cultura.client.mock_data import (
    CULTURAL_DOMAINS,
    CULTURAL_HUBS,
    ENTITIES_BY_HUB,
    HUB_METADATA,
    MOCK_ENTITIES,
)
from cultura.export.exporters import (
    export_geojson,
    export_ics,
    export_json,
    export_markdown,
)

# Custom Dark Mode Styling
DARK_THEME_CSS = """
<style>
    /* Background & Container */
    .stApp {
        background-color: #0B0E14;
        color: #E2E8F0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #0F131C !important;
        border-right: 1px solid #1F2633;
    }

    /* Metric Cards */
    .metric-card {
        background-color: #151A23;
        border: 1px solid #1F2633;
        border-radius: 12px;
        padding: 18px 20px;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border-color: #00F0FF;
    }
    .metric-title {
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .metric-value {
        font-size: 1.85rem;
        font-weight: 700;
        margin-bottom: 4px;
    }
    .metric-desc {
        font-size: 0.75rem;
        color: #64748B;
    }

    /* Accent Colors */
    .cyan-accent { color: #00F0FF !important; }
    .violet-accent { color: #8A2BE2 !important; }
    .green-accent { color: #10B981 !important; }
    .gold-accent { color: #F59E0B !important; }

    /* Timeline Slot Card */
    .slot-card {
        background-color: #151A23;
        border: 1px solid #1F2633;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .slot-card:hover {
        border-color: #8A2BE2;
    }
    .slot-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .domain-tag {
        font-size: 0.7rem;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 6px;
        text-transform: uppercase;
    }
    .tag-dining { background: rgba(249, 115, 22, 0.2); color: #FB923C; }
    .tag-music { background: rgba(217, 70, 239, 0.2); color: #E879F9; }
    .tag-arts { background: rgba(6, 182, 212, 0.2); color: #22D3EE; }
    .tag-cinema { background: rgba(59, 130, 246, 0.2); color: #60A5FA; }
    .tag-nightlife { background: rgba(168, 85, 247, 0.2); color: #C084FC; }
    .tag-literary { background: rgba(34, 197, 94, 0.2); color: #4ADE80; }
    .tag-fashion { background: rgba(244, 63, 94, 0.2); color: #FB7185; }

    /* Header Banner */
    .cultura-header {
        background: linear-gradient(135deg, rgba(0, 240, 255, 0.1) 0%, rgba(138, 43, 226, 0.15) 100%);
        border: 1px solid rgba(0, 240, 255, 0.3);
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 24px;
    }
</style>
"""

PRESET_SEEDS_BY_HUB: Dict[str, List[str]] = {
    "Bangalore": [
        "Third Wave Coffee:dining",
        "The Humming Tree:music",
        "National Gallery of Modern Art:arts",
        "Atta Galatta:literary",
        "Toit Brewpub:nightlife",
        "Suchitra Film Society:cinema",
    ],
    "Mumbai": [
        "Trishna Seafood:dining",
        "The G5A Foundation:arts",
        "NCPA Symphony:music",
        "Prithvi Theatre:arts",
        "Aer Rooftop:nightlife",
        "Kitab Khana:literary",
    ],
    "New York": [
        "Blue Note Jazz Club:music",
        "The Strand Bookstore:literary",
        "Film Forum:cinema",
        "Whitney Museum:arts",
        "Katz's Delicatessen:dining",
        "Dante NYC:nightlife",
    ],
    "London": [
        "Ronnie Scott's:music",
        "Tate Modern:arts",
        "BFI Southbank:cinema",
        "Daunt Books:literary",
        "Dishoom Covent Garden:dining",
        "Nightjar:nightlife",
    ],
    "Tokyo": [
        "Blue Note Tokyo:music",
        "Mori Art Museum:arts",
        "Daikanyama Tsutaya Books:literary",
        "Bunkamura Le Cinema:cinema",
        "Bar Trench:nightlife",
        "Sukiyabashi Jiro:dining",
    ],
    "Paris": [
        "Le Duc des Lombards:music",
        "Centre Pompidou:arts",
        "Shakespeare and Company:literary",
        "Cinematheque Francaise:cinema",
        "Le Syndicat:nightlife",
        "Le Comptoir du Relais:dining",
    ],
    "Berlin": [
        "Berghain / Panorama Bar:nightlife",
        "Boros Foundation:arts",
        "Kino Central:cinema",
        "Do You Read Me?!:literary",
        "A-Trane Jazz Club:music",
        "Nobelhart & Schmutzig:dining",
    ],
    "San Francisco": [
        "SFJAZZ Center:music",
        "SFMOMA:arts",
        "City Lights Booksellers:literary",
        "Castro Theatre:cinema",
        "Smuggler's Cove:nightlife",
        "Tartine Bakery:dining",
    ],
}


def build_pydeck_map(plan: ItineraryPlan, hub_meta: Dict[str, Any]) -> pdk.Deck:
    """Builds a 3D PyDeck Deck with glowing Scatterplot markers and transit route PathLayer."""
    venues_data: List[Dict[str, Any]] = []
    path_coords: List[List[float]] = []

    for item in plan.items:
        entity = item.entity
        lon = float(entity.coordinates.longitude)
        lat = float(entity.coordinates.latitude)
        path_coords.append([lon, lat])

        domain_str = entity.domain.value if hasattr(entity.domain, "value") else str(entity.domain)
        slot_str = item.slot.value.title() if hasattr(item.slot, "value") else str(item.slot).title()

        venues_data.append({
            "name": entity.name,
            "lat": lat,
            "lon": lon,
            "domain": domain_str.upper(),
            "slot": f"Day {item.day} - {slot_str}",
            "time_window": item.time_window,
            "address": entity.address,
            "affinity": f"{int(item.affinity_score * 100)}%",
            "vibe": ", ".join(entity.tags[:3]),
        })

    # Glowing Cyan Scatterplot Layer
    scatterplot_layer = pdk.Layer(
        "ScatterplotLayer",
        data=venues_data,
        get_position=["lon", "lat"],
        get_color="[0, 240, 255, 230]",
        get_radius=220,
        pickable=True,
        auto_highlight=True,
        radius_min_pixels=6,
        radius_max_pixels=18,
    )

    # Violet Route Transit Path Layer
    path_layer = pdk.Layer(
        "PathLayer",
        data=[{"path": path_coords}],
        get_path="path",
        get_color="[138, 43, 226, 210]",
        width_scale=20,
        width_min_pixels=3,
        pickable=False,
    )

    view_state = pdk.ViewState(
        latitude=hub_meta.get("latitude", 12.9716),
        longitude=hub_meta.get("longitude", 77.5946),
        zoom=12.2,
        pitch=45,
        bearing=15,
    )

    return pdk.Deck(
        layers=[path_layer, scatterplot_layer],
        initial_view_state=view_state,
        tooltip={
            "html": """
            <div style="background-color: #151A23; border: 1px solid #00F0FF; padding: 10px; border-radius: 8px; color: #FFFFFF; font-family: sans-serif;">
                <b style="color: #00F0FF; font-size: 1.1em;">{name}</b><br/>
                <span style="color: #8A2BE2; font-weight: bold;">{domain}</span> | <span>{slot} ({time_window})</span><br/>
                <small style="color: #94A3B8;">{address}</small><br/>
                <span style="color: #10B981;">Affinity: {affinity}</span> | <i>{vibe}</i>
            </div>
            """,
            "style": {"color": "white"},
        },
        map_style="mapbox://styles/mapbox/dark-v10",
    )


def generate_plan(hub: str, seeds: List[TasteSeed], budget: str, tempo: str) -> ItineraryPlan:
    """Invokes the ReActPlanner asynchronously and returns a validated ItineraryPlan."""
    planner = ReActPlanner()
    return asyncio.run(
        planner.plan_48h(
            city_hub=hub,
            taste_seeds=seeds,
            budget=budget,
            tempo=tempo,
        )
    )


def main() -> None:
    """Streamlit application entry point."""
    st.set_page_config(
        page_title="CULTURA | Autonomous Cultural Intelligence Agent",
        page_icon="🧭",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Sidebar Controls
    # ------------------------------------------------------------------------
    with st.sidebar:
        st.markdown(
            "## 🧭 [CULTURA](https://github.com/)\n"
            "<small style='color:#00F0FF;'>Autonomous Cultural Intelligence & Taste Graph Agent</small>",
            unsafe_allow_html=True,
        )
        st.markdown("---")

        selected_hub = st.selectbox(
            "Cultural Capital",
            options=CULTURAL_HUBS,
            index=0,
            help="Choose destination premier cultural hub",
        )

        presets = PRESET_SEEDS_BY_HUB.get(selected_hub, PRESET_SEEDS_BY_HUB["Bangalore"])
        chosen_presets = st.multiselect(
            "Curated Taste Seeds",
            options=presets,
            default=presets[:2],
            help="Pre-indexed cultural anchors across dining, music, arts, and cinema",
        )

        custom_seed = st.text_input(
            "Custom Taste Anchor",
            placeholder="e.g. Coltrane:music or Pour-Over:dining",
            help="Add custom aesthetic preferences",
        )

        st.markdown("---")
        tempo = st.radio(
            "Itinerary Tempo",
            options=["Relaxed", "Moderate", "Intensive"],
            index=1,
            horizontal=True,
            help="Pacing between consecutive cultural stops",
        )

        budget = st.select_slider(
            "Budget Profile",
            options=["Low", "Medium", "High"],
            value="Medium",
            help="Culinary and venue tier preference",
        )

        st.markdown("---")
        generate_btn = st.button("✨ Generate 48-Hour Itinerary", type="primary", use_container_width=True)

    # Parse Seeds
    raw_seed_strings = list(chosen_presets)
    if custom_seed.strip():
        raw_seed_strings.append(custom_seed.strip())

    parsed_seeds: List[TasteSeed] = []
    for s_str in raw_seed_strings:
        s_clean = s_str.strip()
        if not s_clean:
            continue
        if ":" in s_clean:
            p = s_clean.split(":", 1)
            name_part = p[0].strip()
            domain_part = p[1].strip()
            if not name_part:
                continue
            try:
                dom = CulturalDomain.normalize(domain_part)
            except ValueError:
                dom = CulturalDomain.DINING
            try:
                parsed_seeds.append(TasteSeed(name=name_part, domain=dom, weight=1.0))
            except Exception:
                continue
        else:
            try:
                parsed_seeds.append(TasteSeed(name=s_clean, domain=CulturalDomain.DINING, weight=1.0))
            except Exception:
                continue

    if not parsed_seeds:
        parsed_seeds = [TasteSeed(name="Third Wave Coffee", domain=CulturalDomain.DINING, weight=1.0)]

    # Plan Generation or Session Retrieval
    if generate_btn or "current_plan" not in st.session_state or st.session_state.get("current_hub") != selected_hub:
        with st.spinner(f"Agent orchestrating ReAct loop across Qloo Taste Graph for {selected_hub}..."):
            plan = generate_plan(selected_hub, parsed_seeds, budget.lower(), tempo.lower())
            st.session_state["current_plan"] = plan
            st.session_state["current_hub"] = selected_hub
    else:
        plan = st.session_state["current_plan"]

    hub_meta = HUB_METADATA.get(selected_hub, HUB_METADATA["Bangalore"])

    # ------------------------------------------------------------------------
    # Main Dashboard Header
    # ------------------------------------------------------------------------
    st.markdown(
        f"""
        <div class="cultura-header">
            <h1 style="margin: 0 0 8px 0; font-size: 2.2rem; font-weight: 800;">
                <span class="cyan-accent">📍 {selected_hub}</span> — 48-Hour Cultural Blueprint
            </h1>
            <p style="margin: 0; color: #94A3B8; font-size: 1.05rem;">
                Autonomous Diurnal Curation Grounded in Qloo's Taste Graph | 
                <span style="color: #00F0FF;">{hub_meta.get('city', selected_hub)}, {hub_meta.get('country', '')}</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ------------------------------------------------------------------------
    # Top Diurnal Metrics Row
    # ------------------------------------------------------------------------
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Cultural Coherence</div>
                <div class="metric-value cyan-accent">{plan.cultural_coherence_score * 100:.1f}%</div>
                <div class="metric-desc">Qloo Taste Graph Synergy</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Shannon Diversity</div>
                <div class="metric-value violet-accent">{plan.domain_diversity_score * 100:.1f}%</div>
                <div class="metric-desc">Multi-Domain Entropy</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col3:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Transit Efficiency</div>
                <div class="metric-value green-accent">{plan.transit_efficiency_score * 100:.1f}%</div>
                <div class="metric-desc">Spatio-Temporal Optimization</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col4:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-title">Total Stops</div>
                <div class="metric-value gold-accent">{len(plan.items)} Venues</div>
                <div class="metric-desc">4 Diurnal Slots × 2 Days</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<br/>", unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Interactive PyDeck 3D Map
    # ------------------------------------------------------------------------
    st.markdown("### 🗺️ 3D Cultural Route & Venue Topology")
    deck = build_pydeck_map(plan, hub_meta)
    st.pydeck_chart(deck, use_container_width=True)

    st.markdown("<br/>", unsafe_allow_html=True)

    # ------------------------------------------------------------------------
    # Interactive Day-by-Day Diurnal Timeline
    # ------------------------------------------------------------------------
    st.markdown("### 🗓️ Curated 48-Hour Diurnal Schedule")
    tab_day1, tab_day2 = st.tabs(["☀️ Day 1: Diurnal Immersion", "🌙 Day 2: Subcultural Resonance"])

    for tab, day_num in [(tab_day1, 1), (tab_day2, 2)]:
        with tab:
            day_items = [it for it in plan.items if it.day == day_num]
            for item in day_items:
                slot_str = item.slot.value.title() if hasattr(item.slot, "value") else str(item.slot).title()
                entity = item.entity
                dom_str = entity.domain.value if hasattr(entity.domain, "value") else str(entity.domain)
                tag_class = f"tag-{dom_str.lower()}"
                transit_text = f"🚗 {item.transit_from_previous_min}m transit from prior" if item.transit_from_previous_min > 0 else "📍 Starting Point"

                with st.expander(f"{slot_str} ({item.time_window}): {entity.name} — {int(item.affinity_score * 100)}% match", expanded=True):
                    c_left, c_right = st.columns([3, 1])
                    with c_left:
                        st.markdown(
                            f"<span class='domain-tag {tag_class}'>{dom_str.upper()}</span> &nbsp; "
                            f"<small style='color:#94A3B8;'>{transit_text}</small><br/>"
                            f"<p style='margin-top:8px;'><b>Curator Notes:</b> {item.curator_notes or item.why_recommended}</p>"
                            f"<p><small style='color:#64748B;'><b>Why Qloo Matched:</b> {item.why_recommended}</small></p>"
                            f"<p style='color:#00F0FF;'><small>📍 {entity.address}</small></p>",
                            unsafe_allow_html=True,
                        )
                    with c_right:
                        st.markdown(
                            f"<div style='text-align:right;'>"
                            f"<b style='color:#10B981; font-size:1.3rem;'>{int(item.affinity_score * 100)}%</b><br/>"
                            f"<small style='color:#94A3B8;'>Affinity Match</small><br/><br/>"
                            f"<small style='color:#C084FC;'>{' • '.join(entity.tags[:3])}</small>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

    # ------------------------------------------------------------------------
    # Multi-Format One-Click Export Buttons
    # ------------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📥 Download Curated Itinerary")
    d1, d2, d3, d4 = st.columns(4)

    ics_data = export_ics(plan)
    md_data = export_markdown(plan)
    geojson_data = export_geojson(plan)
    json_data = export_json(plan)
    hub_slug = selected_hub.lower().replace(" ", "_")

    with d1:
        st.download_button(
            label="📅 Download iCalendar (.ics)",
            data=ics_data,
            file_name=f"{hub_slug}_itinerary.ics",
            mime="text/calendar",
            use_container_width=True,
        )
    with d2:
        st.download_button(
            label="📝 Download Markdown (.md)",
            data=md_data,
            file_name=f"{hub_slug}_itinerary.md",
            mime="text/markdown",
            use_container_width=True,
        )
    with d3:
        st.download_button(
            label="🗺️ Download GeoJSON (.geojson)",
            data=geojson_data,
            file_name=f"{hub_slug}_itinerary.geojson",
            mime="application/geo+json",
            use_container_width=True,
        )
    with d4:
        st.download_button(
            label="📦 Download JSON (.json)",
            data=json_data,
            file_name=f"{hub_slug}_itinerary.json",
            mime="application/json",
            use_container_width=True,
        )


if __name__ == "__main__" or (hasattr(st, "runtime") and st.runtime.exists()):
    main()
