#!/usr/bin/env python3
"""
CULTURA Doctor SLA Benchmark Runner.

Measures `cultura doctor` wall-clock execution latency across 50 iterations:
1. Direct function call (`doctor()`)
2. CLI invocation via `CliRunner` (`app.invoke(["doctor"])`)

Asserts strict technical SLA thresholds:
- Mean latency < 10.0 ms
- Max latency < 100.0 ms
- 100% exit code 0 success rate

Author: R Jan Steve Daniel
License: Apache-2.0
"""

from __future__ import annotations

import io
import statistics
import sys
import time
from typing import Dict, List

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from typer.testing import CliRunner

import cultura.cli.main
from cultura.cli.main import app, doctor

console = Console()


def run_benchmark(iterations: int = 50) -> Dict[str, Dict[str, float]]:
    runner = CliRunner()

    # 1. Direct function call benchmark (muted output to prevent terminal I/O skew)
    original_console = cultura.cli.main.console
    cultura.cli.main.console = Console(file=io.StringIO())

    direct_latencies: List[float] = []
    try:
        # Warmup run
        doctor()
        for _ in range(iterations):
            t0 = time.perf_counter()
            doctor()
            t1 = time.perf_counter()
            direct_latencies.append((t1 - t0) * 1000.0)
    finally:
        cultura.cli.main.console = original_console

    # 2. CliRunner invocation benchmark
    cli_latencies: List[float] = []
    # Warmup run
    runner.invoke(app, ["doctor"])
    for _ in range(iterations):
        t0 = time.perf_counter()
        res = runner.invoke(app, ["doctor"])
        t1 = time.perf_counter()
        if res.exit_code != 0:
            raise RuntimeError(f"CliRunner doctor command failed with exit code {res.exit_code}")
        cli_latencies.append((t1 - t0) * 1000.0)

    results: Dict[str, Dict[str, float]] = {
        "direct": {
            "mean": statistics.mean(direct_latencies),
            "median": statistics.median(direct_latencies),
            "p95": sorted(direct_latencies)[int(iterations * 0.95)],
            "max": max(direct_latencies),
            "min": min(direct_latencies),
            "stdev": statistics.stdev(direct_latencies) if len(direct_latencies) > 1 else 0.0,
        },
        "cli": {
            "mean": statistics.mean(cli_latencies),
            "median": statistics.median(cli_latencies),
            "p95": sorted(cli_latencies)[int(iterations * 0.95)],
            "max": max(cli_latencies),
            "min": min(cli_latencies),
            "stdev": statistics.stdev(cli_latencies) if len(cli_latencies) > 1 else 0.0,
        },
    }
    return results


def main() -> int:
    console.print(
        Panel(
            "[bold cyan]CULTURA Doctor SLA Stress Benchmark (50 Iterations)[/bold cyan]\n"
            "[dim]SLA Target: Max Latency < 100.0ms | Mean Latency < 10.0ms[/dim]",
            border_style="cyan",
            box=box.ROUNDED,
        )
    )

    iterations = 50
    results = run_benchmark(iterations=iterations)

    table = Table(
        title=f"Doctor Latency Statistics ({iterations} Runs)",
        box=box.ROUNDED,
        header_style="bold magenta",
    )
    table.add_column("Benchmark Target", style="bold white", width=26)
    table.add_column("Mean (ms)", justify="right", style="cyan")
    table.add_column("Median (ms)", justify="right", style="cyan")
    table.add_column("P95 (ms)", justify="right", style="yellow")
    table.add_column("Max (ms)", justify="right", style="bold green")
    table.add_column("SLA Max (<100ms)", justify="center", width=18)
    table.add_column("SLA Mean (<10ms)", justify="center", width=18)

    all_passed = True
    for mode, label in [("direct", "Direct Function Call"), ("cli", "CliRunner Invocation")]:
        stats = results[mode]
        sla_max_ok = stats["max"] < 100.0
        sla_mean_ok = stats["mean"] < 10.0
        if not (sla_max_ok and sla_mean_ok):
            all_passed = False

        status_max = "[bold green]PASS[/bold green]" if sla_max_ok else "[bold red]FAIL[/bold red]"
        status_mean = "[bold green]PASS[/bold green]" if sla_mean_ok else "[bold red]FAIL[/bold red]"

        table.add_row(
            label,
            f"{stats['mean']:.3f}",
            f"{stats['median']:.3f}",
            f"{stats['p95']:.3f}",
            f"{stats['max']:.3f}",
            status_max,
            status_mean,
        )

    console.print(table)
    console.print()

    if all_passed:
        console.print(
            Panel(
                "[bold green]✓ STRICT SLA SATISFIED ACROSS ALL MODES[/bold green]\n"
                f"Direct Mean: {results['direct']['mean']:.2f}ms (Margin: {10.0 / results['direct']['mean']:.1f}x faster)\n"
                f"CLI Mean:    {results['cli']['mean']:.2f}ms (Margin: {10.0 / results['cli']['mean']:.1f}x faster)\n"
                f"Max Peak:    {max(results['direct']['max'], results['cli']['max']):.2f}ms (< 100.0ms limit)",
                border_style="green",
                box=box.ROUNDED,
            )
        )
        return 0
    else:
        console.print(
            Panel(
                "[bold red]✗ SLA VIOLATION DETECTED[/bold red]\n"
                "One or more latency SLA targets were exceeded.",
                border_style="red",
                box=box.ROUNDED,
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
