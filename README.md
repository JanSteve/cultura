# CULTURA: Autonomous Cultural Intelligence & Taste Graph Agent

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-blue.svg)](pyproject.toml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Qloo Hackathon](https://img.shields.io/badge/Devpost-Qloo%20Agentic%20AI%20Hackathon-purple.svg)](https://qloo.devpost.com/)
[![Offline Mode](https://img.shields.io/badge/Mock%20Mode-100%25%20Offline%20Deterministic-success.svg)](src/cultura/client/mock_data.py)
[![Tests](https://img.shields.io/badge/Tests-200%2B%20Passing%20(100%25)-brightgreen.svg)](tests/)
[![Doctor SLA](https://img.shields.io/badge/Doctor%20SLA-%3C100ms%20(Verified%200.23ms)-orange.svg)](src/cultura/cli/main.py)

> **CULTURA** is an autonomous cultural intelligence and taste graph agent engineered for the **Qloo Agentic AI Hackathon** on Devpost. Powered by Qloo's cultural correlation entity graph (spanning 250M+ cultural entities across music, film, dining, arts, literature, nightlife, and fashion), CULTURA synthesizes bespoke 48-hour urban exploration itineraries grounded in deep cross-domain affinities and rigorous spatio-temporal transit constraints.

---

## 🏛️ Pitch & Vision: What is CULTURA?

Modern travel planners and generic LLMs suffer from two fatal failure modes:
1. **Hallucinatory "Top 10" Clichés:** They recommend generic tourist traps without cultural coherence or taste affinity.
2. **Geographical & Diurnal Incoherence:** They assemble schedules that zigzag across metropolitan traffic bottlenecks with zero awareness of transit dwell times or natural diurnal pacing.

**CULTURA transforms how discerning cultural travelers explore the world.** By bridging user taste seeds (e.g. *"A love for post-punk vinyl, third-wave natural process coffee, and brutalist architecture"*) through Qloo's multidimensional taste graph vectors, CULTURA discovers latent non-obvious cross-domain correlations. It knows why a fan of *Tame Impala* and *Interstellar* will resonate with an audiophile vinyl listening lounge in Tokyo, an avant-garde cinema club in Paris, or a heritage filter coffee institution in Bangalore.

### Core Capabilities:
- **7 Cultural Domains:** Seamless cross-domain affinity queries across **Dining**, **Music**, **Arts**, **Cinema**, **Nightlife**, **Literary**, and **Fashion**.
- **8 Premier Cultural Capitals:** Authentic, verified cultural grounding across **Bangalore**, **Mumbai**, **New York**, **London**, **Tokyo**, **Paris**, **Berlin**, and **San Francisco**.
- **100% Deterministic Offline Fallback:** Fully operational zero-credential mock catalog with 82 verified cultural anchors and an in-memory taste affinity engine (<1ms latency).
- **Autonomous ReAct Agent Loop:** 5-phase reasoning (`Thought` $\rightarrow$ `Action` $\rightarrow$ `Observation` $\rightarrow$ `Reflection` $\rightarrow$ `Synthesis`) with backtracking for spatio-temporal conflicts and domain anti-clumping.
- **Dual Interface:** Interactive Typer + Rich terminal CLI with ASCII timeline trees alongside a modern dark-mode Streamlit 3D PyDeck web dashboard.
- **Multi-Format Export Engine:** Direct export to RFC 5545 iCalendar (`.ics`), GitHub-flavored Markdown (`.md`), RFC 7946 GeoJSON (`.geojson`), and Pydantic JSON (`.json`).

---

## 🏗️ System Architecture

```
+--------------------------------------------------------------------------------------------------+
|                                    CULTURA SYSTEM ARCHITECTURE                                   |
+--------------------------------------------------------------------------------------------------+
|                                                                                                  |
|   +------------------------------------------------------------------------------------------+   |
|   |                              USER INPUT & TASTE SEEDS                                    |   |
|   |         Hub Selection (8 Global Hubs)  *  Freeform Taste Seeds  *  Budget & Tempo        |   |
|   +--------------------------------------------+---------------------------------------------+   |
|                                                |                                                 |
|                                                v                                                 |
|   +------------------------------------------------------------------------------------------+   |
|   |                          AUTONOMOUS ReAct AGENT PLANNER                                  |   |
|   |                                                                                          |   |
|   |      [ THOUGHT ]      Disambiguate taste seeds & determine diurnal constraints           |   |
|   |           |                                                                              |   |
|   |           v                                                                              |   |
|   |      [ ACTION ]       Query Qloo Taste Graph (Entity Search & Cross-Domain Affinity)     |   |
|   |           |                                                                              |   |
|   |           v                                                                              |   |
|   |     [ OBSERVATION ]   Receive candidate venues, affinity scores & coordinates            |   |
|   |           |                                                                              |   |
|   |           v                                                                              |   |
|   |      [ REFLECT ]      Evaluate Haversine transit (<45m), Shannon entropy, 0 duplicates   |   |
|   |           |                                                                              |   |
|   |           v                                                                              |   |
|   |     [ SYNTHESIS ]     Assemble 48-Hour 8-Slot Diurnal Progression Itinerary              |   |
|   +--------------------------------------------+---------------------------------------------+   |
|                                                |                                                 |
|                     +--------------------------+--------------------------+                      |
|                     |                                                     |                      |
|                     v                                                     v                      |
|   +------------------------------------+                +------------------------------------+   |
|   |     QLOO TASTE GRAPH CLIENT        |                |      IN-MEMORY MOCK CATALOG        |   |
|   |  - Live Async HTTPX REST Client    |                |  - 82 Curated Entities in 8 Hubs   |   |
|   |  - https://hackathon.api.qloo.com  |  <--Fallback-- |  - 7 Cultural Domains Coverage     |   |
|   |  - Transparent Offline Failover    |                |  - Deterministic Affinity Scoring  |   |
|   +------------------------------------+                +------------------------------------+   |
|                                                |                                                 |
|                                                v                                                 |
|   +------------------------------------------------------------------------------------------+   |
|   |                       PYDANTIC V2 VALIDATED ITINERARY PLAN                               |   |
|   |          48-Hour Invariants  *  8 Time Slots  *  No Venue Duplicates  *  Diurnal Pace    |   |
|   +-------------------+--------------------------------------------------+-------------------+   |
|                       |                                                  |                       |
|                       v                                                  v                       |
|   +----------------------------------------+     +-------------------------------------------+   |
|   |            DUAL INTERFACE              |     |           MULTI-FORMAT EXPORTERS          |   |
|   |                                        |     |                                           |   |
|   |  * Typer + Rich Terminal CLI           |     |  * RFC 5545 iCalendar (.ics)              |   |
|   |    - 'cultura doctor' (<100ms SLA)     |     |  * GitHub Flavored Markdown (.md)         |   |
|   |    - 'cultura plan' (ASCII Tree/Table) |     |  * RFC 7946 GeoJSON (.geojson)            |   |
|   |    - 'cultura hubs' & 'search'         |     |  * Pydantic Validated JSON (.json)        |   |
|   |                                        |     +-------------------------------------------+   |
|   |  * Streamlit Web Dashboard             |                                                     |
|   |    - Dark Mode UI                      |                                                     |
|   |    - PyDeck 3D Geographical Maps       |                                                     |
|   |    - Diurnal Timeline Cards & Metrics  |                                                     |
|   +----------------------------------------+                                                     |
|                                                                                                  |
+--------------------------------------------------------------------------------------------------+
```

---

## 🌍 8 Cultural Hubs & 7 Domains Coverage Matrix

CULTURA maps 82 authentic cultural venues across 8 global capitals, ensuring 100% coverage across all 7 cultural domains:

| Cultural Hub | Center Coordinates | Dining | Music | Arts | Cinema | Nightlife | Literary | Fashion | Total Venues |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :---: |
| **📍 Bangalore** | `12.9716° N, 77.5946° E` | Vidyarthi Bhavan, MTR | Windmills Craftworks, Fandom | NGMA, Bangalore Intl Centre | Suchitra Film Society | Pecos Classic Rock Pub | Blossom Book House | Cinnamon Concept Store | **10** |
| **📍 Mumbai** | `18.9220° N, 72.8347° E` | Britannia & Co., Bombay Canteen | NCPA, antiSOCIAL | Jehangir Gallery, Chemould Prescott | Regal Cinema, Matterden CNC | Toto's Garage Pub | Kitab Khana | Le Mill Colaba | **11** |
| **📍 New York** | `40.7128° N, -74.0060° W` | Via Carota, Katz's Deli | Village Vanguard, Bowery Ballroom | Whitney Museum | Film Forum, Metrograph | Bemelmans Bar | Strand Book Store | Dover Street Market | **10** |
| **📍 London** | `51.5074° N, -0.1278° W` | St. JOHN, Dishoom Shoreditch | Ronnie Scott's, Fabric | Tate Modern | BFI Southbank, Prince Charles | The French House | Daunt Books Marylebone | LN-CC | **10** |
| **📍 Tokyo** | `35.6762° N, 139.6503° E` | Afuri Harajuku, Omoide Yokocho | Lion Kissa, Pit Inn | Mori Art Museum, 21_21 DESIGN | Bunkamura Le Cinéma | Bar BenFiddich | Daikanyama T-Site | Comme des Garçons | **10** |
| **📍 Paris** | `48.8566° N, 2.3522° E` | Septime, Bouillon Chartier | Duc des Lombards, Rex Club | Pompidou, Palais de Tokyo | Le Champo, Cinémathèque | Le Syndicat | Shakespeare and Company | Merci Paris | **11** |
| **📍 Berlin** | `52.5200° N, 13.4050° E` | Nobelhart & Schmutzig, Mustafa's | Berghain, Pierre Boulez Saal | Boros Collection, KW Institute | Babylon Kino | Buck and Breck | Do You Read Me?! | VooStore Berlin | **10** |
| **📍 San Francisco** | `37.7749° N, -122.4194° W`| Zuni Café, Tartine Manufactory | SFJAZZ, The Fillmore | SFMOMA | Roxie Theater, Castro Theatre | Smuggler's Cove | City Lights Booksellers | Reliquary | **10** |
| **Total Catalog** | *Global & Indian Hubs* | **16 venues** | **16 venues** | **13 venues** | **13 venues** | **8 venues** | **8 venues** | **8 venues** | **82 venues** |

---

## ⚡ Quickstart Guide

### 1. Installation
CULTURA requires Python 3.10 or higher:
```bash
# Clone the repository
git clone https://github.com/JanSteve/cultura.git
cd cultura

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install clean dependencies and package in editable mode
pip install -r requirements.txt
pip install -e .
```

### 2. Environment Setup (Optional)
CULTURA is engineered with **zero required configuration** — it runs 100% offline out-of-the-box using its deterministic in-memory mock catalog. To connect to the live Qloo Hackathon REST API gateway:
```bash
cp .env.example .env
# Edit .env and paste your QLOO_API_KEY
```

### 3. Verify Health with Sub-100ms Doctor SLA
Run the integrated diagnostic suite:
```bash
cultura doctor
```
*Expected latency: ~0.2ms (well within the strict <100ms SLA).*

### 4. Synthesize a 48-Hour Cultural Itinerary
```bash
# Plan in Bangalore using authentic local seeds
cultura plan --hub Bangalore -s "Vidyarthi Bhavan:dining" -s "Windmills Craftworks:music"

# Multi-format exports (.ics, .md, .geojson, .json) to custom folder
cultura plan --hub Tokyo -s "Mori Art Museum:arts" -s "Bar BenFiddich:nightlife" -e ics -e md -e geojson -e json --output-dir ./plans
```

### 5. Launch the Streamlit 3D Web Dashboard
```bash
streamlit run src/cultura/web/app.py
```
Open your browser at `http://localhost:8501` to explore interactive taste badge pickers, 3D PyDeck arc routes, diurnal metric gauges, and visual timeline cards.

---

## 🖥️ CLI Reference & Examples

CULTURA provides a rich, responsive terminal CLI built with Typer and Rich.

### `cultura doctor`
Performs an instantaneous, 5-point environment and catalog audit:
```bash
$ cultura doctor
```
```
 ██████╗██╗   ██╗██╗  ████████╗██╗   ██╗██████╗  █████╗ 
██╔════╝██║   ██║██║  ╚══██╔══╝██║   ██║██╔══██╗██╔══██╗
██║     ██║   ██║██║     ██║   ██║   ██║██████╔╝███████║
██║     ██║   ██║██║     ██║   ██║   ██║██╔══██╗██╔══██║
╚██████╗╚██████╔╝███████╗██║   ╚██████╔╝██║  ██║██║  ██║
 Autonomous Cultural Intelligence Grounded in Qloo's Taste Graph

System & Taste Graph Diagnostics

╭───────────────────────────┬──────────────────────────┬─────────────┬─────────╮
│ Check / Component         │ Status                   │ Details     │ Latency │
├───────────────────────────┼──────────────────────────┼─────────────┼─────────┤
│ Python Runtime            │ ✓ Compatible             │ Python      │  0.00ms │
│                           │                          │ 3.11.5 (>=  │         │
│                           │                          │ 3.10)       │         │
│ Mock Catalog Integrity    │ ✓ Verified               │ 82 entities │  0.03ms │
│                           │                          │ across 8    │         │
│                           │                          │ hubs & 7    │         │
│                           │                          │ domains     │         │
│ Client Connectivity       │ ✓ Mock Mode Active       │ 100%        │  0.00ms │
│                           │                          │ Determinis… │         │
│                           │                          │ Offline     │         │
│                           │                          │ Fallback    │         │
│ System Time & Timezone    │ ✓ Synchronized           │ 2026-11-03  │  0.19ms │
│                           │                          │ UTC         │         │
│                           │                          │ (Aligned)   │         │
│ SLA Benchmark             │ ✓ 0.23ms                 │ Strict SLA: │  0.23ms │
│                           │                          │ <100ms      │         │
│                           │                          │ wall-clock  │         │
╰───────────────────────────┴──────────────────────────┴─────────────┴─────────╯
╭──────────────────────── CULTURA Health Check Summary ────────────────────────╮
│ System Health: ALL 4 CHECKS OPERATIONAL                                      │
│ Mock Catalog: 82 entities in 8 hubs | Python 3.11.5 | Mode: 100%             │
│ Deterministic Offline Fallback                                               │
│ Execution Time: 0.23ms (SLA <100ms: PASSED)                                  │
╰──────────────────────────────────────────────────────────────────────────────╯
```

### `cultura hubs`
Lists all supported cultural capitals with geographic center points and signature anchor venues:
```bash
$ cultura hubs
```
```
Premier Cultural Capitals & Grounded Hubs

╭────────────────────┬──────────────────────────┬────────────────┬───────────────────────────╮
│ Hub / Capital      │ Center Coordinates       │ Curated Stops  │ Signature Cultural Anchors│
├────────────────────┼──────────────────────────┼────────────────┼───────────────────────────┤
│ 📍 Bangalore       │ 12.9716° N, 77.5946° E   │ 10 venues      │ Vidyarthi Bhavan, MTR     │
│ 📍 Mumbai          │ 18.9220° N, 72.8347° E   │ 11 venues      │ Britannia & Co., NCPA     │
│ 📍 New York        │ 40.7128° N, -74.0060° E  │ 10 venues      │ Via Carota, Katz's Deli   │
│ 📍 London          │ 51.5074° N, -0.1278° E   │ 10 venues      │ St. JOHN, Ronnie Scott's  │
│ 📍 Tokyo           │ 35.6762° N, 139.6503° E  │ 10 venues      │ Afuri Harajuku, Kissa Lion│
│ 📍 Paris           │ 48.8566° N, 2.3522° E    │ 11 venues      │ Septime, Duc des Lombards │
│ 📍 Berlin          │ 52.5200° N, 13.4050° E   │ 10 venues      │ Nobelhart & Schmutzig     │
│ 📍 San Francisco   │ 37.7749° N, -122.4194° E │ 10 venues      │ Zuni Café, SFJAZZ Center  │
╰────────────────────┴──────────────────────────┴────────────────┴───────────────────────────╯
```

### `cultura search`
Searches cultural entities by keyword query and domain filter:
```bash
$ cultura search "Coffee" --domain dining
```
```
╭──────────────┬───────────────────────────┬────────────────┬──────────────────────────╮
│ Domain       │ Entity Name               │ Hub            │ Vibe Tags                │
├──────────────┼───────────────────────────┼────────────────┼──────────────────────────┤
│ DINING       │ Vidyarthi Bhavan          │ Bangalore      │ heritage, crisp-dosa,    │
│              │                           │                │ filter-coffee, nostalgic │
╰──────────────┴───────────────────────────┴────────────────┴──────────────────────────╯
```

### `cultura plan`
Synthesizes an autonomous, time-sequenced 48-hour itinerary complete with ASCII timeline trees and diurnal quality evaluation:
```bash
$ cultura plan --hub Bangalore -s "Vidyarthi Bhavan:dining" -e ics -e md --output-dir ./plans
```
```
📍 Bangalore 48-Hour Cultural Timeline
├── Day 1 — Diurnal Immersion & Cultural Anchors
│   ├── Morning (09:00 - 12:30): Vidyarthi Bhavan [DINING] (100% match) [Start Point]
│   ├── Afternoon (13:00 - 16:30): Bangalore International Centre [ARTS] (77% match) [19m transit]
│   ├── Evening (17:00 - 20:30): Mavalli Tiffin Room (MTR) [DINING] (69% match) [15m transit]
│   └── Night (21:00 - 00:30): Windmills Craftworks [MUSIC] (88% match) [38m transit]
└── Day 2 — Subcultural Resonance & Explorations
    ├── Morning (09:00 - 12:30): Blossom Book House [LITERARY] (78% match) [33m transit]
    ├── Afternoon (13:00 - 16:30): National Gallery of Modern Art [ARTS] (72% match) [6m transit]
    ├── Evening (17:00 - 20:30): Fandom at Gilly's Defined [MUSIC] (78% match) [18m transit]
    └── Night (21:00 - 00:30): Pecos Classic Rock Pub [NIGHTLIFE] (80% match) [11m transit]

                   CULTURA Itinerary Quality & Diurnal Scores                   
╭────────────────────────────────┬──────────────┬──────────────────────────────╮
│ Diurnal Metric                 │    Score     │ Evaluation                   │
├────────────────────────────────┼──────────────┼──────────────────────────────┤
│ Cultural Coherence             │    73.4%     │ High affinity grounding      │
│ Shannon Domain Diversity       │    81.8%     │ Multi-domain entropy coverage│
│ Transit Efficiency             │    90.9%     │ Optimal spatial transit      │
│ Overall Quality Score          │    81.2%     │ CULTURA Curation Index       │
╰────────────────────────────────┴──────────────┴──────────────────────────────╯
```

---

## 📦 Multi-Format Exporter Specifications

CULTURA provides multi-format export engines compliant with international data interchange standards:

### 1. RFC 5545 iCalendar (`.ics`)
- **Standard:** Internet Calendaring and Scheduling Core Object Specification (RFC 5545).
- **Features:** Generates discrete `VEVENT` entries for each of the 8 itinerary slots with precise start/end timestamps, geolocation coordinates (`GEO`), curator notes, domain categorization, and transit alerts.
- **Compatibility:** Native import into Apple Calendar, Google Calendar, Outlook, and mobile calendar apps.

### 2. GitHub-Flavored Markdown Travel Guide (`.md`)
- **Standard:** CommonMark + GFM extensions.
- **Features:** Rich typography featuring diurnal timeline headers, vibe badges, Google Maps navigation hyperlinks, domain classifications, curator justification notes, and an executive summary table with transit minutes.
- **Compatibility:** Direct rendering on GitHub, Notion, Obsidian, and static site generators.

### 3. RFC 7946 GeoJSON FeatureCollection (`.geojson`)
- **Standard:** The GeoJSON Format (RFC 7946).
- **Features:** Emits a `FeatureCollection` containing:
  - 8 `Point` features corresponding to venue stops with metadata properties (`name`, `day`, `slot`, `domain`, `affinity_score`, `tags`).
  - 1 `LineString` feature tracing the chronological route with distance properties for spatial transit visualization.
- **Compatibility:** Direct ingestion by QGIS, Mapbox, Deck.gl, Google Earth, and Leaflet.

### 4. Pydantic-Validated JSON (`.json`)
- **Standard:** Strict JSON Schema serialization via Pydantic V2.
- **Features:** Full lossless roundtrip serialization containing raw affinity scores, confidence intervals, coordinates, and diagnostic quality metrics.

---

## 🧪 Automated Test Suite & Verification

The project includes an exhaustive automated test suite with **over 200 tests passing at 100%**:

```bash
# Run the entire test suite
pytest -v
```

### Verification Highlights:
- **Packaging & Submission Kit (`tests/test_packaging.py`):** Asserts Apache 2.0 license integrity, PEP 518/621 `pyproject.toml` valid configuration, clean `requirements.txt`, `.env.example`, and comprehensive `README.md` attribution.
- **Sub-100ms Doctor SLA (`tests/test_adversarial_cli.py`):** Evaluates `cultura doctor` over 50 iterations; verifies zero memory leaks and wall-clock execution under 5ms (exceeding the 100ms requirement by 20x).
- **Autonomous ReAct Planning (`tests/test_agent_planner.py` & `tests/test_adversarial_planner.py`):** Verifies state machine transitions (`Thought` $\rightarrow$ `Action` $\rightarrow$ `Observation` $\rightarrow$ `Reflection` $\rightarrow$ `Synthesis`), Haversine transit bounds (<45m), zero duplicate venues, and Shannon entropy thresholding ($\ge 4$ domains).
- **Qloo API Client & Mock Engine (`tests/test_qloo_client.py` & `tests/test_adversarial_qloo.py`):** Verifies live HTTPX calls, network error failover, 100 concurrent async queries, and deterministic Jaccard affinity scoring.
- **Multi-Format Exporters (`tests/test_exporters.py` & `tests/test_adversarial_exporters.py`):** Verifies RFC 5545 timestamp syntax, RFC 7946 LineString coordinate geometries, Markdown table formatting, and JSON roundtrip fidelity across all 8 hubs.

---

## 🌐 Streamlit 3D Web Dashboard

Launch the visual dashboard:
```bash
streamlit run src/cultura/web/app.py
```

### Dashboard Highlights:
- **Dark Mode Aesthetic:** Custom CSS styling with neon accents and card layouts.
- **Interactive Taste Seed Badges:** Multi-select chips for quick selection across music, dining, cinema, and arts.
- **3D PyDeck Geographical Arc Map:** Interactive 3D globe visualization rendering animated transit arcs and venue scatter points with custom color coding per domain.
- **Diurnal Timeline Cards:** Chronological Day 1 & Day 2 cards detailing opening hours, transit buffers, match confidence bars, and curator notes.
- **Export Action Hub:** One-click downloads for `.ics`, `.md`, `.geojson`, and `.json`.

---

## 📄 Devpost Submission & Commercial Pitch

CULTURA was created for the **Qloo Agentic AI Hackathon** on Devpost. For complete commercial documentation and market analysis, refer to [`docs/QLOO_DEVPOST_SUBMISSION.md`](docs/QLOO_DEVPOST_SUBMISSION.md):
- **$1.9 Trillion Cultural Tourism Market Opportunity**
- **Commercialization Strategy & B2B API Licensing:** Tailored for boutique hotel brands (e.g. Ace Hotel, Soho House) and premium card concierges (e.g. Amex Centurion).
- **Jason Calacanis $25,000 Angel Investment Pitch:** Clear product-market fit, unit economics, and scalability roadmap.

---

## ⚖️ Author & Copyright Attribution

- **Project:** CULTURA: Autonomous Cultural Intelligence & Taste Graph Agent
- **Author:** **R Jan Steve Daniel** ([@JanSteve](https://github.com/JanSteve))
- **Repository:** [https://github.com/JanSteve/cultura](https://github.com/JanSteve/cultura)
- **License:** Apache License, Version 2.0
- **Copyright Notice:** `Copyright 2026 R Jan Steve Daniel`
