"""
Adversarial Stress Test Suite for Milestone 3 (CLI & Doctor SLA).
Empirically stress-tests:
1. Doctor SLA latency under repeated execution (50 runs): direct call and CliRunner.
   Strict thresholds: max latency < 100ms, mean latency < 10ms.
2. CLI Robustness & Error Handling:
   - Non-existent hub ("Atlantis")
   - Empty seeds (no seeds passed)
   - Special characters and formatting in seeds ("Special & Unusual:music", "::dining", ":", whitespace)
   - Deeply nested non-existent export directory auto-creation
   - Invalid export formats and search options

Copyright 2026 R Jan Steve Daniel. Licensed under Apache-2.0.
"""

from __future__ import annotations

import io
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List

import pytest
from rich.console import Console
from typer.testing import CliRunner

import cultura.cli.main
from cultura.cli.main import app, doctor


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ============================================================================
# 1. Doctor SLA Stress Tests (50 Iterations)
# ============================================================================

def test_doctor_sla_direct_call_50_iterations() -> None:
    """
    Stress-tests direct doctor() function execution across 50 iterations.
    Asserts strict SLA:
    - Mean latency < 10.0 ms
    - Max latency < 100.0 ms
    """
    # Mute console during latency benchmark to avoid I/O skew
    original_console = cultura.cli.main.console
    cultura.cli.main.console = Console(file=io.StringIO())

    latencies: List[float] = []
    try:
        # Warmup
        doctor()
        for _ in range(50):
            t0 = time.perf_counter()
            doctor()
            t1 = time.perf_counter()
            latencies.append((t1 - t0) * 1000.0)
    finally:
        cultura.cli.main.console = original_console

    mean_lat = sum(latencies) / len(latencies)
    max_lat = max(latencies)
    min_lat = min(latencies)

    print(
        f"\n[Doctor SLA Direct Function] 50 runs -> Mean: {mean_lat:.3f}ms | Max: {max_lat:.3f}ms | Min: {min_lat:.3f}ms"
    )

    assert max_lat < 100.0, f"Doctor SLA Max Latency exceeded: {max_lat:.2f}ms >= 100ms"
    assert mean_lat < 10.0, f"Doctor SLA Mean Latency exceeded: {mean_lat:.2f}ms >= 10ms"


def test_doctor_sla_clirunner_50_iterations(runner: CliRunner) -> None:
    """
    Stress-tests doctor CLI invocation via CliRunner across 50 iterations.
    Asserts strict SLA:
    - Mean latency < 10.0 ms
    - Max latency < 100.0 ms
    - All exit codes == 0
    """
    latencies: List[float] = []
    # Warmup
    runner.invoke(app, ["doctor"])
    for _ in range(50):
        t0 = time.perf_counter()
        result = runner.invoke(app, ["doctor"])
        t1 = time.perf_counter()
        assert result.exit_code == 0
        latencies.append((t1 - t0) * 1000.0)

    mean_lat = sum(latencies) / len(latencies)
    max_lat = max(latencies)
    min_lat = min(latencies)

    print(
        f"\n[Doctor SLA CliRunner] 50 runs -> Mean: {mean_lat:.3f}ms | Max: {max_lat:.3f}ms | Min: {min_lat:.3f}ms"
    )

    assert max_lat < 100.0, f"Doctor SLA Max Latency exceeded: {max_lat:.2f}ms >= 100ms"
    assert mean_lat < 10.0, f"Doctor SLA Mean Latency exceeded: {mean_lat:.2f}ms >= 10ms"


# ============================================================================
# 2. CLI Robustness & Error Handling: Hub and Seed Edge Cases
# ============================================================================

def test_plan_nonexistent_hub_adversarial(runner: CliRunner) -> None:
    """
    Adversarial Challenge: Non-existent hub `cultura plan --hub Atlantis`.
    Must return clean error message and exit code 1 or 2 with NO unhandled tracebacks.
    """
    result = runner.invoke(app, ["plan", "--hub", "Atlantis", "-s", "Jazz:music"])
    assert result.exit_code in (1, 2)
    assert "Unsupported cultural hub" in result.output
    assert "Traceback (most recent call last)" not in result.output


def test_plan_case_insensitive_hub_adversarial(runner: CliRunner) -> None:
    """
    Adversarial Challenge: Hub name with erratic casing e.g. 'bAnGaLoRe'.
    Should be recognized cleanly through canonical hub mapping.
    """
    result = runner.invoke(app, ["plan", "--hub", "bAnGaLoRe", "-s", "Coffee:dining"])
    assert result.exit_code == 0
    assert "Bangalore" in result.output
    assert "Cultural Coherence" in result.output


def test_plan_empty_seeds_adversarial(runner: CliRunner) -> None:
    """
    Adversarial Challenge: Empty seeds `cultura plan --hub Bangalore` (no seeds).
    Must return clean error message and exit code 1 or 2 with NO unhandled tracebacks.
    """
    result = runner.invoke(app, ["plan", "--hub", "Bangalore"])
    assert result.exit_code in (1, 2)
    assert "seed" in result.output.lower()
    assert "Traceback (most recent call last)" not in result.output


def test_plan_special_characters_in_seeds(runner: CliRunner) -> None:
    """
    Adversarial Challenge: Seeds with ampersands, punctuation, and mixed formats:
    -s "Special & Unusual:music"
    """
    result = runner.invoke(
        app, ["plan", "--hub", "Bangalore", "-s", "Special & Unusual:music"]
    )
    assert result.exit_code == 0
    assert "Special & Unusual" in result.output
    assert "MUSIC" in result.output
    assert "Day 1" in result.output


def test_plan_unicode_and_emojis_in_seeds(runner: CliRunner) -> None:
    """
    Adversarial Challenge: Seeds with unicode characters or emojis:
    -s "Third Wave ☕:dining"
    """
    result = runner.invoke(
        app, ["plan", "--hub", "Bangalore", "-s", "Third Wave ☕:dining"]
    )
    assert result.exit_code == 0
    assert "Third Wave ☕" in result.output
    assert "Day 1" in result.output


def test_plan_nested_nonexistent_export_dir(runner: CliRunner, tmp_path: Path) -> None:
    """
    Adversarial Challenge: Exporting to a non-existent deeply nested directory.
    Verifies automatic directory creation without FileNotFoundError or tracebacks.
    """
    deep_dir = tmp_path / "deep" / "nested" / "sub" / "output_dir"
    assert not deep_dir.exists()

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
            str(deep_dir),
        ],
    )
    assert result.exit_code == 0
    assert deep_dir.exists()
    assert (deep_dir / "bangalore_itinerary.json").exists()
    assert (deep_dir / "bangalore_itinerary.md").exists()
    assert "Traceback (most recent call last)" not in result.output


def test_plan_empty_and_whitespace_only_seed_handling(runner: CliRunner) -> None:
    """
    Adversarial Challenge: Seed strings that are empty or whitespace only:
    -s "" or -s "   "
    Should cleanly fail validation without unhandled tracebacks.
    """
    result_empty = runner.invoke(app, ["plan", "--hub", "Bangalore", "-s", ""])
    assert result_empty.exit_code in (1, 2)
    assert "Traceback (most recent call last)" not in result_empty.output

    result_ws = runner.invoke(app, ["plan", "--hub", "Bangalore", "-s", "   "])
    assert result_ws.exit_code in (1, 2)
    assert "Traceback (most recent call last)" not in result_ws.output


def test_plan_malformed_seed_colon_adversarial(runner: CliRunner) -> None:
    """
    Adversarial Challenge: Malformed seed with colon delimiter and empty name:
    e.g. -s "::dining" or -s ":" or -s ":music"
    Verifies clean error handling without unhandled tracebacks or uncaught exceptions.
    """
    for bad_seed in ["::dining", ":", ":music"]:
        proc = subprocess.run(
            [sys.executable, "-m", "cultura.cli.main", "plan", "--hub", "Bangalore", "-s", bad_seed],
            capture_output=True,
            text=True,
        )
        has_traceback = (
            "Traceback (most recent call last)" in proc.stderr
            or "Traceback (most recent call last)" in proc.stdout
        )
        assert proc.returncode in (1, 2)
        assert not has_traceback, (
            f"CLI Robustness Violation: '-s \"{bad_seed}\"' produced an unhandled traceback:\n"
            f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
        )
        combined_output = proc.stdout + proc.stderr
        assert "seed name cannot be empty" in combined_output


def test_plan_invalid_export_format_adversarial(runner: CliRunner) -> None:
    """
    Adversarial Challenge: Unsupported export format e.g. --export invalid_format.
    Verifies clean error handling without unhandled tracebacks or uncaught exceptions.
    """
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "cultura.cli.main",
            "plan",
            "--hub",
            "Bangalore",
            "-s",
            "Coffee:dining",
            "--export",
            "invalid_format",
        ],
        capture_output=True,
        text=True,
    )
    has_traceback = (
        "Traceback (most recent call last)" in proc.stderr
        or "Traceback (most recent call last)" in proc.stdout
    )
    assert proc.returncode in (1, 2)
    assert not has_traceback, (
        f"CLI Robustness Violation: '--export invalid_format' produced an unhandled traceback:\n"
        f"STDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}"
    )
    combined_output = proc.stdout + proc.stderr
    assert "Unsupported export format" in combined_output
