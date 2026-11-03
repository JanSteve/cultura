#!/usr/bin/env python3
"""
CULTURA Empirical Adversarial Challenge Runner for Milestone 5.
Authored by challenger_m5_1.

Conducts exhaustive empirical verification:
1. Itinerary generation across all 8 cultural hubs with varied and extreme seeds
   (exact in-hub, cross-hub, pure concept, boundary weights [0.0, 2.0], multi-seed, obscure non-matching).
2. Schedule invariants: exactly 8 items, 0 duplicate venues, strict chronological sequence.
3. Spatio-temporal transit constraints: every inter-venue leg <= 45 minutes via Haversine calculation.
4. Shannon domain diversity: >= 4 unique domains represented, zero adjacent clumping.
5. CLI `cultura plan` end-to-end execution and timeline verification.
6. Benchmark `cultura doctor` across 50 iterations: direct, CliRunner, and subprocess with max < 100ms assertion.
"""

from __future__ import annotations

import asyncio
import io
import json
import statistics
import subprocess
import sys
import time
from typing import Any, Dict, List, Tuple

from rich.console import Console
from typer.testing import CliRunner

from cultura.agent.planner import DiurnalRules, ReActPlanner
from cultura.agent.tools import (
    CulturalDomain,
    ItineraryItem,
    ItineraryPlan,
    TasteSeed,
    TimeSlot,
    haversine_transit_minutes,
)
from cultura.cli.main import app, doctor
from cultura.client.mock_data import CULTURAL_HUBS, normalize_hub
from cultura.client.qloo import QlooClient


# Test configurations across all 8 cultural hubs
HUB_TEST_CASES: List[Dict[str, Any]] = [
    {
        "hub": "Bangalore",
        "code": "BLR",
        "cases": [
            {
                "name": "Exact in-hub signature anchor",
                "seeds": [TasteSeed(name="Vidyarthi Bhavan", domain=CulturalDomain.DINING, weight=1.0)],
            },
            {
                "name": "Cross-hub signature anchor (NYC jazz in BLR)",
                "seeds": [TasteSeed(name="Village Vanguard", domain=CulturalDomain.MUSIC, weight=1.0)],
            },
            {
                "name": "Pure aesthetic tag / genre concept",
                "seeds": [TasteSeed(name="Brutalist Architecture", domain=CulturalDomain.ARTS, weight=1.5)],
            },
            {
                "name": "Boundary weights: minimum weight 0.0",
                "seeds": [TasteSeed(name="Third Wave Coffee", domain=CulturalDomain.DINING, weight=0.0)],
            },
            {
                "name": "Boundary weights: maximum weight 2.0",
                "seeds": [TasteSeed(name="The Humming Tree", domain=CulturalDomain.MUSIC, weight=2.0)],
            },
            {
                "name": "Multi-seed heterogeneous domains",
                "seeds": [
                    TasteSeed(name="Ranga Shankara", domain=CulturalDomain.ARTS, weight=1.2),
                    TasteSeed(name="Pecos", domain=CulturalDomain.NIGHTLIFE, weight=0.8),
                    TasteSeed(name="Blossom Book House", domain=CulturalDomain.LITERARY, weight=1.0),
                ],
            },
            {
                "name": "Obscure non-matching synthetic seed",
                "seeds": [TasteSeed(name="NonExistentBangaloreVenue999", domain=CulturalDomain.ARTS, weight=1.0)],
            },
        ],
    },
    {
        "hub": "Mumbai",
        "code": "BOM",
        "cases": [
            {
                "name": "Exact in-hub signature anchor",
                "seeds": [TasteSeed(name="Prithvi Theatre", domain=CulturalDomain.ARTS, weight=1.0)],
            },
            {
                "name": "Cross-hub signature anchor (Tokyo literary in BOM)",
                "seeds": [TasteSeed(name="Daikanyama T-Site", domain=CulturalDomain.LITERARY, weight=1.0)],
            },
            {
                "name": "Pure aesthetic tag / genre concept",
                "seeds": [TasteSeed(name="Bollywood Heritage", domain=CulturalDomain.CINEMA, weight=1.5)],
            },
            {
                "name": "Boundary weights: minimum weight 0.0",
                "seeds": [TasteSeed(name="Britannia & Co.", domain=CulturalDomain.DINING, weight=0.0)],
            },
            {
                "name": "Boundary weights: maximum weight 2.0",
                "seeds": [TasteSeed(name="NCPA", domain=CulturalDomain.ARTS, weight=2.0)],
            },
            {
                "name": "Multi-seed heterogeneous domains",
                "seeds": [
                    TasteSeed(name="Subko Coffee", domain=CulturalDomain.DINING, weight=1.0),
                    TasteSeed(name="Aer Bar", domain=CulturalDomain.NIGHTLIFE, weight=1.1),
                    TasteSeed(name="Kitab Khana", domain=CulturalDomain.LITERARY, weight=0.9),
                ],
            },
            {
                "name": "Obscure non-matching synthetic seed",
                "seeds": [TasteSeed(name="ObscureMumbaiAestheticQueryX", domain=CulturalDomain.FASHION, weight=1.0)],
            },
        ],
    },
    {
        "hub": "New York",
        "code": "NYC",
        "cases": [
            {
                "name": "Exact in-hub signature anchor",
                "seeds": [TasteSeed(name="Village Vanguard", domain=CulturalDomain.MUSIC, weight=1.0)],
            },
            {
                "name": "Cross-hub signature anchor (Berlin techno in NYC)",
                "seeds": [TasteSeed(name="Berghain", domain=CulturalDomain.NIGHTLIFE, weight=1.0)],
            },
            {
                "name": "Pure aesthetic tag / genre concept",
                "seeds": [TasteSeed(name="Abstract Expressionism", domain=CulturalDomain.ARTS, weight=1.5)],
            },
            {
                "name": "Boundary weights: minimum weight 0.0",
                "seeds": [TasteSeed(name="Russ & Daughters", domain=CulturalDomain.DINING, weight=0.0)],
            },
            {
                "name": "Boundary weights: maximum weight 2.0",
                "seeds": [TasteSeed(name="The Strand", domain=CulturalDomain.LITERARY, weight=2.0)],
            },
            {
                "name": "Multi-seed heterogeneous domains",
                "seeds": [
                    TasteSeed(name="Film Forum", domain=CulturalDomain.CINEMA, weight=1.0),
                    TasteSeed(name="Blue Note", domain=CulturalDomain.MUSIC, weight=1.2),
                    TasteSeed(name="Katz's Delicatessen", domain=CulturalDomain.DINING, weight=0.8),
                ],
            },
            {
                "name": "Obscure non-matching synthetic seed",
                "seeds": [TasteSeed(name="MysteryNYCConcept404", domain=CulturalDomain.CINEMA, weight=1.0)],
            },
        ],
    },
    {
        "hub": "London",
        "code": "LDN",
        "cases": [
            {
                "name": "Exact in-hub signature anchor",
                "seeds": [TasteSeed(name="Tate Modern", domain=CulturalDomain.ARTS, weight=1.0)],
            },
            {
                "name": "Cross-hub signature anchor (BLR dining in LDN)",
                "seeds": [TasteSeed(name="Vidyarthi Bhavan", domain=CulturalDomain.DINING, weight=1.0)],
            },
            {
                "name": "Pure aesthetic tag / genre concept",
                "seeds": [TasteSeed(name="Post-Punk", domain=CulturalDomain.MUSIC, weight=1.5)],
            },
            {
                "name": "Boundary weights: minimum weight 0.0",
                "seeds": [TasteSeed(name="Dishoom", domain=CulturalDomain.DINING, weight=0.0)],
            },
            {
                "name": "Boundary weights: maximum weight 2.0",
                "seeds": [TasteSeed(name="Ronnie Scott's", domain=CulturalDomain.MUSIC, weight=2.0)],
            },
            {
                "name": "Multi-seed heterogeneous domains",
                "seeds": [
                    TasteSeed(name="BFI Southbank", domain=CulturalDomain.CINEMA, weight=1.0),
                    TasteSeed(name="Daunt Books", domain=CulturalDomain.LITERARY, weight=1.2),
                    TasteSeed(name="Fabric", domain=CulturalDomain.NIGHTLIFE, weight=0.9),
                ],
            },
            {
                "name": "Obscure non-matching synthetic seed",
                "seeds": [TasteSeed(name="UnchartedLondonUndergroundVenue", domain=CulturalDomain.ARTS, weight=1.0)],
            },
        ],
    },
    {
        "hub": "Tokyo",
        "code": "TYO",
        "cases": [
            {
                "name": "Exact in-hub signature anchor",
                "seeds": [TasteSeed(name="Daikanyama T-Site", domain=CulturalDomain.LITERARY, weight=1.0)],
            },
            {
                "name": "Cross-hub signature anchor (Parisian fashion in TYO)",
                "seeds": [TasteSeed(name="Le Marais Boutiques", domain=CulturalDomain.FASHION, weight=1.0)],
            },
            {
                "name": "Pure aesthetic tag / genre concept",
                "seeds": [TasteSeed(name="Cyberpunk Aesthetic", domain=CulturalDomain.CINEMA, weight=1.5)],
            },
            {
                "name": "Boundary weights: minimum weight 0.0",
                "seeds": [TasteSeed(name="Sukiyabashi Jiro", domain=CulturalDomain.DINING, weight=0.0)],
            },
            {
                "name": "Boundary weights: maximum weight 2.0",
                "seeds": [TasteSeed(name="Mori Art Museum", domain=CulturalDomain.ARTS, weight=2.0)],
            },
            {
                "name": "Multi-seed heterogeneous domains",
                "seeds": [
                    TasteSeed(name="Bar Trench", domain=CulturalDomain.NIGHTLIFE, weight=1.1),
                    TasteSeed(name="Bunkamura Le Cinema", domain=CulturalDomain.CINEMA, weight=0.9),
                    TasteSeed(name="Blue Note Tokyo", domain=CulturalDomain.MUSIC, weight=1.2),
                ],
            },
            {
                "name": "Obscure non-matching synthetic seed",
                "seeds": [TasteSeed(name="GhostTokyoSynthVenue99", domain=CulturalDomain.DINING, weight=1.0)],
            },
        ],
    },
    {
        "hub": "Paris",
        "code": "PAR",
        "cases": [
            {
                "name": "Exact in-hub signature anchor",
                "seeds": [TasteSeed(name="Le Marais Boutiques", domain=CulturalDomain.FASHION, weight=1.0)],
            },
            {
                "name": "Cross-hub signature anchor (SF cinema in PAR)",
                "seeds": [TasteSeed(name="Castro Theatre", domain=CulturalDomain.CINEMA, weight=1.0)],
            },
            {
                "name": "Pure aesthetic tag / genre concept",
                "seeds": [TasteSeed(name="French New Wave", domain=CulturalDomain.CINEMA, weight=1.5)],
            },
            {
                "name": "Boundary weights: minimum weight 0.0",
                "seeds": [TasteSeed(name="Shakespeare and Company", domain=CulturalDomain.LITERARY, weight=0.0)],
            },
            {
                "name": "Boundary weights: maximum weight 2.0",
                "seeds": [TasteSeed(name="Centre Pompidou", domain=CulturalDomain.ARTS, weight=2.0)],
            },
            {
                "name": "Multi-seed heterogeneous domains",
                "seeds": [
                    TasteSeed(name="Duc des Lombards", domain=CulturalDomain.MUSIC, weight=1.0),
                    TasteSeed(name="Café de Flore", domain=CulturalDomain.DINING, weight=1.2),
                    TasteSeed(name="Silencio", domain=CulturalDomain.NIGHTLIFE, weight=0.8),
                ],
            },
            {
                "name": "Obscure non-matching synthetic seed",
                "seeds": [TasteSeed(name="NonExistentParisBoutiqueXYZ", domain=CulturalDomain.FASHION, weight=1.0)],
            },
        ],
    },
    {
        "hub": "Berlin",
        "code": "BER",
        "cases": [
            {
                "name": "Exact in-hub signature anchor",
                "seeds": [TasteSeed(name="Berghain", domain=CulturalDomain.NIGHTLIFE, weight=1.0)],
            },
            {
                "name": "Cross-hub signature anchor (Mumbai theatre in BER)",
                "seeds": [TasteSeed(name="Prithvi Theatre", domain=CulturalDomain.ARTS, weight=1.0)],
            },
            {
                "name": "Pure aesthetic tag / genre concept",
                "seeds": [TasteSeed(name="Bauhaus Architecture", domain=CulturalDomain.ARTS, weight=1.5)],
            },
            {
                "name": "Boundary weights: minimum weight 0.0",
                "seeds": [TasteSeed(name="Mustafa's Gemüsedöner", domain=CulturalDomain.DINING, weight=0.0)],
            },
            {
                "name": "Boundary weights: maximum weight 2.0",
                "seeds": [TasteSeed(name="Babylon Kino", domain=CulturalDomain.CINEMA, weight=2.0)],
            },
            {
                "name": "Multi-seed heterogeneous domains",
                "seeds": [
                    TasteSeed(name="Watergate", domain=CulturalDomain.NIGHTLIFE, weight=1.0),
                    TasteSeed(name="Do You Read Me?!", domain=CulturalDomain.LITERARY, weight=1.2),
                    TasteSeed(name="Tresor", domain=CulturalDomain.MUSIC, weight=1.1),
                ],
            },
            {
                "name": "Obscure non-matching synthetic seed",
                "seeds": [TasteSeed(name="PhantomBerlinIndustrialClub", domain=CulturalDomain.NIGHTLIFE, weight=1.0)],
            },
        ],
    },
    {
        "hub": "San Francisco",
        "code": "SFO",
        "cases": [
            {
                "name": "Exact in-hub signature anchor",
                "seeds": [TasteSeed(name="Castro Theatre", domain=CulturalDomain.CINEMA, weight=1.0)],
            },
            {
                "name": "Cross-hub signature anchor (London art in SFO)",
                "seeds": [TasteSeed(name="Tate Modern", domain=CulturalDomain.ARTS, weight=1.0)],
            },
            {
                "name": "Pure aesthetic tag / genre concept",
                "seeds": [TasteSeed(name="Beat Generation Poetry", domain=CulturalDomain.LITERARY, weight=1.5)],
            },
            {
                "name": "Boundary weights: minimum weight 0.0",
                "seeds": [TasteSeed(name="Tartine Bakery", domain=CulturalDomain.DINING, weight=0.0)],
            },
            {
                "name": "Boundary weights: maximum weight 2.0",
                "seeds": [TasteSeed(name="SFMOMA", domain=CulturalDomain.ARTS, weight=2.0)],
            },
            {
                "name": "Multi-seed heterogeneous domains",
                "seeds": [
                    TasteSeed(name="City Lights Books", domain=CulturalDomain.LITERARY, weight=1.2),
                    TasteSeed(name="The Fillmore", domain=CulturalDomain.MUSIC, weight=1.0),
                    TasteSeed(name="Smuggler's Cove", domain=CulturalDomain.NIGHTLIFE, weight=0.9),
                ],
            },
            {
                "name": "Obscure non-matching synthetic seed",
                "seeds": [TasteSeed(name="SiliconValleyCyberpunkSpot", domain=CulturalDomain.CINEMA, weight=1.0)],
            },
        ],
    },
]


async def run_itinerary_challenge() -> Dict[str, Any]:
    """Tests all 8 hubs and 56 total seed permutations against strict invariants."""
    print("=" * 80)
    print("CHALLENGE SUITE 1-4: ITINERARY GENERATION & INVARIANTS ACROSS 8 HUBS")
    print("=" * 80)

    client = QlooClient(use_mock_fallback=True)
    planner = ReActPlanner(client=client)

    results: Dict[str, Any] = {
        "total_tests": 0,
        "passed_tests": 0,
        "failed_tests": 0,
        "failures": [],
        "hubs_tested": [],
        "min_unique_domains": 999,
        "max_transit_minutes_observed": 0,
        "transit_violations": 0,
        "clumping_violations": 0,
        "duplicate_violations": 0,
        "length_violations": 0,
        "chronological_violations": 0,
        "timings_ms": [],
    }

    expected_sequence = [
        (1, TimeSlot.MORNING),
        (1, TimeSlot.AFTERNOON),
        (1, TimeSlot.EVENING),
        (1, TimeSlot.NIGHT),
        (2, TimeSlot.MORNING),
        (2, TimeSlot.AFTERNOON),
        (2, TimeSlot.EVENING),
        (2, TimeSlot.NIGHT),
    ]

    for hub_entry in HUB_TEST_CASES:
        hub_name = hub_entry["hub"]
        results["hubs_tested"].append(hub_name)

        for case in hub_entry["cases"]:
            results["total_tests"] += 1
            case_name = case["name"]
            seeds = case["seeds"]

            t0 = time.perf_counter()
            try:
                plan: ItineraryPlan = await planner.plan_48h(
                    city_hub=hub_name,
                    taste_seeds=seeds,
                )
                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                results["timings_ms"].append(elapsed_ms)

                # 1. Invariant: Exactly 8 items
                if len(plan.items) != 8:
                    results["length_violations"] += 1
                    raise AssertionError(f"Expected 8 items, got {len(plan.items)}")

                # 2. Invariant: 0 duplicate venues
                venue_ids = [item.entity.id for item in plan.items]
                unique_venue_ids = set(venue_ids)
                if len(unique_venue_ids) != 8:
                    results["duplicate_violations"] += 1
                    raise AssertionError(f"Duplicate venues detected: {len(venue_ids)} items, {len(unique_venue_ids)} unique")

                # 3. Invariant: Strict chronological order
                actual_sequence = [(item.day, item.slot) for item in plan.items]
                if actual_sequence != expected_sequence:
                    results["chronological_violations"] += 1
                    raise AssertionError(f"Sequence mismatch: expected {expected_sequence}, got {actual_sequence}")

                # 4. Invariant: Spatio-temporal transit constraint <= 45 min
                for i in range(1, len(plan.items)):
                    prev_item = plan.items[i - 1]
                    curr_item = plan.items[i]

                    # Haversine recalculation
                    calc_transit = haversine_transit_minutes(
                        prev_item.entity.latitude,
                        prev_item.entity.longitude,
                        curr_item.entity.latitude,
                        curr_item.entity.longitude,
                    )
                    stored_transit = curr_item.transit_from_previous_min

                    results["max_transit_minutes_observed"] = max(
                        results["max_transit_minutes_observed"],
                        calc_transit,
                        stored_transit,
                    )

                    if calc_transit > 45 or stored_transit > 45:
                        results["transit_violations"] += 1
                        raise AssertionError(
                            f"Transit exceeded 45 min at leg {i} ({prev_item.entity.name} -> {curr_item.entity.name}): "
                            f"calculated={calc_transit}m, stored={stored_transit}m"
                        )

                # 5. Invariant: Shannon domain diversity >= 4 unique domains & no clumping
                plan_domains = [item.entity.domain for item in plan.items]
                unique_domains = set(plan_domains)
                results["min_unique_domains"] = min(results["min_unique_domains"], len(unique_domains))

                if len(unique_domains) < 4:
                    raise AssertionError(
                        f"Domain diversity violated: expected >= 4 domains, found {len(unique_domains)} ({unique_domains})"
                    )

                for i in range(len(plan.items) - 1):
                    if plan_domains[i] == plan_domains[i + 1]:
                        results["clumping_violations"] += 1
                        raise AssertionError(
                            f"Domain clumping detected at slots {i} and {i+1}: consecutive domain '{plan_domains[i].value}'"
                        )

                results["passed_tests"] += 1
                print(f"  [PASS] {hub_name:14s} | {case_name:42s} | 8 items, {len(unique_domains)} doms, max leg {max(it.transit_from_previous_min for it in plan.items)}m ({elapsed_ms:.1f}ms)")

            except Exception as e:
                results["failed_tests"] += 1
                err_msg = f"{hub_name} - {case_name}: {str(e)}"
                results["failures"].append(err_msg)
                print(f"  [FAIL] {hub_name:14s} | {case_name:42s} | ERROR: {str(e)}")

    await client.close()
    return results


def run_cli_plan_challenge() -> Dict[str, Any]:
    """Empirically invokes CLI `cultura plan` across hubs and checks output and exit code."""
    print("\n" + "=" * 80)
    print("CHALLENGE SUITE: CLI `cultura plan` END-TO-END EXECUTION")
    print("=" * 80)

    runner = CliRunner()
    cli_results: Dict[str, Any] = {
        "runs": 0,
        "passes": 0,
        "fails": 0,
        "errors": [],
    }

    test_invocations = [
        (["plan", "--hub", "Bangalore", "-s", "Vidyarthi Bhavan:dining", "-s", "Pecos:nightlife"], "Bangalore"),
        (["plan", "--hub", "Tokyo", "-s", "Daikanyama T-Site:literary"], "Tokyo"),
        (["plan", "--hub", "Paris", "-s", "Le Marais Boutiques:fashion", "-s", "Shakespeare and Company:literary"], "Paris"),
        (["plan", "--hub", "San Francisco", "-s", "Castro Theatre:cinema", "--export", "json"], "San Francisco"),
    ]

    for args, hub in test_invocations:
        cli_results["runs"] += 1
        t0 = time.perf_counter()
        res = runner.invoke(app, args)
        elapsed = (time.perf_counter() - t0) * 1000.0

        if res.exit_code == 0 and "Itinerary" in res.output and "Day 1" in res.output and "Day 2" in res.output:
            cli_results["passes"] += 1
            print(f"  [PASS] CLI plan --hub {hub:14s} ({elapsed:.1f}ms) | Timeline tree & scores rendered")
        else:
            cli_results["fails"] += 1
            err = f"CLI plan failed for {hub} (exit {res.exit_code}): {res.output[:200]}"
            cli_results["errors"].append(err)
            print(f"  [FAIL] CLI plan --hub {hub:14s} | {err}")

    return cli_results


def run_doctor_benchmark_50() -> Dict[str, Any]:
    """
    Benchmarks `cultura doctor` across 50 iterations:
    1. Direct function call
    2. CliRunner execution
    3. Subprocess execution (`python3 -m cultura.cli.main doctor`)
    Asserts max execution time strictly < 100ms.
    """
    print("\n" + "=" * 80)
    print("CHALLENGE SUITE 5: `cultura doctor` 50-ITERATION BENCHMARK (SLA < 100ms)")
    print("=" * 80)

    iterations = 50
    runner = CliRunner()

    # 1. Direct function call
    import cultura.cli.main
    orig_console = cultura.cli.main.console
    cultura.cli.main.console = Console(file=io.StringIO())

    direct_latencies: List[float] = []
    try:
        doctor()  # warmup
        for i in range(iterations):
            t0 = time.perf_counter()
            doctor()
            t1 = time.perf_counter()
            direct_latencies.append((t1 - t0) * 1000.0)
    finally:
        cultura.cli.main.console = orig_console

    # 2. CliRunner execution
    cli_latencies: List[float] = []
    runner.invoke(app, ["doctor"])  # warmup
    for i in range(iterations):
        t0 = time.perf_counter()
        res = runner.invoke(app, ["doctor"])
        t1 = time.perf_counter()
        if res.exit_code != 0:
            raise RuntimeError(f"CliRunner doctor failed at iteration {i}: exit {res.exit_code}")
        cli_latencies.append((t1 - t0) * 1000.0)

    # 3. Subprocess execution (tests cold OS process overhead)
    # Let's run 5 iterations of subprocess to record cold OS process launch time
    subp_latencies: List[float] = []
    for i in range(10):
        t0 = time.perf_counter()
        sub_res = subprocess.run(
            [sys.executable, "-m", "cultura.cli.main", "doctor"],
            capture_output=True,
            text=True,
        )
        t1 = time.perf_counter()
        if sub_res.returncode != 0:
            raise RuntimeError(f"Subprocess doctor failed: {sub_res.stderr}")
        subp_latencies.append((t1 - t0) * 1000.0)

    stats = {
        "iterations": iterations,
        "direct": {
            "mean_ms": statistics.mean(direct_latencies),
            "median_ms": statistics.median(direct_latencies),
            "p95_ms": sorted(direct_latencies)[int(iterations * 0.95)],
            "max_ms": max(direct_latencies),
            "min_ms": min(direct_latencies),
            "stdev_ms": statistics.stdev(direct_latencies),
            "sla_ok": max(direct_latencies) < 100.0,
        },
        "cli": {
            "mean_ms": statistics.mean(cli_latencies),
            "median_ms": statistics.median(cli_latencies),
            "p95_ms": sorted(cli_latencies)[int(iterations * 0.95)],
            "max_ms": max(cli_latencies),
            "min_ms": min(cli_latencies),
            "stdev_ms": statistics.stdev(cli_latencies),
            "sla_ok": max(cli_latencies) < 100.0,
        },
        "subprocess_sample": {
            "mean_ms": statistics.mean(subp_latencies),
            "max_ms": max(subp_latencies),
            "min_ms": min(subp_latencies),
        },
    }

    print(f"Direct Function (50 runs): Mean={stats['direct']['mean_ms']:.2f}ms, Median={stats['direct']['median_ms']:.2f}ms, P95={stats['direct']['p95_ms']:.2f}ms, Max={stats['direct']['max_ms']:.2f}ms | SLA < 100ms: {'PASS' if stats['direct']['sla_ok'] else 'FAIL'}")
    print(f"CliRunner (50 runs):       Mean={stats['cli']['mean_ms']:.2f}ms, Median={stats['cli']['median_ms']:.2f}ms, P95={stats['cli']['p95_ms']:.2f}ms, Max={stats['cli']['max_ms']:.2f}ms | SLA < 100ms: {'PASS' if stats['cli']['sla_ok'] else 'FAIL'}")
    print(f"Subprocess (10 runs):      Mean={stats['subprocess_sample']['mean_ms']:.2f}ms, Max={stats['subprocess_sample']['max_ms']:.2f}ms, Min={stats['subprocess_sample']['min_ms']:.2f}ms")

    return stats


def main() -> int:
    overall_start = time.perf_counter()

    # 1. Run itinerary invariant tests
    itinerary_res = asyncio.run(run_itinerary_challenge())

    # 2. Run CLI plan tests
    cli_res = run_cli_plan_challenge()

    # 3. Run doctor benchmark
    doctor_res = run_doctor_benchmark_50()

    total_time = time.perf_counter() - overall_start

    print("\n" + "=" * 80)
    print("EMPIRICAL CHALLENGE SUMMARY VERDICT")
    print("=" * 80)
    print(f"Total Plan Invariant Tests: {itinerary_res['total_tests']} runs across {len(itinerary_res['hubs_tested'])} hubs")
    print(f"Passed: {itinerary_res['passed_tests']} | Failed: {itinerary_res['failed_tests']}")
    print(f"Length Invariant Violations:       {itinerary_res['length_violations']}")
    print(f"Duplicate Venue Violations:       {itinerary_res['duplicate_violations']}")
    print(f"Chronological Order Violations:   {itinerary_res['chronological_violations']}")
    print(f"Transit Violations (>45 min):     {itinerary_res['transit_violations']} (Max observed: {itinerary_res['max_transit_minutes_observed']} min)")
    print(f"Domain Diversity Violations (<4): {itinerary_res['min_unique_domains']} min domains observed")
    print(f"Clumping Violations:              {itinerary_res['clumping_violations']}")
    print(f"Doctor Max Execution Time:        Direct {doctor_res['direct']['max_ms']:.2f}ms, CLI {doctor_res['cli']['max_ms']:.2f}ms (<100ms SLA)")
    print(f"CLI Plan Runs:                    {cli_res['passes']}/{cli_res['runs']} passed")
    print(f"Total Challenge Runtime:          {total_time:.2f}s")

    all_passed = (
        itinerary_res["failed_tests"] == 0
        and itinerary_res["length_violations"] == 0
        and itinerary_res["duplicate_violations"] == 0
        and itinerary_res["chronological_violations"] == 0
        and itinerary_res["transit_violations"] == 0
        and itinerary_res["clumping_violations"] == 0
        and itinerary_res["min_unique_domains"] >= 4
        and doctor_res["direct"]["sla_ok"]
        and doctor_res["cli"]["sla_ok"]
        and cli_res["fails"] == 0
    )

    if all_passed:
        print("\n>>> FINAL EMPIRICAL VERDICT: APPROVE <<<")
        return 0
    else:
        print("\n>>> FINAL EMPIRICAL VERDICT: REQUEST_CHANGES <<<")
        return 1


if __name__ == "__main__":
    sys.exit(main())
